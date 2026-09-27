"""Esquemas de los eventos del registro del protocolo (ADR-0008, punto 7; ADR-0007).

Cada evento de `protocolo/eventos.jsonl` guarda en `datos` un objeto con uno de
estos esquemas. Se validan con pydantic estricto al leer el registro, para
que un evento mal formado se reporte (regla P-E10) en vez de interpretarse a
medias.

Los esquemas validan la forma. Las reglas de contenido de una decisión (número
de opciones, revisor humano declarado, modelo exacto, etc.) están en
`agentresearch.protocolo.decisiones`, para reportarlas con mensajes claros.
"""

from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from agentresearch.protocolo.estudio import es_ruta_relativa_valida

TIPO_APROBADO = "protocolo_aprobado"
TIPO_ENMENDADO = "protocolo_enmendado"
TIPO_DECISION_PROPUESTA = "decision_propuesta"
TIPO_DECISION_CONFIRMADA = "decision_confirmada"
TIPO_ESTUDIO_CREADO = "estudio_creado"

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
    """Advertencia activa al enmendar (ADR-0008, punto 10).

    `nueva` indica que no estaba activa en la versión registrada anterior. Solo
    las nuevas llevan justificación y origen; las que ya existían se registran
    sin ellos, porque se justificaron (o se registraron) antes.
    """

    id_regla: str
    ubicacion: str | None
    mensaje: str
    referencia: str
    nueva: bool
    justificacion: TextoNoVacio | None = None
    origen: Literal["archivo", "terminal"] | None = None

    @model_validator(mode="after")
    def _justificada_si_es_nueva(self) -> "AdvertenciaRegistrada":
        justificada = self.justificacion is not None and self.origen is not None
        sin_justificar = self.justificacion is None and self.origen is None
        if self.nueva and not justificada:
            raise ValueError("una advertencia nueva lleva justificacion y origen")
        if not self.nueva and not sin_justificar:
            raise ValueError("una advertencia que ya estaba activa no lleva justificacion")
        return self

    @model_serializer(mode="wrap")
    def _sin_justificacion_vacia(self, siguiente: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Omite `justificacion` y `origen` en las advertencias que ya estaban activas."""
        datos: dict[str, Any] = siguiente(self)
        if not self.nueva:
            datos.pop("justificacion", None)
            datos.pop("origen", None)
        return datos


class CambioRegistrado(ModeloEvento):
    """Un cambio del diff estructural (ADR-0008, punto 13)."""

    ruta: str
    operacion: Literal["agregado", "eliminado", "modificado", "reordenado"]
    antes: Any
    despues: Any
    agregados: list[Any] | None = None
    eliminados: list[Any] | None = None

    @model_serializer(mode="wrap")
    def _sin_listas_vacias_de_escalares(
        self, siguiente: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Omite `agregados` y `eliminados` cuando el cambio no es de una lista de escalares."""
        datos: dict[str, Any] = siguiente(self)
        if self.agregados is None and self.eliminados is None:
            datos.pop("agregados", None)
            datos.pop("eliminados", None)
        return datos


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


# --- Creación del estudio (ADR-0007) ---------------------------------------------


class ArchivoRegistrado(ModeloEvento):
    """Un archivo del estudio y su hash, en el momento de registrarlo."""

    ruta: RutaRelativa
    hash: HashSha256


class DatosEstudioCreado(ModeloEvento):
    """Datos del evento `estudio_creado`, el primero del registro.

    `instrucciones` son los archivos que gobiernan al agente en el estudio
    (`CLAUDE.md`, `.claude/settings.json` y las *skills*); `validar` e
    `historial` avisan si cambian. `insumos` son los archivos que el
    investigador aportó con `--contexto`.
    """

    nombre: TextoNoVacio
    titulo: TextoNoVacio
    modelo: TextoNoVacio
    fuente_agente: TextoNoVacio
    archivos: list[ArchivoRegistrado]
    instrucciones: list[ArchivoRegistrado]
    insumos: list[ArchivoRegistrado]


# --- Anclaje ----------------------------------------------------------------------


class ArchivoAnclaje(ModeloEvento):
    """Contenido de `protocolo/anclaje.json` (ADR-0008, punto 21)."""

    registro: RutaRelativa
    numero_eventos: Annotated[int, Field(ge=0)]
    hash_ultimo: str
