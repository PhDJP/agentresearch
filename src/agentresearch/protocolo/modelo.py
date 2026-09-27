"""Modelo pydantic del protocolo de un estudio de mapeo (versión de esquema 1).

El esquema valida la forma: claves, tipos y valores permitidos. No exige
contenido, porque un protocolo en borrador está incompleto por naturaleza; las
reglas de contenido (P-E01 a P-E08 y P-A01 a P-A09) viven en
`agentresearch.protocolo.validacion` y se aplican sobre el modelo ya cargado.

Los campos que vigila una regla de contenido son opcionales o tienen un valor
vacío por defecto, para que su ausencia se reporte con el ID de la regla y no
como un error de esquema.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

VERSION_ESQUEMA = 1

Cruce = Annotated[list[str], Field(min_length=2)]
"""Combinación de dos o más IDs de faceta (`F`) o de dato de extracción (`DE`)."""

LetraRegla = Literal["A", "B", "C", "D", "E", "F"]
"""Celdas de la tabla de decisión de dos revisores (Petersen et al., 2015, tabla 6)."""

TipoCriterio = Literal[
    "tema",
    "lugar_publicacion",
    "periodo",
    "evaluacion_empirica",
    "idioma",
    "tipo_documento",
    "otro",
]
"""Tipos de criterio (a)-(e) de Petersen et al. (2015, §5.1.2), más tipo de documento y otro."""

FaseCriterio = Literal["titulo_resumen", "texto_completo", "ambas"]

ComponenteBloque = Literal["poblacion", "concepto", "contexto", "otro"]


class ModeloProtocolo(BaseModel):
    """Base de todos los modelos del protocolo.

    `extra="forbid"` rechaza claves desconocidas, para que una clave mal escrita
    no se ignore en silencio. `strict=True` evita conversiones implícitas (por
    ejemplo, el texto "25" no se acepta como el entero 25).
    """

    model_config = ConfigDict(extra="forbid", strict=True)


class Autor(ModeloProtocolo):
    nombre: str
    orcid: str = ""
    rol: str = ""


class RegistroProtocolo(ModeloProtocolo):
    """Registro público del protocolo (PRISMA-ScR, ítem 5). Opcional."""

    plataforma: str = ""
    identificador: str = ""
    url: str = ""


class Metadatos(ModeloProtocolo):
    titulo: str
    version_protocolo: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    autores: list[Autor]
    registro: RegistroProtocolo = RegistroProtocolo()
    financiacion: str = ""


class Pregunta(ModeloProtocolo):
    """Pregunta de investigación (PRISMA-ScR, ítem 4)."""

    id: str
    texto: str
    tipo: Literal["descriptiva", "analitica"]
    responde_con: list[str] = []
    derivada_de: list[Cruce] = []


class ComponentePcc(ModeloProtocolo):
    descripcion: str
    terminos: list[str] = []


class ComponenteContexto(ComponentePcc):
    restrictivo: bool = False


class Pcc(ModeloProtocolo):
    """Marco PCC (Población, Concepto, Contexto) del JBI."""

    poblacion: ComponentePcc
    concepto: ComponentePcc
    contexto: ComponenteContexto


class EquivalenciaPicoc(ModeloProtocolo):
    """Equivalencia con PICOC de Kitchenham (ADR-0002)."""

    population: str = ""
    intervention: str = ""
    comparison: str = ""
    outcome: str = ""
    context: str = ""


class Marco(ModeloProtocolo):
    pcc: Pcc
    equivalencia_picoc: EquivalenciaPicoc


class Fuente(ModeloProtocolo):
    """Fuente de información (PRISMA-ScR, ítem 7)."""

    id: str
    tipo: Literal["api", "exportacion"]
    cobertura: str = ""
    limites: str = ""


class EstrategiaBasesDeDatos(ModeloProtocolo):
    activa: bool


class EstrategiaBolaDeNieve(ModeloProtocolo):
    activa: bool
    direcciones: list[Literal["atras", "adelante"]] = []


class EstrategiaBusquedaManual(ModeloProtocolo):
    activa: bool
    fuentes: list[str] = []


class ArticuloValidacion(ModeloProtocolo):
    doi: str = ""
    titulo: str = ""
    como_se_conoce: str = ""


class ConjuntoValidacion(ModeloProtocolo):
    activo: bool
    articulos: list[ArticuloValidacion] = []


class CriterioParada(ModeloProtocolo):
    """Criterio de parada de la búsqueda (Petticrew y Roberts, en Petersen et al., 2015).

    `valor` es el número de artículos nuevos incluidos (umbral_nuevos) o de
    horas (presupuesto_tiempo).
    """

    tipo: Literal["umbral_nuevos", "presupuesto_tiempo"]
    valor: int
    justificacion: str = ""


class Estrategias(ModeloProtocolo):
    bases_de_datos: EstrategiaBasesDeDatos
    bola_de_nieve: EstrategiaBolaDeNieve
    busqueda_manual: EstrategiaBusquedaManual
    conjunto_validacion: ConjuntoValidacion
    criterio_parada: CriterioParada


class Bloque(ModeloProtocolo):
    """Bloque de búsqueda: OR entre sus términos, AND con los demás bloques."""

    id: str
    nombre: str
    componente: ComponenteBloque
    terminos: list[str] = []
    variantes: dict[str, list[str]] = {}
    """Variantes de un término truncado, para las fuentes que no admiten su truncamiento.

    Las escribe el investigador; el paquete nunca las inventa (ADR-0009, punto 3).
    """


class Periodo(ModeloProtocolo):
    """Años de publicación, ambos inclusive. `null` significa sin límite."""

    desde: int | None = None
    hasta: int | None = None
    justificacion: str = ""


class Idiomas(ModeloProtocolo):
    """Idiomas admitidos. Una lista vacía significa sin restricción."""

    valores: list[str] = []
    justificacion: str = ""


class Busqueda(ModeloProtocolo):
    """Estrategia de búsqueda (PRISMA-ScR, ítem 8)."""

    bloques: list[Bloque]
    periodo: Periodo
    idiomas: Idiomas
    tipos_documento: list[str] = []


class Criterio(ModeloProtocolo):
    """Criterio de inclusión o exclusión (PRISMA-ScR, ítem 6)."""

    id: str
    texto: str
    fase: FaseCriterio | None = None
    tipo: TipoCriterio
    ejemplos_si: list[str] = []
    ejemplos_no: list[str] = []


class Criterios(ModeloProtocolo):
    inclusion: list[Criterio]
    exclusion: list[Criterio]


class Revisor(ModeloProtocolo):
    id: str
    tipo: Literal["humano", "llm"]


class ReglaCombinacion(ModeloProtocolo):
    """Celdas de la tabla de decisión cuyos registros avanzan a la fase siguiente."""

    avanzan: list[LetraRegla]


class Piloto(ModeloProtocolo):
    tamano: int
    umbral_kappa: float


class Seleccion(ModeloProtocolo):
    """Proceso de selección (PRISMA-ScR, ítem 9)."""

    revisores: list[Revisor]
    regla_combinacion: ReglaCombinacion
    piloto: Piloto
    tamano_lote_llm: int


class ItemExtraccion(ModeloProtocolo):
    """Dato del formulario de extracción (PRISMA-ScR, ítems 10 y 11)."""

    id: str
    nombre: str
    descripcion: str = ""
    tipo: Literal["texto", "numero", "categoria", "booleano", "fecha"]
    categorias: list[str] = []
    preguntas: list[str] = []


class CategoriaFaceta(ModeloProtocolo):
    """Categoría de una faceta, con definición, regla y ejemplos (Wohlin et al., 2013)."""

    id: str
    nombre: str
    definicion: str = ""
    regla: str = ""
    ejemplos: list[str] = []


class Faceta(ModeloProtocolo):
    id: str
    nombre: str
    origen: Literal["existente", "emergente"]
    multiple: bool
    categorias: list[CategoriaFaceta] = []


class Extraccion(ModeloProtocolo):
    items: list[ItemExtraccion]
    facetas: list[Faceta]


class Calidad(ModeloProtocolo):
    """Evaluación de calidad, opcional (PRISMA-ScR, ítem 12)."""

    activa: bool
    preguntas: list[str] = []


class Analisis(ModeloProtocolo):
    """Plan de síntesis (PRISMA-ScR, ítem 13)."""

    plan: str = ""
    cruces: list[Cruce] = []


class Protocolo(ModeloProtocolo):
    """Protocolo completo de un estudio de mapeo, versión de esquema 1."""

    version_esquema: Literal[1]
    estado: Literal["borrador", "vigente"]
    metadatos: Metadatos
    justificacion: str
    objetivos: str
    pregunta_general: str
    preguntas: list[Pregunta]
    marco: Marco
    fuentes: list[Fuente]
    estrategias: Estrategias
    busqueda: Busqueda
    criterios: Criterios
    seleccion: Seleccion
    extraccion: Extraccion
    calidad: Calidad
    analisis: Analisis
