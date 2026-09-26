"""Aprobación y enmienda del protocolo (ADR-0008, puntos 5 a 15).

Ambas operaciones siguen el mismo esquema:

1. leen los bytes del protocolo una sola vez y validan sobre ellos;
2. preparan en memoria el nuevo texto (estado y versión) y su hash;
3. piden la confirmación del investigador en una terminal interactiva;
4. escriben, en este orden, la copia de la versión, el evento (punto de
   confirmación), el anclaje y el protocolo. Todo se sincroniza a disco
   antes de reemplazar `protocolo.yaml`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agentresearch.protocolo.archivo import (
    DocumentoProtocolo,
    actualizar_documento,
    decodificar_protocolo,
    texto_protocolo,
)
from agentresearch.protocolo.ciclo_de_vida import (
    VERSION_APROBADA,
    EstadoRegistro,
    escribir_anclaje,
    leer_estado_registro,
)
from agentresearch.protocolo.entradas import ErrorEntrada, leer_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_APROBADO,
    AdvertenciaJustificada,
    DatosAprobado,
    EstadoProtocolo,
    ModeloEvento,
    PersonaHumana,
)
from agentresearch.protocolo.modelo import Protocolo
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL, Terminal
from agentresearch.protocolo.validacion import (
    Hallazgo,
    LecturaProtocolo,
    ResultadoValidacion,
    leer_para_validar,
    validar_documento,
    validar_lectura,
)
from agentresearch.trazabilidad import (
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    escribir_atomico,
    hash_bytes,
)

Reloj = Callable[[], datetime]


class ErrorCicloDeVida(Exception):
    """La operación no se puede hacer; `errores` explica por qué, sin haber escrito nada."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("; ".join(errores))


class OperacionCancelada(Exception):
    """El investigador no confirmó la operación; no se escribió nada."""


# --- Archivo de justificaciones de las advertencias (ADR-0008, punto 10) -----------


class JustificacionAdvertencia(ModeloEvento):
    id_regla: str
    ubicacion: str | None = None
    justificacion: str


class ArchivoJustificaciones(ModeloEvento):
    justificaciones: list[JustificacionAdvertencia]


@dataclass(frozen=True, slots=True)
class ResultadoOperacion:
    """Resultado de una aprobación o una enmienda ya escrita."""

    ruta_protocolo: str
    version_anterior: str
    version_protocolo: str
    hash_protocolo: str
    ruta_version: str
    evento: EventoRegistro
    anclaje: Anclaje

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta_protocolo": self.ruta_protocolo,
            "version_anterior": self.version_anterior,
            "version_protocolo": self.version_protocolo,
            "hash_protocolo": self.hash_protocolo,
            "ruta_version": self.ruta_version,
            "evento": self.evento.id,
            "tipo_evento": self.evento.tipo,
            "datos": self.evento.datos,
            "anclaje": str(self.anclaje),
        }


# --- Aprobar ------------------------------------------------------------------------


def aprobar(
    ruta: Path | str,
    aprobado_por: str,
    terminal: Terminal,
    justificaciones: Path | str | None = None,
    reloj: Reloj | None = None,
) -> ResultadoOperacion:
    """Aprueba un borrador: lo pasa a `vigente` en la versión 1.0.0 y registra el evento.

    Lanza `ErrorCicloDeVida` si no se puede aprobar y `OperacionCancelada` si el
    investigador no confirma. En ambos casos no escribe nada.
    """
    rutas = RutasProtocolo.desde(ruta)
    lectura, registro, validacion = _leer_y_validar(rutas)
    documento = _documento_sin_errores(lectura, validacion)
    protocolo = documento.protocolo

    errores: list[str] = []
    if protocolo.estado != "borrador":
        errores.append(
            "el protocolo ya está vigente; todo cambio posterior se registra con "
            "`agentresearch protocolo enmendar`"
        )
    elif registro.ultima_version is not None:
        errores.append(
            f"el registro ya contiene una aprobación ({registro.ultima_version.evento.id})"
        )
    version_anterior = protocolo.metadatos.version_protocolo
    if protocolo.estado == "borrador" and not version_anterior.startswith("0."):
        errores.append(
            f"un borrador lleva una versión 0.y.z, y este tiene la {version_anterior}; la "
            f"aprobación fija la versión {VERSION_APROBADA}"
        )
    errores += _problemas_de_persona(protocolo, aprobado_por, "--aprobado-por")
    errores += _problemas_de_pendientes(registro)
    justificadas: dict[tuple[str, str | None], str] = {}
    if justificaciones is not None:
        try:
            justificadas = _leer_justificaciones(justificaciones, validacion.advertencias)
        except ErrorEntrada as error:
            errores += error.errores
    if errores:
        raise ErrorCicloDeVida(errores)

    contenido_nuevo = _nuevo_texto(documento, "vigente", VERSION_APROBADA)
    hash_protocolo = hash_bytes(contenido_nuevo)
    _exigir_terminal(terminal)

    terminal.mostrar(
        _resumen_aprobacion(
            rutas, protocolo, version_anterior, lectura, hash_protocolo, aprobado_por, registro
        )
    )
    advertencias = _justificar_advertencias(terminal, validacion.advertencias, justificadas)
    _confirmar_frase(terminal, f"aprobar {VERSION_APROBADA}")

    datos = DatosAprobado(
        version_anterior=version_anterior,
        version_protocolo=VERSION_APROBADA,
        hash_revisado=_hash_leido(lectura),
        hash_protocolo=hash_protocolo,
        ruta_protocolo=rutas.relativa(rutas.protocolo),
        ruta_version=rutas.relativa(rutas.copia_de_version(VERSION_APROBADA)),
        aprobado_por=PersonaHumana(tipo="humano", id=aprobado_por),
        advertencias=advertencias,
    )
    evento, anclaje = escribir_version(
        rutas, lectura, VERSION_APROBADA, contenido_nuevo, TIPO_APROBADO, datos, reloj
    )
    return ResultadoOperacion(
        ruta_protocolo=datos.ruta_protocolo,
        version_anterior=version_anterior,
        version_protocolo=VERSION_APROBADA,
        hash_protocolo=hash_protocolo,
        ruta_version=datos.ruta_version,
        evento=evento,
        anclaje=anclaje,
    )


def _resumen_aprobacion(
    rutas: RutasProtocolo,
    protocolo: Protocolo,
    version_anterior: str,
    lectura: LecturaProtocolo,
    hash_protocolo: str,
    aprobado_por: str,
    registro: EstadoRegistro,
) -> str:
    confirmadas = [d.id_decision for d in registro.decisiones.values() if d.estado == "confirmada"]
    return "\n".join(
        [
            f"Aprobación del protocolo {rutas.relativa(rutas.protocolo)}",
            f"  título: {protocolo.metadatos.titulo}",
            f"  versión: {version_anterior} → {VERSION_APROBADA} (borrador → vigente)",
            f"  hash del archivo revisado: {_hash_leido(lectura)}",
            f"  hash del protocolo aprobado: {hash_protocolo}",
            f"  aprobado por: {aprobado_por}",
            f"  decisiones confirmadas: {', '.join(confirmadas) if confirmadas else 'ninguna'}",
        ]
    )


def _leer_justificaciones(
    ruta: Path | str, advertencias: list[Hallazgo]
) -> dict[tuple[str, str | None], str]:
    nombre = str(ruta)
    archivo = validar_modelo(ArchivoJustificaciones, leer_json(ruta), nombre)
    activas = {(a.id_regla, a.ubicacion) for a in advertencias}
    justificadas: dict[tuple[str, str | None], str] = {}
    errores: list[str] = []
    for entrada in archivo.justificaciones:
        clave = (entrada.id_regla, entrada.ubicacion)
        descripcion = f"{entrada.id_regla} en {entrada.ubicacion or '(sin ubicación)'}"
        if clave in justificadas:
            errores.append(f"{nombre}: la advertencia {descripcion} está repetida")
        elif clave not in activas:
            errores.append(
                f"{nombre}: la advertencia {descripcion} no corresponde a ninguna advertencia "
                "activa del protocolo"
            )
        elif not entrada.justificacion.strip():
            errores.append(f"{nombre}: la justificación de {descripcion} está vacía")
        else:
            justificadas[clave] = entrada.justificacion.strip()
    if errores:
        raise ErrorEntrada(errores)
    return justificadas


def _justificar_advertencias(
    terminal: Terminal,
    advertencias: list[Hallazgo],
    justificadas: dict[tuple[str, str | None], str],
) -> list[AdvertenciaJustificada]:
    """Muestra cada advertencia con su justificación y pide las que falten."""
    if not advertencias:
        terminal.mostrar("Advertencias activas: ninguna")
        return []
    terminal.mostrar(f"Advertencias activas: {len(advertencias)}, cada una con su justificación")
    resultado = []
    for advertencia in advertencias:
        terminal.mostrar(f"  - {advertencia}")
        texto = justificadas.get((advertencia.id_regla, advertencia.ubicacion))
        origen: Literal["archivo", "terminal"] = "archivo"
        if texto is not None:
            terminal.mostrar(f"    justificación (archivo): {texto}")
        else:
            respuesta = terminal.preguntar("    justificación: ")
            texto = (respuesta or "").strip()
            origen = "terminal"
            if not texto:
                raise OperacionCancelada(
                    f"la advertencia {advertencia.id_regla} necesita una justificación"
                )
        resultado.append(
            AdvertenciaJustificada(
                id_regla=advertencia.id_regla,
                ubicacion=advertencia.ubicacion,
                mensaje=advertencia.mensaje,
                referencia=advertencia.referencia,
                justificacion=texto,
                origen=origen,
            )
        )
    return resultado


# --- Piezas compartidas con la enmienda ---------------------------------------------


def _leer_y_validar(
    rutas: RutasProtocolo,
) -> tuple[LecturaProtocolo, EstadoRegistro, ResultadoValidacion]:
    lectura = leer_para_validar(rutas.protocolo)
    registro = leer_estado_registro(rutas)
    return lectura, registro, validar_lectura(lectura, registro)


def _documento_sin_errores(
    lectura: LecturaProtocolo,
    validacion: ResultadoValidacion,
    admitir: Callable[[Hallazgo], bool] = lambda _hallazgo: False,
) -> DocumentoProtocolo:
    """Devuelve el documento si no hay errores de validación (salvo los admitidos)."""
    errores = [str(h) for h in validacion.errores if not admitir(h)]
    if errores or lectura.documento is None:
        raise ErrorCicloDeVida(errores)
    return lectura.documento


def _hash_leido(lectura: LecturaProtocolo) -> str:
    assert lectura.hash is not None  # hay documento, así que se leyeron los bytes
    return lectura.hash


def _problemas_de_persona(protocolo: Protocolo, id_persona: str, opcion: str) -> list[str]:
    """Exige que `id_persona` sea un revisor humano declarado en `seleccion.revisores`."""
    revisores = {revisor.id: revisor.tipo for revisor in protocolo.seleccion.revisores}
    humanos = [id_revisor for id_revisor, tipo in revisores.items() if tipo == "humano"]
    if revisores.get(id_persona) == "humano":
        return []
    if revisores.get(id_persona) == "llm":
        return [
            f"{opcion} {id_persona!r} es un revisor de tipo llm; el LLM propone, pero decide "
            "el investigador (CLAUDE.md, regla 1)"
        ]
    return [
        f"{opcion} {id_persona!r} no es un revisor humano declarado en seleccion.revisores "
        f"(humanos: {', '.join(humanos) or 'ninguno'})"
    ]


def _problemas_de_pendientes(registro: EstadoRegistro) -> list[str]:
    if not registro.pendientes:
        return []
    ids = ", ".join(d.id_decision for d in registro.pendientes)
    return [
        f"hay decisiones pendientes de confirmar ({ids}); el investigador las confirma con "
        "`agentresearch protocolo decision confirmar`, o las reemplaza"
    ]


def _nuevo_texto(documento: DocumentoProtocolo, estado: EstadoProtocolo, version: str) -> bytes:
    """Texto del protocolo con otro estado y otra versión, conservando comentarios y comillas."""
    nuevo = documento.protocolo.model_copy(deep=True)
    nuevo.estado = estado
    nuevo.metadatos.version_protocolo = version
    actualizar_documento(documento, nuevo)
    contenido = texto_protocolo(documento).encode("utf-8")
    # Comprobación interna: el texto nuevo se lee con el estado y la versión esperados, sin errores.
    releido = decodificar_protocolo(contenido)
    errores = [h for h in validar_documento(releido) if h.severidad == "error"]
    if (
        releido.protocolo.estado != estado
        or releido.protocolo.metadatos.version_protocolo != version
        or errores
    ):
        raise ErrorCicloDeVida(["error interno: el texto nuevo del protocolo no es el esperado"])
    return contenido


def _exigir_terminal(terminal: Terminal) -> None:
    if not terminal.es_interactiva():
        raise ErrorCicloDeVida([MENSAJE_SIN_TERMINAL])


def _confirmar_frase(terminal: Terminal, frase: str) -> None:
    respuesta = terminal.preguntar(
        f"Escriba «{frase}» para confirmar, o cualquier otra cosa para cancelar: "
    )
    if respuesta is None or respuesta.strip() != frase:
        raise OperacionCancelada(f"no se escribió «{frase}»")


def escribir_version(
    rutas: RutasProtocolo,
    lectura: LecturaProtocolo,
    version: str,
    contenido_nuevo: bytes,
    tipo: str,
    datos: ModeloEvento,
    reloj: Reloj | None,
) -> tuple[EventoRegistro, Anclaje]:
    """Escribe copia, evento, anclaje y protocolo, en ese orden (ADR-0008, punto 14).

    Antes de escribir, comprueba que el protocolo no cambió desde que se leyó
    (por ejemplo, mientras el investigador confirmaba).
    """
    try:
        actual = rutas.protocolo.read_bytes()
    except OSError:
        actual = None
    if actual != lectura.contenido:
        raise OperacionCancelada(
            f"{rutas.relativa(rutas.protocolo)} cambió mientras se confirmaba; vuelva a "
            "ejecutar el comando"
        )
    escribir_atomico(rutas.copia_de_version(version), contenido_nuevo)
    registro = (
        RegistroEncadenado(rutas.eventos, reloj=reloj)
        if reloj is not None
        else RegistroEncadenado(rutas.eventos)
    )
    evento = registro.agregar(tipo, datos.model_dump(mode="json"))
    anclaje = escribir_anclaje(rutas)
    escribir_atomico(rutas.protocolo, contenido_nuevo)
    return evento, anclaje
