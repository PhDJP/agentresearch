"""Esquemas de los eventos del ciclo de vida del protocolo (ADR-0008, punto 7).

Cada evento de `protocolo/eventos.jsonl` guarda en `datos` un objeto con uno de
estos esquemas. Se validan con pydantic estricto al leer el registro, para
que un evento mal formado se reporte (regla P-E10) en vez de interpretarse a
medias.

Los esquemas validan la forma. Las reglas de contenido de una decisión (número
de opciones, revisor humano declarado, modelo exacto, etc.) están en
`agentresearch.protocolo.decisiones`, para reportarlas con mensajes claros.
"""

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from agentresearch.protocolo.estudio import es_ruta_relativa_valida

TIPO_APROBADO = "protocolo_aprobado"
TIPO_ENMENDADO = "protocolo_enmendado"
TIPO_DECISION_PROPUESTA = "decision_propuesta"
TIPO_DECISION_CONFIRMADA = "decision_confirmada"

Nivel = Literal["mayor", "menor", "parche"]
EstadoProtocolo = Literal["borrador", "vigente"]


def _ruta_relativa(texto: str) -> str:
    if not es_ruta_relativa_valida(texto):
        raise ValueError("debe ser una ruta relativa al estudio, con '/' y sin '..'")
    return texto


HashSha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
VersionProtocolo = Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
RutaRelativa = Annotated[str, AfterValidator(_ruta_relativa)]
IdEvento = Annotated[str, Field(pattern=r"^evt-\d{6,}$")]
TextoNoVacio = Annotated[str, Field(min_length=1)]


class ModeloEvento(BaseModel):
    """Base de los esquemas de eventos y de los archivos de entrada."""

    model_config = ConfigDict(extra="forbid", strict=True)


class PersonaHumana(ModeloEvento):
    """Quién aprobó, enmendó o confirmó: siempre un revisor humano declarado."""

    tipo: Literal["humano"]
    id: TextoNoVacio


class AdvertenciaJustificada(ModeloEvento):
    """Advertencia activa al aprobar, con la justificación del investigador (ADR-0008, punto 10)."""

    id_regla: str
    ubicacion: str | None
    mensaje: str
    referencia: str
    justificacion: TextoNoVacio
    origen: Literal["archivo", "terminal"]


class AdvertenciaRegistrada(ModeloEvento):
    """Advertencia activa al enmendar (no se exige justificarla)."""

    id_regla: str
    ubicacion: str | None
    mensaje: str
    referencia: str


class CambioRegistrado(ModeloEvento):
    """Un cambio del diff estructural (ADR-0008, punto 13)."""

    ruta: str
    operacion: Literal["agregado", "eliminado", "modificado", "reordenado"]
    antes: Any
    despues: Any
    agregados: list[Any] | None = None
    eliminados: list[Any] | None = None


class DatosAprobado(ModeloEvento):
    """Datos del evento `protocolo_aprobado`."""

    version_anterior: VersionProtocolo
    version_protocolo: VersionProtocolo
    hash_revisado: HashSha256
    hash_protocolo: HashSha256
    ruta_protocolo: RutaRelativa
    ruta_version: RutaRelativa
    aprobado_por: PersonaHumana
    advertencias: list[AdvertenciaJustificada]


class DatosEnmendado(ModeloEvento):
    """Datos del evento `protocolo_enmendado`."""

    version_anterior: VersionProtocolo
    version_protocolo: VersionProtocolo
    nivel: Nivel
    hash_protocolo_anterior: HashSha256
    hash_revisado: HashSha256
    hash_protocolo: HashSha256
    ruta_protocolo: RutaRelativa
    ruta_version: RutaRelativa
    justificacion: TextoNoVacio
    efecto_esperado: TextoNoVacio
    enmendado_por: PersonaHumana
    cambios: list[CambioRegistrado]
    solo_formato: bool
    advertencias: list[AdvertenciaRegistrada]


# --- Decisiones del protocolo ---------------------------------------------------


class OpcionDecision(ModeloEvento):
    id: str
    descripcion: str
    pros: list[str]
    contras: list[str]
    referencias: list[str]


class Proponente(ModeloEvento):
    """Quién propuso las opciones: un humano (con `id`) o un LLM (con `modelo` exacto)."""

    tipo: Literal["humano", "llm"]
    id: str = ""
    modelo: str = ""


class Decisor(ModeloEvento):
    """Quién eligió la opción. Debe ser un humano; el tipo `llm` se acepta aquí para
    rechazarlo con un mensaje claro (CLAUDE.md, regla 1)."""

    tipo: Literal["humano", "llm"]
    id: str


class Decision(ModeloEvento):
    """Una decisión del protocolo, con sus opciones y la elegida (CLAUDE.md, regla 9)."""

    id_decision: str
    tema: str
    pregunta: str
    opciones: list[OpcionDecision]
    elegida: str
    justificacion: str
    propuesto_por: Proponente
    decidido_por: Decisor
    reemplaza: str | None = None


class DatosDecisionPropuesta(ModeloEvento):
    """Datos del evento `decision_propuesta`."""

    decision: Decision
    version_protocolo: VersionProtocolo
    estado_protocolo: EstadoProtocolo
    hash_protocolo: HashSha256


class DatosDecisionConfirmada(ModeloEvento):
    """Datos del evento `decision_confirmada`."""

    id_decision: TextoNoVacio
    evento_propuesta: IdEvento
    hash_evento_propuesta: HashSha256
    confirmado_por: PersonaHumana


# --- Anclaje ----------------------------------------------------------------------


class ArchivoAnclaje(ModeloEvento):
    """Contenido de `protocolo/anclaje.json` (ADR-0008, punto 21)."""

    registro: RutaRelativa
    numero_eventos: Annotated[int, Field(ge=0)]
    hash_ultimo: str
