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
    ErrorLecturaProtocolo,
    actualizar_documento,
    decodificar_protocolo,
    texto_protocolo,
)
from agentresearch.protocolo.ciclo_de_vida import (
    VERSION_APROBADA,
    EstadoRegistro,
    VersionRegistrada,
    escribir_anclaje,
    falta_anclaje,
    leer_estado_registro,
    siguiente_version,
)
from agentresearch.protocolo.diferencias import Cambio, diferencias_protocolo
from agentresearch.protocolo.entradas import ErrorEntrada, leer_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_APROBADO,
    TIPO_ENMENDADO,
    AdvertenciaJustificada,
    AdvertenciaRegistrada,
    CambioRegistrado,
    DatosAprobado,
    DatosEnmendado,
    EstadoProtocolo,
    ModeloEvento,
    Nivel,
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
    anclaje_recreado: bool = False
    """`anclaje.json` faltaba y se volvió a crear (ADR-0008, punto 21)."""

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
            "anclaje_recreado": self.anclaje_recreado,
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
    lectura, registro, validacion = leer_y_validar(rutas)
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
    errores += problemas_de_persona(protocolo, aprobado_por, "--aprobado-por")
    errores += _problemas_de_pendientes(registro)
    justificadas: dict[ClaveAdvertencia, str] = {}
    if justificaciones is not None:
        try:
            justificadas = _leer_justificaciones(justificaciones, validacion.advertencias)
        except ErrorEntrada as error:
            errores += error.errores
    if errores:
        raise ErrorCicloDeVida(errores)

    contenido_nuevo = _nuevo_texto(documento, "vigente", VERSION_APROBADA)
    hash_protocolo = hash_bytes(contenido_nuevo)
    exigir_terminal(terminal)

    terminal.mostrar(
        _resumen_aprobacion(
            rutas, protocolo, version_anterior, lectura, hash_protocolo, aprobado_por, registro
        )
    )
    advertencias_activas = validacion.advertencias
    textos = _justificar_advertencias(
        terminal,
        advertencias_activas,
        justificadas,
        f"Advertencias activas: {len(advertencias_activas)}, cada una con su justificación",
    )
    confirmar_frase(terminal, f"aprobar {VERSION_APROBADA}")
    advertencias = [
        AdvertenciaJustificada(
            id_regla=a.id_regla,
            ubicacion=a.ubicacion,
            mensaje=a.mensaje,
            referencia=a.referencia,
            justificacion=textos[clave_advertencia(a)][0],
            origen=textos[clave_advertencia(a)][1],
        )
        for a in advertencias_activas
    ]

    datos = DatosAprobado(
        version_anterior=version_anterior,
        version_protocolo=VERSION_APROBADA,
        hash_revisado=hash_leido(lectura),
        hash_protocolo=hash_protocolo,
        ruta_protocolo=rutas.relativa(rutas.protocolo),
        ruta_version=rutas.relativa(rutas.copia_de_version(VERSION_APROBADA)),
        aprobado_por=PersonaHumana(tipo="humano", id=aprobado_por),
        advertencias=advertencias,
    )
    evento, anclaje, recreado = escribir_version(
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
        anclaje_recreado=recreado,
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
            f"  hash del archivo revisado: {hash_leido(lectura)}",
            f"  hash del protocolo aprobado: {hash_protocolo}",
            f"  aprobado por: {aprobado_por}",
            f"  decisiones confirmadas: {', '.join(confirmadas) if confirmadas else 'ninguna'}",
        ]
    )


ClaveAdvertencia = tuple[str, str | None]
OrigenJustificacion = Literal["archivo", "terminal"]


def clave_advertencia(advertencia: Hallazgo) -> ClaveAdvertencia:
    """Identifica una advertencia por su regla y su ubicación (ADR-0008, punto 10)."""
    return (advertencia.id_regla, advertencia.ubicacion)


def _leer_justificaciones(
    ruta: Path | str,
    a_justificar: list[Hallazgo],
    ya_activas: frozenset[ClaveAdvertencia] = frozenset(),
    version_anterior: str | None = None,
) -> dict[ClaveAdvertencia, str]:
    """Lee el archivo de justificaciones y empareja cada entrada con una advertencia.

    `ya_activas` son las advertencias de una enmienda que ya estaban activas en
    la versión anterior: no se vuelven a justificar, así que una entrada para
    ellas es un error, igual que una que no corresponde a ninguna advertencia.
    """
    nombre = str(ruta)
    archivo = validar_modelo(ArchivoJustificaciones, leer_json(ruta), nombre)
    activas = {clave_advertencia(a) for a in a_justificar}
    justificadas: dict[ClaveAdvertencia, str] = {}
    errores: list[str] = []
    for entrada in archivo.justificaciones:
        clave = (entrada.id_regla, entrada.ubicacion)
        descripcion = f"{entrada.id_regla} en {entrada.ubicacion or '(sin ubicación)'}"
        if clave in justificadas:
            errores.append(f"{nombre}: la advertencia {descripcion} está repetida")
        elif clave in ya_activas:
            errores.append(
                f"{nombre}: la advertencia {descripcion} ya estaba activa en la versión "
                f"{version_anterior}; al enmendar solo se justifican las advertencias nuevas"
            )
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
    justificadas: dict[ClaveAdvertencia, str],
    encabezado: str,
    ya_activas: frozenset[ClaveAdvertencia] = frozenset(),
    version_anterior: str | None = None,
) -> dict[ClaveAdvertencia, tuple[str, OrigenJustificacion]]:
    """Muestra cada advertencia con su justificación y pide las que falten.

    Las advertencias de `ya_activas` se muestran sin pedir justificación.
    Devuelve el texto y el origen de la justificación de cada una de las demás.
    """
    if not advertencias:
        terminal.mostrar("Advertencias activas: ninguna")
        return {}
    terminal.mostrar(encabezado)
    resultado: dict[ClaveAdvertencia, tuple[str, OrigenJustificacion]] = {}
    for advertencia in advertencias:
        terminal.mostrar(f"  - {advertencia}")
        clave = clave_advertencia(advertencia)
        if clave in ya_activas:
            terminal.mostrar(f"    ya estaba activa en la versión {version_anterior}")
            continue
        texto = justificadas.get(clave)
        if texto is not None:
            terminal.mostrar(f"    justificación (archivo): {texto}")
            resultado[clave] = (texto, "archivo")
            continue
        texto = (terminal.preguntar("    justificación: ") or "").strip()
        if not texto:
            raise OperacionCancelada(
                f"la advertencia {advertencia.id_regla} necesita una justificación"
            )
        resultado[clave] = (texto, "terminal")
    return resultado


# --- Enmendar -----------------------------------------------------------------------

NivelElegido = Literal["mayor", "menor"]
"""Niveles que elige el investigador; el parche lo asigna el paquete (ADR-0008, punto 6)."""


class ArchivoEnmienda(ModeloEvento):
    """Contenido de `--archivo-enmienda` (ADR-0008, punto 12)."""

    justificacion: str
    efecto_esperado: str


@dataclass(frozen=True, slots=True)
class PropuestaEnmienda:
    """Lo que registraría una enmienda: diff, versión siguiente y lo que la impediría."""

    ruta_protocolo: str
    version_registrada: str
    evento_registrado: str
    cambios: list[Cambio]
    nivel: Nivel | None
    version_siguiente: str | None
    problemas: list[str]
    advertencias_nuevas: list[Hallazgo]
    """Advertencias activas que no lo estaban en la versión registrada: exigen justificación."""

    @property
    def solo_formato(self) -> bool:
        return not self.cambios

    @property
    def opciones_de_version(self) -> dict[str, str]:
        """Versión siguiente para cada nivel que se puede elegir, si aún no se eligió."""
        if self.nivel is not None:
            return {}
        return {
            nivel: siguiente_version(self.version_registrada, nivel) for nivel in ("menor", "mayor")
        }

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta_protocolo": self.ruta_protocolo,
            "version_registrada": self.version_registrada,
            "evento_registrado": self.evento_registrado,
            "nivel": self.nivel,
            "version_siguiente": self.version_siguiente,
            "opciones_de_version": self.opciones_de_version,
            "solo_formato": self.solo_formato,
            "cambios": [cambio.como_dict() for cambio in self.cambios],
            "advertencias_nuevas": [a.como_dict() for a in self.advertencias_nuevas],
            "problemas": self.problemas,
            "se_puede_enmendar": not self.problemas,
        }


@dataclass(slots=True)
class _Enmienda:
    """Estado interno de una enmienda en preparación."""

    rutas: RutasProtocolo
    lectura: LecturaProtocolo
    validacion: ResultadoValidacion
    documento: DocumentoProtocolo
    ultima: VersionRegistrada
    propuesta: PropuestaEnmienda


def simular_enmienda(ruta: Path | str, nivel: NivelElegido | None = None) -> PropuestaEnmienda:
    """Calcula el diff y la versión siguiente sin escribir nada ni exigir terminal.

    Lanza `ErrorCicloDeVida` solo si no se puede calcular el diff (protocolo
    ilegible, sin aprobación o con el registro dañado). Lo demás que impediría
    enmendar se devuelve en `problemas`.
    """
    return _preparar_enmienda(RutasProtocolo.desde(ruta), nivel).propuesta


def enmendar(
    ruta: Path | str,
    nivel: NivelElegido | None,
    enmendado_por: str | None,
    terminal: Terminal,
    justificacion: str | None = None,
    efecto_esperado: str | None = None,
    archivo_enmienda: Path | str | None = None,
    reloj: Reloj | None = None,
    justificaciones: Path | str | None = None,
) -> ResultadoOperacion:
    """Registra una enmienda de un protocolo vigente e incrementa su versión.

    Las advertencias que no estaban activas en la versión registrada exigen una
    justificación, del archivo `justificaciones` o de la terminal (ADR-0008,
    punto 10). Lanza `ErrorCicloDeVida` si no se puede enmendar y
    `OperacionCancelada` si el investigador no confirma. En ambos casos no
    escribe nada.
    """
    enmienda = _preparar_enmienda(RutasProtocolo.desde(ruta), nivel)
    propuesta = enmienda.propuesta
    errores = list(propuesta.problemas)
    if propuesta.nivel is None:
        errores.append("falta --nivel mayor|menor")
    if enmendado_por is None:
        errores.append("falta --enmendado-por")
    else:
        errores += problemas_de_persona(
            enmienda.documento.protocolo, enmendado_por, "--enmendado-por"
        )
    textos: tuple[str, str] | None = None
    try:
        textos = _textos_de_enmienda(justificacion, efecto_esperado, archivo_enmienda)
    except ErrorEntrada as error:
        errores += error.errores
    ya_activas = _claves_registradas(enmienda.ultima)
    justificadas: dict[ClaveAdvertencia, str] = {}
    if justificaciones is not None:
        try:
            justificadas = _leer_justificaciones(
                justificaciones, propuesta.advertencias_nuevas, ya_activas, enmienda.ultima.version
            )
        except ErrorEntrada as error:
            errores += error.errores
    if errores:
        raise ErrorCicloDeVida(errores)
    assert propuesta.nivel is not None and propuesta.version_siguiente is not None
    assert enmendado_por is not None and textos is not None
    texto_justificacion, texto_efecto = textos

    version = propuesta.version_siguiente
    contenido_nuevo = _nuevo_texto(enmienda.documento, "vigente", version)
    hash_protocolo = hash_bytes(contenido_nuevo)
    exigir_terminal(terminal)

    rutas = enmienda.rutas
    terminal.mostrar(
        _resumen_enmienda(
            enmienda, hash_protocolo, enmendado_por, texto_justificacion, texto_efecto
        )
    )
    advertencias_activas = enmienda.validacion.advertencias
    textos_advertencias = _justificar_advertencias(
        terminal,
        advertencias_activas,
        justificadas,
        f"Advertencias activas: {len(advertencias_activas)}; se justifican las nuevas, que no "
        f"estaban activas en la versión {enmienda.ultima.version}",
        ya_activas,
        enmienda.ultima.version,
    )
    confirmar_frase(terminal, f"enmendar {version}")

    datos = DatosEnmendado(
        version_anterior=enmienda.ultima.version,
        version_protocolo=version,
        nivel=propuesta.nivel,
        hash_protocolo_anterior=enmienda.ultima.hash_protocolo,
        hash_revisado=hash_leido(enmienda.lectura),
        hash_protocolo=hash_protocolo,
        ruta_protocolo=rutas.relativa(rutas.protocolo),
        ruta_version=rutas.relativa(rutas.copia_de_version(version)),
        justificacion=texto_justificacion,
        efecto_esperado=texto_efecto,
        enmendado_por=PersonaHumana(tipo="humano", id=enmendado_por),
        cambios=[CambioRegistrado.model_validate(c.como_dict()) for c in propuesta.cambios],
        solo_formato=propuesta.solo_formato,
        advertencias=[
            _advertencia_registrada(a, textos_advertencias.get(clave_advertencia(a)))
            for a in advertencias_activas
        ],
    )
    evento, anclaje, recreado = escribir_version(
        rutas, enmienda.lectura, version, contenido_nuevo, TIPO_ENMENDADO, datos, reloj
    )
    return ResultadoOperacion(
        ruta_protocolo=datos.ruta_protocolo,
        version_anterior=datos.version_anterior,
        version_protocolo=version,
        hash_protocolo=hash_protocolo,
        ruta_version=datos.ruta_version,
        evento=evento,
        anclaje=anclaje,
        anclaje_recreado=recreado,
    )


def _preparar_enmienda(rutas: RutasProtocolo, nivel: NivelElegido | None) -> _Enmienda:
    lectura, registro, validacion = leer_y_validar(rutas)
    ultima = registro.ultima_version
    protocolo_rel = rutas.relativa(rutas.protocolo)

    def _admitido(hallazgo: Hallazgo) -> bool:
        # El P-E09 de "cambio sin enmienda" es lo que la enmienda resuelve; el de una
        # operación interrumpida, no.
        return (
            hallazgo.id_regla == "P-E09"
            and ultima is not None
            and lectura.hash != ultima.datos.hash_revisado
        )

    problemas = [str(h) for h in validacion.errores if not _admitido(h)]
    documento = lectura.documento
    if documento is None or not registro.integro:
        raise ErrorCicloDeVida(problemas)
    if ultima is None:
        raise ErrorCicloDeVida(
            problemas
            + [
                "el protocolo no está aprobado: un borrador se edita libremente y se aprueba "
                "con `agentresearch protocolo aprobar`"
            ]
        )

    try:
        anterior = decodificar_protocolo(rutas.resolver(ultima.datos.ruta_version).read_bytes())
    except ErrorLecturaProtocolo as error:
        raise ErrorCicloDeVida(
            [f"no se pudo leer la copia {ultima.datos.ruta_version}: {error}"]
        ) from None
    protocolo = documento.protocolo
    if protocolo.estado != "vigente":
        problemas.append(
            f"el estado de {protocolo_rel} es «{protocolo.estado}»; un protocolo aprobado no "
            "vuelve a borrador, y el estado no se edita a mano"
        )
    if protocolo.metadatos.version_protocolo != ultima.version:
        problemas.append(
            f"la versión de {protocolo_rel} ({protocolo.metadatos.version_protocolo}) no es la "
            f"registrada ({ultima.version}); la versión la asigna el paquete, no se edita a mano"
        )
    sin_cambios = lectura.hash == ultima.hash_protocolo
    if sin_cambios:
        problemas.append(
            f"no hay cambios que enmendar: {protocolo_rel} coincide con la versión "
            f"{ultima.version} registrada en {ultima.evento.id}"
        )
    problemas += _problemas_de_pendientes(registro)

    ya_activas = _claves_registradas(ultima)
    advertencias_nuevas = [
        a for a in validacion.advertencias if clave_advertencia(a) not in ya_activas
    ]
    cambios = diferencias_protocolo(anterior.protocolo, protocolo)
    nivel_efectivo: Nivel | None = nivel
    if not cambios:
        nivel_efectivo = "parche"
        # Sin ningún cambio basta «no hay cambios»: el nivel parche no aplica.
        if nivel is not None and not sin_cambios:
            problemas.append(
                "el cambio es solo de formato o comentarios: el nivel es parche y lo asigna el "
                "paquete, así que no se da --nivel"
            )
    propuesta = PropuestaEnmienda(
        ruta_protocolo=protocolo_rel,
        version_registrada=ultima.version,
        evento_registrado=ultima.evento.id,
        cambios=cambios,
        nivel=nivel_efectivo,
        version_siguiente=(
            siguiente_version(ultima.version, nivel_efectivo) if nivel_efectivo else None
        ),
        problemas=problemas,
        advertencias_nuevas=advertencias_nuevas,
    )
    return _Enmienda(rutas, lectura, validacion, documento, ultima, propuesta)


def _claves_registradas(version: VersionRegistrada) -> frozenset[ClaveAdvertencia]:
    """Advertencias activas en una versión registrada, según su evento."""
    return frozenset((a.id_regla, a.ubicacion) for a in version.datos.advertencias)


def _advertencia_registrada(
    advertencia: Hallazgo, justificada: tuple[str, OrigenJustificacion] | None
) -> AdvertenciaRegistrada:
    """Advertencia del evento de enmienda: las nuevas llevan su justificación."""
    return AdvertenciaRegistrada(
        id_regla=advertencia.id_regla,
        ubicacion=advertencia.ubicacion,
        mensaje=advertencia.mensaje,
        referencia=advertencia.referencia,
        nueva=justificada is not None,
        justificacion=justificada[0] if justificada is not None else None,
        origen=justificada[1] if justificada is not None else None,
    )


def _textos_de_enmienda(
    justificacion: str | None, efecto_esperado: str | None, archivo: Path | str | None
) -> tuple[str, str]:
    """Justificación y efecto esperado, del archivo o de las opciones (no de ambos)."""
    if archivo is not None:
        if justificacion is not None or efecto_esperado is not None:
            raise ErrorEntrada(
                ["use --archivo-enmienda o --justificacion y --efecto-esperado, pero no ambos"]
            )
        datos = validar_modelo(ArchivoEnmienda, leer_json(archivo), str(archivo))
        justificacion, efecto_esperado = datos.justificacion, datos.efecto_esperado
    errores = []
    if not (justificacion or "").strip():
        errores.append("falta la justificación de la enmienda (--justificacion)")
    if not (efecto_esperado or "").strip():
        errores.append("falta el efecto esperado de la enmienda (--efecto-esperado)")
    if errores:
        raise ErrorEntrada(errores)
    assert justificacion is not None and efecto_esperado is not None
    return justificacion.strip(), efecto_esperado.strip()


def _resumen_enmienda(
    enmienda: _Enmienda,
    hash_protocolo: str,
    enmendado_por: str,
    justificacion: str,
    efecto_esperado: str,
) -> str:
    propuesta = enmienda.propuesta
    lineas = [
        f"Enmienda del protocolo {propuesta.ruta_protocolo}",
        f"  versión: {propuesta.version_registrada} → {propuesta.version_siguiente} "
        f"(nivel {propuesta.nivel})",
        f"  hash de la versión registrada: {enmienda.ultima.hash_protocolo}",
        f"  hash del archivo revisado: {hash_leido(enmienda.lectura)}",
        f"  hash del protocolo enmendado: {hash_protocolo}",
        f"  enmendado por: {enmendado_por}",
        f"  justificación: {justificacion}",
        f"  efecto esperado: {efecto_esperado}",
    ]
    lineas += texto_de_cambios(propuesta.cambios)
    return "\n".join(lineas)


def texto_de_cambios(cambios: list[Cambio]) -> list[str]:
    """Líneas legibles del diff estructural."""
    if not cambios:
        return ["Cambios: ninguno de contenido (solo formato o comentarios)"]
    return [f"Cambios: {len(cambios)}"] + [f"  - {cambio}" for cambio in cambios]


# --- Piezas compartidas con la enmienda ---------------------------------------------


def leer_y_validar(
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


def hash_leido(lectura: LecturaProtocolo) -> str:
    assert lectura.hash is not None  # hay documento, así que se leyeron los bytes
    return lectura.hash


def problemas_de_persona(protocolo: Protocolo, id_persona: str, opcion: str) -> list[str]:
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


def exigir_terminal(terminal: Terminal) -> None:
    if not terminal.es_interactiva():
        raise ErrorCicloDeVida([MENSAJE_SIN_TERMINAL])


def confirmar_frase(terminal: Terminal, frase: str) -> None:
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
) -> tuple[EventoRegistro, Anclaje, bool]:
    """Escribe copia, evento, anclaje y protocolo, en ese orden (ADR-0008, punto 14).

    Antes de escribir, comprueba que el protocolo no cambió desde que se leyó
    (por ejemplo, mientras el investigador confirmaba). Devuelve el evento, el
    anclaje y si `anclaje.json` faltaba y se volvió a crear.
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
    recreado = falta_anclaje(rutas)
    registro = (
        RegistroEncadenado(rutas.eventos, reloj=reloj)
        if reloj is not None
        else RegistroEncadenado(rutas.eventos)
    )
    evento = registro.agregar(tipo, datos.model_dump(mode="json"))
    anclaje = escribir_anclaje(rutas)
    escribir_atomico(rutas.protocolo, contenido_nuevo)
    return evento, anclaje, recreado
