"""Actualización del agente en un estudio: `agentresearch estudio actualizar` (ADR-0007).

Un estudio vive varios hitos, y cada versión del agente puede traer
instrucciones nuevas (reglas del `CLAUDE.md`, permisos, *skills*). El
procedimiento es:

1. el investigador cambia la versión del agente en `pyproject.toml` y ejecuta
   `uv sync`;
2. ejecuta en su terminal `estudio actualizar`, que toma la versión instalada,
   regenera desde las plantillas los archivos que el paquete administra
   (conservando el modelo fijado), muestra el diff de cada uno y pide la
   frase de confirmación;
3. el comando registra el evento `estudio_actualizado` y escribe los archivos;
4. el investigador hace el commit con el anclaje en el mensaje.

Como `aprobar`, exige una terminal interactiva y un revisor humano declarado:
el LLM no actualiza sus propias instrucciones. El evento es el punto de
confirmación: se escribe antes que los archivos, y si algo falla después,
volver a ejecutar el comando completa la actualización, sin otro evento, si los
archivos que genera coinciden con los hashes registrados.
"""

import difflib
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ruamel.yaml.error import YAMLError

from agentresearch.estudio.creacion import (
    ADMINISTRADOS,
    renderizar,
    texto_de_plantilla,
    valores_de_plantilla,
)
from agentresearch.estudio.modelo import (
    NOMBRE_ARCHIVO,
    Agente,
    Estudio,
    leer_estudio,
    texto_estudio,
)
from agentresearch.protocolo.aprobacion import (
    ErrorCicloDeVida,
    OperacionCancelada,
    confirmar_frase,
    exigir_terminal,
    problemas_de_persona,
)
from agentresearch.protocolo.ciclo_de_vida import (
    ActualizacionRegistrada,
    escribir_anclaje,
    falta_anclaje,
    leer_estado_registro,
)
from agentresearch.protocolo.entradas import ErrorEntrada, leer_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_ESTUDIO_ACTUALIZADO,
    ArchivoActualizado,
    ArchivoRegistrado,
    DatosEstudioActualizado,
    ModeloEvento,
    PersonaHumana,
    TextoNoVacio,
)
from agentresearch.protocolo.instrucciones import es_ruta_de_instrucciones, hashes_de_instrucciones
from agentresearch.protocolo.terminal import Terminal
from agentresearch.protocolo.validacion import leer_para_validar
from agentresearch.trazabilidad import (
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    escribir_atomico,
    hash_bytes,
)

Reloj = Callable[[], datetime]


class ArchivoJustificacion(ModeloEvento):
    """Contenido de `--archivo`: `{"justificacion": "…"}`."""

    justificacion: TextoNoVacio


@dataclass(frozen=True, slots=True)
class CambioArchivo:
    """Un archivo administrado por el paquete: su contenido actual y el nuevo."""

    ruta: str
    anterior: bytes | None
    nuevo: bytes

    @property
    def cambia(self) -> bool:
        return self.anterior != self.nuevo

    def diff(self) -> list[str]:
        """Diff unificado del archivo, línea por línea."""
        anterior = self.anterior.decode("utf-8").splitlines() if self.anterior is not None else []
        return list(
            difflib.unified_diff(
                anterior,
                self.nuevo.decode("utf-8").splitlines(),
                fromfile=f"a/{self.ruta}" if self.anterior is not None else "/dev/null",
                tofile=f"b/{self.ruta}",
                lineterm="",
            )
        )


@dataclass(frozen=True, slots=True)
class ResultadoActualizacion:
    """Una actualización del agente ya registrada y escrita."""

    version_anterior: str
    version_nueva: str
    archivos_cambiados: list[str]
    evento: EventoRegistro
    anclaje: Anclaje
    anclaje_recreado: bool = False
    completada: bool = False
    """Se completó una actualización interrumpida, ya registrada en `evento`."""

    def como_dict(self) -> dict[str, Any]:
        return {
            "completada": self.completada,
            "version_anterior": self.version_anterior,
            "version_nueva": self.version_nueva,
            "archivos_cambiados": self.archivos_cambiados,
            "evento": self.evento.id,
            "tipo_evento": self.evento.tipo,
            "datos": self.evento.datos,
            "anclaje": str(self.anclaje),
            "anclaje_recreado": self.anclaje_recreado,
        }


def actualizar_estudio(
    ruta_estudio: Path | str,
    actualizado_por: str,
    terminal: Terminal,
    justificacion: str | None = None,
    archivo_justificacion: Path | str | None = None,
    reloj: Reloj | None = None,
) -> ResultadoActualizacion:
    """Pasa el estudio a la versión instalada del agente, tras la confirmación interactiva.

    Lanza `ErrorCicloDeVida`, sin escribir nada, si no se puede actualizar, y
    `OperacionCancelada` si el investigador no confirma.
    """
    raiz = Path(ruta_estudio).resolve()
    rutas = RutasProtocolo.desde(raiz / "protocolo" / "protocolo.yaml")
    texto_justificacion = _justificacion(justificacion, archivo_justificacion)
    estudio = _leer_estudio(raiz)

    problemas: list[str] = []
    registro = leer_estado_registro(rutas)
    if not registro.integro:
        raise ErrorCicloDeVida(
            [f"el registro de eventos no es íntegro (P-E10): {p}" for p in registro.problemas]
        )
    registrada = registro.version_agente_registrada
    if registrada is None:
        raise ErrorCicloDeVida(
            [
                f"{rutas.relativa(rutas.eventos)} no tiene el evento estudio_creado: el estudio "
                "no se creó con `agentresearch nuevo-estudio`"
            ]
        )
    ultima = registro.actualizaciones[-1] if registro.actualizaciones else None
    if (
        ultima is not None
        and registrada != estudio.agente.version
        and estudio.agente.version == ultima.datos.version_anterior
    ):
        # El evento se registró, pero la escritura de los archivos no terminó.
        return _completar_interrumpida(raiz, estudio, ultima, registro.anclaje_actual)
    if registrada != estudio.agente.version:
        problemas.append(
            f"{NOMBRE_ARCHIVO} dice que el agente es {estudio.agente.version}, pero el registro "
            f"dice {registrada}; restaure {NOMBRE_ARCHIVO} con Git"
        )
    lectura = leer_para_validar(rutas.protocolo)
    if lectura.documento is None:
        problemas.append(
            f"no se pudo leer {rutas.relativa(rutas.protocolo)} para comprobar el revisor; "
            "ejecute `agentresearch protocolo validar`"
        )
    else:
        problemas += problemas_de_persona(
            lectura.documento.protocolo, actualizado_por, "--actualizado-por"
        )
    instalada = version("agentresearch")
    fuente = _fuente_en_pyproject(raiz, instalada, problemas)
    if problemas:
        raise ErrorCicloDeVida(problemas)
    assert fuente is not None  # sin problemas, pyproject.toml fija la versión instalada

    nuevo = estudio.model_copy(update={"agente": Agente(version=instalada, fuente=fuente)})
    cambios = _cambios(raiz, nuevo)
    if instalada == estudio.agente.version and not any(c.cambia for c in cambios):
        raise ErrorCicloDeVida(
            [
                f"nada que actualizar: el estudio ya usa agentresearch {instalada} y sus "
                "archivos coinciden con las plantillas. Para pasar a otra versión, cámbiela en "
                "pyproject.toml y ejecute `uv sync` antes"
            ]
        )

    exigir_terminal(terminal)
    terminal.mostrar(
        "\n".join(
            _resumen(estudio.agente, nuevo.agente, cambios, texto_justificacion, actualizado_por)
        )
    )
    confirmar_frase(terminal, f"actualizar {instalada}")

    for cambio in cambios:
        if _leer(raiz, cambio.ruta) != cambio.anterior:
            raise OperacionCancelada(
                f"{cambio.ruta} cambió mientras se confirmaba; vuelva a ejecutar el comando"
            )
    datos = DatosEstudioActualizado(
        version_anterior=estudio.agente.version,
        version_nueva=instalada,
        fuente_anterior=estudio.agente.fuente,
        fuente_nueva=fuente,
        archivos=[
            ArchivoActualizado(
                ruta=cambio.ruta,
                hash_anterior=hash_bytes(cambio.anterior) if cambio.anterior is not None else None,
                hash_nuevo=hash_bytes(cambio.nuevo),
            )
            for cambio in cambios
        ],
        instrucciones=_instrucciones_despues(raiz, cambios),
        justificacion=texto_justificacion,
        actualizado_por=PersonaHumana(tipo="humano", id=actualizado_por),
    )
    recreado = falta_anclaje(rutas)
    registro_eventos = (
        RegistroEncadenado(rutas.eventos, reloj=reloj)
        if reloj is not None
        else RegistroEncadenado(rutas.eventos)
    )
    evento = registro_eventos.agregar(TIPO_ESTUDIO_ACTUALIZADO, datos.model_dump(mode="json"))
    anclaje = escribir_anclaje(rutas)
    _escribir_cambios(raiz, cambios)
    return ResultadoActualizacion(
        version_anterior=estudio.agente.version,
        version_nueva=instalada,
        archivos_cambiados=[cambio.ruta for cambio in cambios if cambio.cambia],
        evento=evento,
        anclaje=anclaje,
        anclaje_recreado=recreado,
    )


def _escribir_cambios(raiz: Path, cambios: list[CambioArchivo]) -> None:
    """Escribe los archivos que cambian; `estudio.yaml` al final.

    Mientras `estudio.yaml` conserve la versión anterior, el comando reconoce
    una actualización interrumpida y la completa.
    """
    for cambio in sorted(cambios, key=lambda c: c.ruta == NOMBRE_ARCHIVO):
        if cambio.cambia:
            escribir_atomico(raiz.joinpath(*cambio.ruta.split("/")), cambio.nuevo)


def _completar_interrumpida(
    raiz: Path,
    estudio: Estudio,
    ultima: ActualizacionRegistrada,
    anclaje: Anclaje | None,
) -> ResultadoActualizacion:
    """Completa una actualización ya registrada cuya escritura de archivos no terminó.

    No registra otro evento ni pide confirmación: la actualización ya se
    confirmó. Solo escribe si los archivos que genera la versión instalada
    tienen exactamente los hashes que registró el evento.
    """
    datos = ultima.datos
    evento = ultima.evento
    instalada = version("agentresearch")
    if instalada != datos.version_nueva:
        raise ErrorCicloDeVida(
            [
                f"la actualización a {datos.version_nueva} registrada en {evento.id} se "
                f"interrumpió antes de escribir los archivos, y la versión instalada es "
                f"{instalada}: instale {datos.version_nueva} con `uv sync` y vuelva a ejecutar "
                "el comando para completarla"
            ]
        )
    nuevo = estudio.model_copy(
        update={"agente": Agente(version=datos.version_nueva, fuente=datos.fuente_nueva)}
    )
    cambios = _cambios(raiz, nuevo)
    generados = {cambio.ruta: hash_bytes(cambio.nuevo) for cambio in cambios}
    if generados != {archivo.ruta: archivo.hash_nuevo for archivo in datos.archivos}:
        raise ErrorCicloDeVida(
            [
                f"la actualización registrada en {evento.id} se interrumpió, pero los archivos "
                "que se generarían ahora no coinciden con los registrados; restaure el estudio "
                "con Git"
            ]
        )
    _escribir_cambios(raiz, cambios)
    assert anclaje is not None  # el registro es íntegro y tiene al menos este evento
    return ResultadoActualizacion(
        version_anterior=datos.version_anterior,
        version_nueva=datos.version_nueva,
        archivos_cambiados=[cambio.ruta for cambio in cambios if cambio.cambia],
        evento=evento,
        anclaje=anclaje,
        completada=True,
    )


def _justificacion(texto: str | None, archivo: Path | str | None) -> str:
    if (texto is None) == (archivo is None):
        raise ErrorCicloDeVida(
            ["dé la justificación con --justificacion o con --archivo, no ambos"]
        )
    if texto is not None:
        if not texto.strip():
            raise ErrorCicloDeVida(["la justificación no puede estar vacía"])
        return texto
    assert archivo is not None
    try:
        return validar_modelo(
            ArchivoJustificacion, leer_json(Path(archivo)), str(archivo)
        ).justificacion
    except ErrorEntrada as error:
        raise ErrorCicloDeVida(error.errores) from None


def _leer_estudio(raiz: Path) -> Estudio:
    try:
        return leer_estudio(raiz / NOMBRE_ARCHIVO)
    except FileNotFoundError:
        raise ErrorCicloDeVida(
            [
                f"no existe {raiz / NOMBRE_ARCHIVO}: ejecute el comando en la raíz del "
                "estudio o use --estudio"
            ]
        ) from None
    except (OSError, ValueError, YAMLError) as error:
        raise ErrorCicloDeVida([f"{NOMBRE_ARCHIVO} no es válido: {error}"]) from None


def _fuente_en_pyproject(raiz: Path, instalada: str, problemas: list[str]) -> str | None:
    """La fuente del agente en `pyproject.toml`, si fija la versión instalada."""
    try:
        datos = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        problemas.append(f"no se pudo leer pyproject.toml: {error}")
        return None
    dependencias = datos.get("project", {}).get("dependencies", [])
    fuentes = [
        dependencia.split("@", 1)[1].strip()
        for dependencia in dependencias
        if isinstance(dependencia, str)
        and dependencia.split("@", 1)[0].strip() == "agentresearch"
        and "@" in dependencia
    ]
    if len(fuentes) != 1:
        problemas.append(
            "pyproject.toml debe tener una sola dependencia «agentresearch @ git+…@v<versión>»"
        )
        return None
    if not fuentes[0].endswith(f"@v{instalada}"):
        problemas.append(
            f"pyproject.toml fija {fuentes[0]}, pero la versión instalada es {instalada}: "
            "ejecute `uv sync` después de cambiar la versión en pyproject.toml"
        )
        return None
    return fuentes[0]


def _cambios(raiz: Path, nuevo: Estudio) -> list[CambioArchivo]:
    valores = valores_de_plantilla(nuevo)
    cambios = [
        CambioArchivo(
            destino,
            _leer(raiz, destino),
            renderizar(texto_de_plantilla(origen), valores).encode("utf-8"),
        )
        for origen, destino in ADMINISTRADOS.items()
    ]
    cambios.append(
        CambioArchivo(
            NOMBRE_ARCHIVO, _leer(raiz, NOMBRE_ARCHIVO), texto_estudio(nuevo).encode("utf-8")
        )
    )
    return cambios


def _leer(raiz: Path, relativa: str) -> bytes | None:
    try:
        return raiz.joinpath(*relativa.split("/")).read_bytes()
    except FileNotFoundError:
        return None


def _instrucciones_despues(raiz: Path, cambios: list[CambioArchivo]) -> list[ArchivoRegistrado]:
    """Hashes de todas las instrucciones del agente como quedarán después de escribir."""
    hashes = hashes_de_instrucciones(raiz)
    for cambio in cambios:
        if es_ruta_de_instrucciones(cambio.ruta):
            hashes[cambio.ruta] = hash_bytes(cambio.nuevo)
    return [ArchivoRegistrado(ruta=ruta, hash=hashes[ruta]) for ruta in sorted(hashes)]


def _resumen(
    anterior: Agente,
    nuevo: Agente,
    cambios: list[CambioArchivo],
    justificacion: str,
    actualizado_por: str,
) -> list[str]:
    lineas = [
        "Actualización del agente en el estudio",
        f"  versión: {anterior.version} → {nuevo.version}",
        f"  fuente: {anterior.fuente} → {nuevo.fuente}",
        f"  actualiza: {actualizado_por}",
        f"  justificación: {justificacion}",
        "",
    ]
    cambiados = [cambio for cambio in cambios if cambio.cambia]
    sin_cambio = [cambio.ruta for cambio in cambios if not cambio.cambia]
    lineas.append(f"Archivos que cambian: {len(cambiados)}")
    for cambio in cambiados:
        lineas += cambio.diff()
    if sin_cambio:
        lineas.append(f"Sin cambios: {', '.join(sin_cambio)}")
    return lineas
