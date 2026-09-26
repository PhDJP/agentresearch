"""Validación del protocolo contra las reglas metodológicas P-E00 a P-E08 y P-A01 a P-A09.

Cada regla es una función determinista sobre el modelo ya cargado; no usa
heurísticas sobre el texto libre, salvo P-A07, que examina la forma de los
términos de búsqueda. Los hallazgos siguen el orden del catálogo de reglas y,
dentro de cada regla, el orden del documento.
"""

import math
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap

from agentresearch.protocolo.archivo import (
    DocumentoProtocolo,
    ErrorLecturaProtocolo,
    formatear_ubicacion,
    leer_protocolo,
    posicion_en_yaml,
)
from agentresearch.protocolo.modelo import VERSION_ESQUEMA, Protocolo
from agentresearch.protocolo.reglas import REGLAS, Severidad
from agentresearch.trazabilidad import hash_archivo

MINIMO_CONJUNTO_VALIDACION = 5
"""Artículos mínimos del conjunto de validación antes de advertir (P-A04)."""

Ruta = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class Hallazgo:
    """Un error o una advertencia de validación, con su regla, ubicación y referencia."""

    id_regla: str
    severidad: Severidad
    mensaje: str
    referencia: str
    ubicacion: str | None = None
    linea: int | None = None
    columna: int | None = None

    def __str__(self) -> str:
        donde = f" en {self.ubicacion}" if self.ubicacion else ""
        if self.linea is not None:
            donde += f" (línea {self.linea})"
        return (
            f"{self.severidad} {self.id_regla}{donde}: {self.mensaje}. "
            f"Referencia: {self.referencia}"
        )

    def como_dict(self) -> dict[str, Any]:
        return {
            "id_regla": self.id_regla,
            "severidad": self.severidad,
            "mensaje": self.mensaje,
            "referencia": self.referencia,
            "ubicacion": self.ubicacion,
            "linea": self.linea,
            "columna": self.columna,
        }


@dataclass(frozen=True, slots=True)
class ResultadoValidacion:
    """Resultado de validar un archivo de protocolo."""

    ruta: str
    hallazgos: list[Hallazgo]
    hash_archivo: str | None = None
    estado: str | None = None
    version_protocolo: str | None = None

    @property
    def errores(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad == "error"]

    @property
    def advertencias(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad == "advertencia"]

    @property
    def valido(self) -> bool:
        """Indica si no hay errores (las advertencias no impiden aprobar)."""
        return not self.errores

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta": self.ruta,
            "hash_archivo": self.hash_archivo,
            "version_agente": version("agentresearch"),
            "version_esquema": VERSION_ESQUEMA,
            "estado": self.estado,
            "version_protocolo": self.version_protocolo,
            "valido": self.valido,
            "errores": len(self.errores),
            "advertencias": len(self.advertencias),
            "hallazgos": [hallazgo.como_dict() for hallazgo in self.hallazgos],
        }


def validar_archivo(ruta: Path | str) -> ResultadoValidacion:
    """Lee y valida un archivo de protocolo. Nunca lanza por problemas del archivo."""
    ruta = Path(ruta)
    huella = hash_archivo(ruta) if ruta.is_file() else None
    try:
        documento = leer_protocolo(ruta)
    except ErrorLecturaProtocolo as error:
        regla = REGLAS["P-E00"]
        hallazgos = [
            Hallazgo(
                id_regla=regla.id,
                severidad=regla.severidad,
                mensaje=problema.mensaje,
                referencia=regla.referencia,
                ubicacion=problema.ubicacion,
                linea=problema.linea,
                columna=problema.columna,
            )
            for problema in error.problemas
        ]
        return ResultadoValidacion(ruta=str(ruta), hallazgos=hallazgos, hash_archivo=huella)
    return ResultadoValidacion(
        ruta=str(ruta),
        hallazgos=validar_documento(documento),
        hash_archivo=huella,
        estado=documento.protocolo.estado,
        version_protocolo=documento.protocolo.metadatos.version_protocolo,
    )


def validar_documento(documento: DocumentoProtocolo) -> list[Hallazgo]:
    """Valida un documento leído; los hallazgos llevan la línea y columna del YAML."""
    return [_ubicar(hallazgo, documento.datos) for hallazgo in _hallazgos(documento.protocolo)]


def validar_protocolo(protocolo: Protocolo) -> list[Hallazgo]:
    """Valida un protocolo (sin YAML de origen, los hallazgos no llevan línea)."""
    return [hallazgo for hallazgo, _ruta in _hallazgos(protocolo)]


# --- Infraestructura ---------------------------------------------------------

_Resultado = tuple[str, str, Ruta]
"""(ID de regla, mensaje, ruta en el protocolo)."""

_Comprobacion = Callable[[Protocolo], Iterable[_Resultado]]


def _hallazgos(protocolo: Protocolo) -> Iterator[tuple[Hallazgo, Ruta]]:
    for comprobacion in _COMPROBACIONES:
        for id_regla, mensaje, ruta in comprobacion(protocolo):
            regla = REGLAS[id_regla]
            hallazgo = Hallazgo(
                id_regla=regla.id,
                severidad=regla.severidad,
                mensaje=mensaje,
                referencia=regla.referencia,
                ubicacion=formatear_ubicacion(ruta) or None,
            )
            yield hallazgo, ruta


def _ubicar(par: tuple[Hallazgo, Ruta], datos: CommentedMap) -> Hallazgo:
    hallazgo, ruta = par
    linea, columna = posicion_en_yaml(datos, ruta)
    return replace(hallazgo, linea=linea, columna=columna)


def _vacio(texto: str) -> bool:
    return not texto.strip()


# --- Colecciones con ID --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ColeccionIds:
    prefijo: str
    ruta: Ruta
    ids: list[str]


def _colecciones(protocolo: Protocolo) -> list[_ColeccionIds]:
    return [
        _ColeccionIds("PI", ("preguntas",), [p.id for p in protocolo.preguntas]),
        _ColeccionIds(
            "CI", ("criterios", "inclusion"), [c.id for c in protocolo.criterios.inclusion]
        ),
        _ColeccionIds(
            "CE", ("criterios", "exclusion"), [c.id for c in protocolo.criterios.exclusion]
        ),
        _ColeccionIds("DE", ("extraccion", "items"), [i.id for i in protocolo.extraccion.items]),
        _ColeccionIds("F", ("extraccion", "facetas"), [f.id for f in protocolo.extraccion.facetas]),
        _ColeccionIds("B", ("busqueda", "bloques"), [b.id for b in protocolo.busqueda.bloques]),
    ]


def _datos_y_facetas(protocolo: Protocolo) -> set[str]:
    return {i.id for i in protocolo.extraccion.items} | {f.id for f in protocolo.extraccion.facetas}


# --- Errores -------------------------------------------------------------------


def _p_e01(protocolo: Protocolo) -> Iterator[_Resultado]:
    """IDs únicos y con el patrón de su tipo."""
    for coleccion in _colecciones(protocolo):
        patron = re.compile(rf"{coleccion.prefijo}[1-9][0-9]*")
        yield from _ids_con_patron(coleccion.ids, coleccion.ruta, patron, f"{coleccion.prefijo}1")

    for posicion, faceta in enumerate(protocolo.extraccion.facetas):
        ruta_categorias: Ruta = ("extraccion", "facetas", posicion, "categorias")
        patron = re.compile(rf"{re.escape(faceta.id)}\.[1-9][0-9]*")
        ids = [categoria.id for categoria in faceta.categorias]
        yield from _ids_con_patron(ids, ruta_categorias, patron, f"{faceta.id}.1")

    for ruta, ids in (
        (("fuentes",), [fuente.id for fuente in protocolo.fuentes]),
        (("seleccion", "revisores"), [revisor.id for revisor in protocolo.seleccion.revisores]),
    ):
        yield from _ids_repetidos(ids, ruta)


def _ids_con_patron(
    ids: list[str], ruta: Ruta, patron: re.Pattern[str], ejemplo: str
) -> Iterator[_Resultado]:
    for posicion, identificador in enumerate(ids):
        if not patron.fullmatch(identificador):
            yield (
                "P-E01",
                f"el ID {identificador!r} no sigue el patrón esperado (p. ej. {ejemplo})",
                (*ruta, posicion, "id"),
            )
    yield from _ids_repetidos(ids, ruta)


def _ids_repetidos(ids: list[str], ruta: Ruta) -> Iterator[_Resultado]:
    vistos: dict[str, int] = {}
    for posicion, identificador in enumerate(ids):
        if identificador in vistos:
            anterior = formatear_ubicacion((*ruta, vistos[identificador]))
            yield (
                "P-E01",
                f"el ID {identificador!r} está repetido (ya aparece en {anterior})",
                (*ruta, posicion, "id"),
            )
        else:
            vistos[identificador] = posicion


def _p_e02(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Toda referencia apunta a un ID existente del tipo correcto."""
    datos_y_facetas = _datos_y_facetas(protocolo)
    preguntas = {pregunta.id for pregunta in protocolo.preguntas}
    tipo_dato = "ningún dato de extracción (DE) ni faceta (F)"

    for i, pregunta in enumerate(protocolo.preguntas):
        for j, referencia in enumerate(pregunta.responde_con):
            if referencia not in datos_y_facetas:
                yield _referencia_rota(referencia, tipo_dato, ("preguntas", i, "responde_con", j))
        for j, cruce in enumerate(pregunta.derivada_de):
            for k, referencia in enumerate(cruce):
                if referencia not in datos_y_facetas:
                    ruta: Ruta = ("preguntas", i, "derivada_de", j, k)
                    yield _referencia_rota(referencia, tipo_dato, ruta)

    for i, item in enumerate(protocolo.extraccion.items):
        for j, referencia in enumerate(item.preguntas):
            if referencia not in preguntas:
                ruta = ("extraccion", "items", i, "preguntas", j)
                yield _referencia_rota(referencia, "ninguna pregunta (PI)", ruta)

    for i, cruce in enumerate(protocolo.analisis.cruces):
        for j, referencia in enumerate(cruce):
            if referencia not in datos_y_facetas:
                yield _referencia_rota(referencia, tipo_dato, ("analisis", "cruces", i, j))


def _referencia_rota(referencia: str, tipo: str, ruta: Ruta) -> _Resultado:
    return ("P-E02", f"{referencia!r} no es el ID de {tipo} del protocolo", ruta)


def _p_e03(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Preguntas descriptivas con datos que las responden; analíticas con cruces."""
    for i, pregunta in enumerate(protocolo.preguntas):
        if pregunta.tipo == "descriptiva" and not pregunta.responde_con:
            yield (
                "P-E03",
                f"la pregunta descriptiva {pregunta.id} no declara qué datos o facetas "
                "la responden (responde_con)",
                ("preguntas", i),
            )
        if pregunta.tipo == "analitica" and not pregunta.derivada_de:
            yield (
                "P-E03",
                f"la pregunta analítica {pregunta.id} no declara de qué cruces se deriva "
                "(derivada_de)",
                ("preguntas", i),
            )


def _p_e04(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Población y concepto con descripción; bloques de búsqueda con términos."""
    pcc = protocolo.marco.pcc
    for nombre, texto, componente in (
        ("poblacion", "de la población", pcc.poblacion),
        ("concepto", "del concepto", pcc.concepto),
    ):
        if _vacio(componente.descripcion):
            yield (
                "P-E04",
                f"la descripción {texto} está vacía",
                ("marco", "pcc", nombre, "descripcion"),
            )
    if not protocolo.busqueda.bloques:
        yield ("P-E04", "no hay ningún bloque de búsqueda", ("busqueda", "bloques"))
    for i, bloque in enumerate(protocolo.busqueda.bloques):
        if all(_vacio(termino) for termino in bloque.terminos):
            yield (
                "P-E04",
                f"el bloque {bloque.id} no tiene ningún término",
                ("busqueda", "bloques", i, "terminos"),
            )


def _p_e05(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Cada criterio declara su fase."""
    for lista in ("inclusion", "exclusion"):
        for i, criterio in enumerate(getattr(protocolo.criterios, lista)):
            if criterio.fase is None:
                yield (
                    "P-E05",
                    f"el criterio {criterio.id} no declara su fase "
                    "(titulo_resumen, texto_completo o ambas)",
                    ("criterios", lista, i),
                )


def _p_e06(protocolo: Protocolo) -> Iterator[_Resultado]:
    """La regla de combinación hace avanzar A y excluye F."""
    avanzan = protocolo.seleccion.regla_combinacion.avanzan
    ruta: Ruta = ("seleccion", "regla_combinacion", "avanzan")
    if "A" not in avanzan:
        yield (
            "P-E06",
            "la regla de combinación no hace avanzar los registros que ambos revisores "
            "incluyen (A)",
            ruta,
        )
    if "F" in avanzan:
        yield (
            "P-E06",
            "la regla de combinación hace avanzar los registros que ambos revisores excluyen (F)",
            ruta,
        )


def _p_e07(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Al menos un revisor humano."""
    if not any(revisor.tipo == "humano" for revisor in protocolo.seleccion.revisores):
        yield (
            "P-E07",
            "no hay ningún revisor humano; el LLM propone, pero decide el investigador",
            ("seleccion", "revisores"),
        )


def _p_e08(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Umbral kappa entre 0 y 1; lote del LLM positivo."""
    kappa = protocolo.seleccion.piloto.umbral_kappa
    if not (math.isfinite(kappa) and 0 <= kappa <= 1):
        yield (
            "P-E08",
            f"el umbral de kappa debe estar entre 0 y 1 (valor: {kappa})",
            ("seleccion", "piloto", "umbral_kappa"),
        )
    lote = protocolo.seleccion.tamano_lote_llm
    if lote <= 0:
        yield (
            "P-E08",
            f"el tamaño del lote del LLM debe ser un entero positivo (valor: {lote})",
            ("seleccion", "tamano_lote_llm"),
        )


# --- Advertencias --------------------------------------------------------------


def _p_a01(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Criterios que exigen evaluación empírica (tipo d de Petersen et al., 2015)."""
    for lista in ("inclusion", "exclusion"):
        for i, criterio in enumerate(getattr(protocolo.criterios, lista)):
            if criterio.tipo == "evaluacion_empirica":
                yield (
                    "P-A01",
                    f"el criterio {criterio.id} exige evaluación empírica; en un mapeo puede "
                    "dejar fuera tendencias recientes que aún no se han evaluado",
                    ("criterios", lista, i, "tipo"),
                )


def _p_a02(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Contexto restrictivo o usado como bloque AND."""
    contexto = protocolo.marco.pcc.contexto
    if contexto.restrictivo:
        yield (
            "P-A02",
            "el contexto está marcado como restrictivo; puede dejar fuera artículos del área",
            ("marco", "pcc", "contexto", "restrictivo"),
        )
    terminos_contexto = {_normalizar_termino(t) for t in contexto.terminos if not _vacio(t)}
    for i, bloque in enumerate(protocolo.busqueda.bloques):
        if bloque.componente == "contexto":
            yield (
                "P-A02",
                f"el bloque {bloque.id} es de contexto y se combina con AND; puede dejar fuera "
                "artículos del área",
                ("busqueda", "bloques", i, "componente"),
            )
            continue
        for j, termino in enumerate(bloque.terminos):
            if _normalizar_termino(termino) in terminos_contexto:
                yield (
                    "P-A02",
                    f"el término {termino!r} del bloque {bloque.id} es un término de contexto "
                    "y restringe la búsqueda con AND",
                    ("busqueda", "bloques", i, "terminos", j),
                )


def _normalizar_termino(termino: str) -> str:
    return termino.strip().strip("\"'").strip().casefold()


def _p_a03(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Menos de dos estrategias de identificación activas."""
    estrategias = protocolo.estrategias
    activas = [
        nombre
        for nombre, activa in (
            ("bases_de_datos", estrategias.bases_de_datos.activa),
            ("bola_de_nieve", estrategias.bola_de_nieve.activa),
            ("busqueda_manual", estrategias.busqueda_manual.activa),
        )
        if activa
    ]
    if len(activas) < 2:
        situacion = (
            f"solo está activa la estrategia {activas[0]}"
            if activas
            else "no hay ninguna estrategia de identificación activa"
        )
        yield (
            "P-A03",
            f"{situacion}; combinar estrategias mejora la cobertura",
            ("estrategias",),
        )


def _p_a04(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Conjunto de validación inactivo o pequeño."""
    conjunto = protocolo.estrategias.conjunto_validacion
    ruta: Ruta = ("estrategias", "conjunto_validacion")
    if not conjunto.activo:
        yield (
            "P-A04",
            "el conjunto de validación está inactivo; sin él no se puede medir la "
            "sensibilidad de la búsqueda",
            (*ruta, "activo"),
        )
        return
    completos = [a for a in conjunto.articulos if not (_vacio(a.doi) and _vacio(a.titulo))]
    if len(completos) < MINIMO_CONJUNTO_VALIDACION:
        yield (
            "P-A04",
            f"el conjunto de validación tiene {len(completos)} artículos con DOI o título "
            f"(se recomiendan al menos {MINIMO_CONJUNTO_VALIDACION})",
            (*ruta, "articulos"),
        )


def _p_a05(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Periodo o idiomas restringidos sin justificación."""
    busqueda = protocolo.busqueda
    periodo = busqueda.periodo
    if (periodo.desde is not None or periodo.hasta is not None) and _vacio(periodo.justificacion):
        yield (
            "P-A05",
            "el periodo está restringido sin justificación",
            ("busqueda", "periodo", "justificacion"),
        )
    if busqueda.idiomas.valores and _vacio(busqueda.idiomas.justificacion):
        yield (
            "P-A05",
            "los idiomas están restringidos sin justificación",
            ("busqueda", "idiomas", "justificacion"),
        )


def _p_a06(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Categorías de faceta sin definición, regla o ejemplos."""
    for i, faceta in enumerate(protocolo.extraccion.facetas):
        for j, categoria in enumerate(faceta.categorias):
            faltantes = []
            if _vacio(categoria.definicion):
                faltantes.append("definición")
            if _vacio(categoria.regla):
                faltantes.append("regla de asignación")
            if all(_vacio(ejemplo) for ejemplo in categoria.ejemplos):
                faltantes.append("ejemplos")
            if faltantes:
                yield (
                    "P-A06",
                    f"a la categoría {categoria.id} le falta: {', '.join(faltantes)}",
                    ("extraccion", "facetas", i, "categorias", j),
                )


def _p_a07(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Acrónimos cortos sueltos en un bloque de búsqueda."""
    for i, bloque in enumerate(protocolo.busqueda.bloques):
        for j, termino in enumerate(bloque.terminos):
            if es_acronimo_corto(termino):
                yield (
                    "P-A07",
                    f"el término {termino!r} del bloque {bloque.id} es un acrónimo corto suelto; "
                    "puede recuperar artículos de otros temas con la misma sigla",
                    ("busqueda", "bloques", i, "terminos", j),
                )


def es_acronimo_corto(termino: str) -> bool:
    """Indica si el término es una sigla de 2 a 4 caracteres en mayúsculas, con o sin comillas.

    Admite un truncamiento final (`*`) y dígitos, pero exige al menos dos letras:
    CBD, "CBD", PEF* y CO2 son siglas; 2020 y A1 no.
    """
    nucleo = termino.strip()
    if len(nucleo) >= 2 and nucleo[0] == nucleo[-1] and nucleo[0] in "\"'":
        nucleo = nucleo[1:-1].strip()
    nucleo = nucleo.removesuffix("*")
    letras = sum(caracter.isalpha() for caracter in nucleo)
    return 2 <= len(nucleo) <= 4 and nucleo.isalnum() and nucleo == nucleo.upper() and letras >= 2


def _p_a08(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Un solo revisor humano (sin ninguno, ya salta P-E07)."""
    humanos = [r for r in protocolo.seleccion.revisores if r.tipo == "humano"]
    if len(humanos) == 1:
        yield (
            "P-A08",
            f"solo hay un revisor humano ({humanos[0].id}); sin un segundo revisor humano "
            "no se puede medir la concordancia entre personas en el piloto de cribado",
            ("seleccion", "revisores"),
        )


def _p_a09(protocolo: Protocolo) -> Iterator[_Resultado]:
    """Piloto de cribado sin tamaño: la concordancia se mide antes del cribado completo."""
    tamano = protocolo.seleccion.piloto.tamano
    if tamano <= 0:
        yield (
            "P-A09",
            f"el piloto de cribado no tiene tamaño definido (valor: {tamano}); la "
            "concordancia entre revisores se mide en un piloto antes del cribado completo",
            ("seleccion", "piloto", "tamano"),
        )


_COMPROBACIONES: tuple[_Comprobacion, ...] = (
    _p_e01,
    _p_e02,
    _p_e03,
    _p_e04,
    _p_e05,
    _p_e06,
    _p_e07,
    _p_e08,
    _p_a01,
    _p_a02,
    _p_a03,
    _p_a04,
    _p_a05,
    _p_a06,
    _p_a07,
    _p_a08,
    _p_a09,
)
