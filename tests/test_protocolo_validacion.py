"""Pruebas de las reglas de validación del protocolo (P-E00 a P-E08, P-A01 a P-A09)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo import (
    REGLAS,
    Protocolo,
    cargar_protocolo,
    texto_plantilla,
    validar_archivo,
    validar_documento,
    validar_protocolo,
)
from agentresearch.protocolo.validacion import es_acronimo_corto
from agentresearch.trazabilidad import hash_archivo

RUTA_PROTOCOLO_SINTETICO = Path(__file__).parent / "datos" / "protocolo_sintetico.yaml"

Mutacion = Callable[[dict[str, Any]], None]


def _ids_de_regla(datos: dict[str, Any]) -> list[str]:
    return [hallazgo.id_regla for hallazgo in validar_protocolo(Protocolo.model_validate(datos))]


# --- Protocolo válido y plantilla ----------------------------------------------


def test_el_protocolo_sintetico_no_tiene_errores_ni_advertencias(
    datos_sinteticos: dict[str, Any],
) -> None:
    assert _ids_de_regla(datos_sinteticos) == []


def test_la_plantilla_solo_tiene_los_hallazgos_de_un_borrador_vacio() -> None:
    hallazgos = validar_documento(cargar_protocolo(texto_plantilla()))

    assert {hallazgo.id_regla for hallazgo in hallazgos} == {
        "P-E04",
        "P-A04",
        "P-A06",
        "P-A08",
        "P-A09",
    }


# --- Una mutación por caso -----------------------------------------------------


def _pregunta(datos: dict[str, Any], id_pregunta: str) -> dict[str, Any]:
    preguntas: list[dict[str, Any]] = datos["preguntas"]
    [pregunta] = [p for p in preguntas if p["id"] == id_pregunta]
    return pregunta


def _asignar(*ruta: str | int, valor: object) -> Mutacion:
    def mutar(datos: dict[str, Any]) -> None:
        contenedor: Any = datos
        for clave in ruta[:-1]:
            contenedor = contenedor[clave]
        contenedor[ruta[-1]] = valor

    return mutar


def _borrar(*ruta: str | int) -> Mutacion:
    def mutar(datos: dict[str, Any]) -> None:
        contenedor: Any = datos
        for clave in ruta[:-1]:
            contenedor = contenedor[clave]
        del contenedor[ruta[-1]]

    return mutar


def _agregar_termino(indice_bloque: int, termino: str) -> Mutacion:
    def mutar(datos: dict[str, Any]) -> None:
        datos["busqueda"]["bloques"][indice_bloque]["terminos"].append(termino)

    return mutar


def _quitar_revisor(id_revisor: str) -> Mutacion:
    def mutar(datos: dict[str, Any]) -> None:
        revisores = datos["seleccion"]["revisores"]
        datos["seleccion"]["revisores"] = [r for r in revisores if r["id"] != id_revisor]

    return mutar


def _sin_estrategias(datos: dict[str, Any]) -> None:
    for nombre in ("bases_de_datos", "bola_de_nieve", "busqueda_manual"):
        datos["estrategias"][nombre]["activa"] = False


def _articulo_en_blanco(datos: dict[str, Any]) -> None:
    datos["estrategias"]["conjunto_validacion"]["articulos"][4] = {"doi": " ", "titulo": ""}


def _responde_con_inexistente(datos: dict[str, Any]) -> None:
    _pregunta(datos, "PI1")["responde_con"].append("DE9")


def _derivada_de_una_pregunta(datos: dict[str, Any]) -> None:
    _pregunta(datos, "PI3")["derivada_de"] = [["F1", "PI1"]]


def _descriptiva_sin_datos(datos: dict[str, Any]) -> None:
    _pregunta(datos, "PI2")["responde_con"] = []


def _analitica_sin_cruces(datos: dict[str, Any]) -> None:
    del _pregunta(datos, "PI3")["derivada_de"]


CASOS: list[tuple[str, Mutacion, list[str]]] = [
    # P-E01: IDs únicos y con patrón
    ("pregunta sin prefijo PI", _asignar("preguntas", 1, "id", valor="Q2"), ["P-E01"]),
    ("criterio repetido", _asignar("criterios", "exclusion", 1, "id", valor="CE1"), ["P-E01"]),
    ("bloque con cero inicial", _asignar("busqueda", "bloques", 0, "id", valor="B01"), ["P-E01"]),
    (
        "categoría con prefijo de otra faceta",
        _asignar("extraccion", "facetas", 1, "categorias", 0, "id", valor="F1.3"),
        ["P-E01"],
    ),
    ("fuente repetida", _asignar("fuentes", 1, "id", valor="openalex"), ["P-E01"]),
    (
        "revisor repetido",
        _asignar("seleccion", "revisores", 1, "id", valor="investigador-1"),
        ["P-E01"],
    ),
    # P-E02: referencias a IDs existentes
    ("responde_con inexistente", _responde_con_inexistente, ["P-E02"]),
    ("derivada_de apunta a una pregunta", _derivada_de_una_pregunta, ["P-E02"]),
    (
        "dato que cita una pregunta inexistente",
        _asignar("extraccion", "items", 0, "preguntas", valor=["PI9"]),
        ["P-E02"],
    ),
    (
        "cruce con faceta inexistente",
        _asignar("analisis", "cruces", valor=[["F1", "F7"]]),
        ["P-E02"],
    ),
    # P-E03: preguntas vinculadas a datos o cruces
    ("pregunta descriptiva sin datos", _descriptiva_sin_datos, ["P-E03"]),
    ("pregunta analítica sin cruces", _analitica_sin_cruces, ["P-E03"]),
    # P-E04: población, concepto y bloques
    (
        "población en blanco",
        _asignar("marco", "pcc", "poblacion", "descripcion", valor="   "),
        ["P-E04"],
    ),
    (
        "concepto vacío",
        _asignar("marco", "pcc", "concepto", "descripcion", valor=""),
        ["P-E04"],
    ),
    ("sin bloques de búsqueda", _asignar("busqueda", "bloques", valor=[]), ["P-E04"]),
    (
        "bloque con términos en blanco",
        _asignar("busqueda", "bloques", 1, "terminos", valor=["", " "]),
        ["P-E04"],
    ),
    # P-E05: fase de cada criterio
    ("criterio de inclusión sin fase", _borrar("criterios", "inclusion", 0, "fase"), ["P-E05"]),
    ("criterio de exclusión sin fase", _borrar("criterios", "exclusion", 1, "fase"), ["P-E05"]),
    # P-E06: regla de combinación
    (
        "regla de combinación sin A",
        _asignar("seleccion", "regla_combinacion", "avanzan", valor=["B", "C", "D", "E"]),
        ["P-E06"],
    ),
    (
        "regla de combinación con F",
        _asignar("seleccion", "regla_combinacion", "avanzan", valor=["A", "B", "F"]),
        ["P-E06"],
    ),
    # P-E07: revisor humano
    (
        "sin revisores humanos",
        _asignar("seleccion", "revisores", valor=[{"id": "claude", "tipo": "llm"}]),
        ["P-E07"],
    ),
    # P-E08: umbral kappa y lote
    ("kappa mayor que 1", _asignar("seleccion", "piloto", "umbral_kappa", valor=1.5), ["P-E08"]),
    ("kappa negativo", _asignar("seleccion", "piloto", "umbral_kappa", valor=-0.1), ["P-E08"]),
    (
        "kappa no numérico",
        _asignar("seleccion", "piloto", "umbral_kappa", valor=float("nan")),
        ["P-E08"],
    ),
    ("lote cero", _asignar("seleccion", "tamano_lote_llm", valor=0), ["P-E08"]),
    ("lote negativo", _asignar("seleccion", "tamano_lote_llm", valor=-3), ["P-E08"]),
    # P-E11: términos de búsqueda traducibles (ADR-0009, puntos 1 a 3)
    ("varias palabras sin comillas", _agregar_termino(0, "fruto seco"), ["P-E11"]),
    ("operador como término, en minúsculas", _agregar_termino(0, "near"), ["P-E11"]),
    ("operador en minúsculas en una frase", _agregar_termino(0, '"fruto and seco"'), ["P-E11"]),
    ("paréntesis", _agregar_termino(0, "(zarambo)"), ["P-E11"]),
    ("etiqueta de campo", _agregar_termino(0, "zarambo[tiab]"), ["P-E11"]),
    ("comodín de un carácter", _agregar_termino(0, "zaramb?"), ["P-E11"]),
    ("truncamiento al inicio", _agregar_termino(0, "*zarambo"), ["P-E11"]),
    ("truncamiento en medio", _agregar_termino(0, "zar*bo"), ["P-E11"]),
    ("truncamiento tras un guion", _agregar_termino(0, "by-*"), ["P-E11"]),
    ("guion al inicio", _agregar_termino(0, "-zarambo"), ["P-E11"]),
    ("comillas sin cerrar", _agregar_termino(0, '"fruto seco'), ["P-E11"]),
    ("comillas vacías", _agregar_termino(0, '""'), ["P-E11"]),
    ("término en blanco junto a otros", _agregar_termino(0, " "), ["P-E11"]),
    ("signo de puntuación", _agregar_termino(0, "zarambo."), ["P-E11"]),
    (
        "variante de un término no truncado",
        _asignar("busqueda", "bloques", 1, "variantes", valor={"secado": ["secados"]}),
        ["P-E11"],
    ),
    (
        "variante truncada",
        _asignar("busqueda", "bloques", 1, "variantes", valor={"dehydrat*": ["dehydrated*"]}),
        ["P-E11"],
    ),
    (
        "término truncado sin variantes en la lista",
        _asignar("busqueda", "bloques", 1, "variantes", valor={"dehydrat*": []}),
        ["P-E11"],
    ),
    (
        "variante de varias palabras sin comillas",
        _asignar("busqueda", "bloques", 1, "variantes", valor={"dehydrat*": ["dry fruit"]}),
        ["P-E11"],
    ),
    # P-A01: evaluación empírica
    (
        "inclusión que exige evaluación empírica",
        _asignar("criterios", "inclusion", 0, "tipo", valor="evaluacion_empirica"),
        ["P-A01"],
    ),
    (
        "exclusión por falta de evaluación empírica",
        _asignar("criterios", "exclusion", 1, "tipo", valor="evaluacion_empirica"),
        ["P-A01"],
    ),
    # P-A02: contexto restrictivo
    (
        "contexto restrictivo",
        _asignar("marco", "pcc", "contexto", "restrictivo", valor=True),
        ["P-A02"],
    ),
    (
        "bloque de contexto",
        _asignar("busqueda", "bloques", 1, "componente", valor="contexto"),
        ["P-A02"],
    ),
    ("término de contexto en un bloque", _agregar_termino(1, '"Industria alimentaria"'), ["P-A02"]),
    # P-A03: estrategias de identificación
    (
        "una sola estrategia activa",
        _asignar("estrategias", "bola_de_nieve", "activa", valor=False),
        ["P-A03"],
    ),
    ("ninguna estrategia activa", _sin_estrategias, ["P-A03"]),
    # P-A04: conjunto de validación
    (
        "conjunto de validación inactivo",
        _asignar("estrategias", "conjunto_validacion", "activo", valor=False),
        ["P-A04"],
    ),
    ("conjunto de validación con un artículo en blanco", _articulo_en_blanco, ["P-A04"]),
    # P-A05: justificación de periodo e idiomas
    (
        "periodo sin justificación",
        _asignar("busqueda", "periodo", "justificacion", valor=""),
        ["P-A05"],
    ),
    (
        "idiomas sin justificación",
        _asignar("busqueda", "idiomas", "justificacion", valor=" "),
        ["P-A05"],
    ),
    # P-A06: categorías completas
    (
        "categoría sin definición",
        _asignar("extraccion", "facetas", 0, "categorias", 0, "definicion", valor=""),
        ["P-A06"],
    ),
    (
        "categoría sin regla",
        _asignar("extraccion", "facetas", 0, "categorias", 1, "regla", valor=""),
        ["P-A06"],
    ),
    (
        "categoría sin ejemplos",
        _asignar("extraccion", "facetas", 1, "categorias", 0, "ejemplos", valor=[]),
        ["P-A06"],
    ),
    # P-A07: acrónimos cortos
    ("acrónimo sin comillas", _agregar_termino(0, "ZF"), ["P-A07"]),
    ("acrónimo entre comillas", _agregar_termino(0, '"ZF"'), ["P-A07"]),
    ("acrónimo truncado", _agregar_termino(1, "PEF*"), ["P-A07"]),
    # P-A08: segundo revisor humano
    ("un solo revisor humano", _quitar_revisor("investigador-2"), ["P-A08"]),
    # P-A09: piloto de cribado sin tamaño
    ("piloto de tamaño 0", _asignar("seleccion", "piloto", "tamano", valor=0), ["P-A09"]),
    ("piloto de tamaño negativo", _asignar("seleccion", "piloto", "tamano", valor=-5), ["P-A09"]),
    # Controles: cambios que no deben producir hallazgos
    (
        "periodo sin límites ni justificación",
        _asignar("busqueda", "periodo", valor={"desde": None, "hasta": None, "justificacion": ""}),
        [],
    ),
    (
        "idiomas sin restricción ni justificación",
        _asignar("busqueda", "idiomas", valor={"valores": [], "justificacion": ""}),
        [],
    ),
    ("sigla dentro de una frase", _agregar_termino(0, '"ZF extract"'), []),
    ("palabra con guion interno truncada", _agregar_termino(0, "by-product*"), []),
    ("palabra con guion interno", _agregar_termino(0, "post-extraction"), []),
    ("palabra con apóstrofo interno", _agregar_termino(0, "farmer's"), []),
    ("palabra con tilde", _agregar_termino(0, "extracción"), []),
    ("frase truncada", _agregar_termino(0, '"fruto sec*"'), []),
    ("palabra sola entre comillas", _agregar_termino(0, '"zarambo"'), []),
    (
        "variantes válidas",
        _asignar(
            "busqueda",
            "bloques",
            1,
            "variantes",
            valor={"dehydrat*": ["dehydration", '"dry fruit"']},
        ),
        [],
    ),
    ("año como término", _agregar_termino(0, "2020"), []),
    ("piloto de un solo registro", _asignar("seleccion", "piloto", "tamano", valor=1), []),
]


@pytest.mark.parametrize(
    ("mutacion", "esperados"),
    [pytest.param(mutacion, esperados, id=nombre) for nombre, mutacion, esperados in CASOS],
)
def test_cada_caso_dispara_exactamente_su_regla(
    datos_sinteticos: dict[str, Any], mutacion: Mutacion, esperados: list[str]
) -> None:
    mutacion(datos_sinteticos)

    assert _ids_de_regla(datos_sinteticos) == esperados


def test_cada_regla_de_contenido_tiene_al_menos_un_caso() -> None:
    cubiertas = {regla for _nombre, _mutacion, esperados in CASOS for regla in esperados}

    # P-E09 y P-E10 leen el directorio del estudio; se prueban en test_protocolo_ciclo_de_vida.py.
    assert cubiertas == set(REGLAS) - {"P-E00", "P-E09", "P-E10"}


def test_sin_revisores_humanos_no_duplica_la_advertencia_del_segundo_revisor(
    datos_sinteticos: dict[str, Any],
) -> None:
    datos_sinteticos["seleccion"]["revisores"] = [{"id": "claude", "tipo": "llm"}]

    assert "P-A08" not in _ids_de_regla(datos_sinteticos)


def test_varios_hallazgos_salen_en_orden_de_catalogo(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["busqueda"]["bloques"][0]["terminos"].append("ZF")
    datos_sinteticos["seleccion"]["tamano_lote_llm"] = 0
    datos_sinteticos["criterios"]["inclusion"][0]["fase"] = None
    datos_sinteticos["marco"]["pcc"]["contexto"]["restrictivo"] = True

    assert _ids_de_regla(datos_sinteticos) == ["P-E05", "P-E08", "P-A02", "P-A07"]


def test_mensajes_de_poblacion_y_concepto_vacios(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["marco"]["pcc"]["poblacion"]["descripcion"] = ""
    datos_sinteticos["marco"]["pcc"]["concepto"]["descripcion"] = ""

    mensajes = [h.mensaje for h in validar_protocolo(Protocolo.model_validate(datos_sinteticos))]

    assert mensajes == [
        "la descripción de la población está vacía",
        "la descripción del concepto está vacía",
    ]


# --- Mensajes ------------------------------------------------------------------


def test_el_mensaje_incluye_id_ubicacion_y_referencia(datos_sinteticos: dict[str, Any]) -> None:
    _pregunta(datos_sinteticos, "PI2")["responde_con"] = []

    [hallazgo] = validar_protocolo(Protocolo.model_validate(datos_sinteticos))

    assert hallazgo.id_regla == "P-E03"
    assert hallazgo.severidad == "error"
    assert hallazgo.ubicacion == "preguntas[1]"
    assert hallazgo.referencia == "Petersen et al. (2015), tabla 3"
    assert str(hallazgo) == (
        "error P-E03 en preguntas[1]: la pregunta descriptiva PI2 no declara qué datos o "
        "facetas la responden (responde_con). Referencia: Petersen et al. (2015), tabla 3"
    )


def test_el_mensaje_de_una_advertencia_cita_su_referencia(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["busqueda"]["bloques"][0]["terminos"].append('"ZF"')

    [hallazgo] = validar_protocolo(Protocolo.model_validate(datos_sinteticos))

    assert str(hallazgo).startswith("advertencia P-A07 en busqueda.bloques[0].terminos[2]: ")
    assert "'\"ZF\"'" in hallazgo.mensaje
    assert str(hallazgo).endswith("Referencia: Lección del ejercicio previo del caso piloto")


@pytest.mark.parametrize(
    ("id_regla", "referencia"),
    [
        ("P-E04", "PRISMA-ScR, ítems 4 y 8; Peters et al. (2024), JBI"),
        (
            "P-E07",
            "CLAUDE.md, regla 1; declaración conjunta Cochrane, Campbell, JBI y CEE (2025)",
        ),
        ("P-E06", "Petersen et al. (2015), tabla 6"),
        ("P-E08", "Landis y Koch (1977)"),
        ("P-A06", "Wohlin et al. (2013)"),
        ("P-A09", "Ali y Petersen (2014); Petersen et al. (2015), figura 17"),
    ],
)
def test_referencias_del_catalogo(id_regla: str, referencia: str) -> None:
    assert REGLAS[id_regla].referencia == referencia


def test_el_catalogo_tiene_los_ids_estables_y_su_severidad() -> None:
    errores = [f"P-E{n:02d}" for n in range(12)]
    advertencias = [f"P-A0{n}" for n in range(1, 10)]

    assert list(REGLAS) == errores + advertencias
    assert all(REGLAS[i].severidad == "error" for i in errores)
    assert all(REGLAS[i].severidad == "advertencia" for i in advertencias)
    assert all(regla.referencia and regla.descripcion for regla in REGLAS.values())


def test_mensajes_de_estrategias_en_singular_y_sin_ninguna(
    datos_sinteticos: dict[str, Any],
) -> None:
    datos_sinteticos["estrategias"]["bola_de_nieve"]["activa"] = False
    [una] = validar_protocolo(Protocolo.model_validate(datos_sinteticos))
    _sin_estrategias(datos_sinteticos)
    [ninguna] = validar_protocolo(Protocolo.model_validate(datos_sinteticos))

    assert "solo está activa la estrategia bases_de_datos" in una.mensaje
    assert "no hay ninguna estrategia" in ninguna.mensaje


# --- Acrónimos -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("termino", "esperado"),
    [
        ("CBD", True),
        ('"CBD"', True),
        ("'CBD'", True),
        (" CBD ", True),
        ("CBD*", True),
        ("CO2", True),
        ("ABCD", True),
        ("ÁRN", True),
        ("ABCDE", False),
        ("A", False),
        ("A1", False),
        ("2020", False),
        ("Cbd", False),
        ("cbd", False),
        ('"CBD oil"', False),
        ("C-BD", False),
        ('"', False),
        ("", False),
    ],
)
def test_es_acronimo_corto(termino: str, esperado: bool) -> None:
    assert es_acronimo_corto(termino) is esperado


# --- Archivos ------------------------------------------------------------------


def test_validar_archivo_valido() -> None:
    resultado = validar_archivo(RUTA_PROTOCOLO_SINTETICO)

    assert resultado.valido
    assert resultado.hallazgos == []
    assert resultado.hash_archivo == hash_archivo(RUTA_PROTOCOLO_SINTETICO)
    assert resultado.estado == "borrador"
    assert resultado.version_protocolo == "0.1.0"


def test_validar_archivo_ubica_la_linea_del_hallazgo(tmp_path: Path) -> None:
    texto = RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8").replace(
        "tamano_lote_llm: 25", "tamano_lote_llm: 0"
    )
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text(texto, encoding="utf-8", newline="\n")

    resultado = validar_archivo(archivo)

    [hallazgo] = resultado.errores
    assert hallazgo.id_regla == "P-E08"
    assert hallazgo.linea is not None
    assert texto.splitlines()[hallazgo.linea - 1].strip() == "tamano_lote_llm: 0"
    assert hallazgo.columna == 3
    assert f"en seleccion.tamano_lote_llm (línea {hallazgo.linea}): " in str(hallazgo)
    assert not resultado.valido
    assert resultado.como_dict()["hallazgos"] == [
        {
            "id_regla": "P-E08",
            "severidad": "error",
            "mensaje": "el tamaño del lote del LLM debe ser un entero positivo (valor: 0)",
            "referencia": "Landis y Koch (1977)",
            "ubicacion": "seleccion.tamano_lote_llm",
            "linea": hallazgo.linea,
            "columna": 3,
        }
    ]


def test_validar_archivo_solo_con_advertencias_es_valido(tmp_path: Path) -> None:
    texto = RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8").replace(
        "restrictivo: false", "restrictivo: true"
    )
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text(texto, encoding="utf-8", newline="\n")

    resultado = validar_archivo(archivo)

    assert resultado.valido
    assert [h.id_regla for h in resultado.advertencias] == ["P-A02"]


def test_validar_archivo_inexistente_da_p_e00(tmp_path: Path) -> None:
    resultado = validar_archivo(tmp_path / "no_existe.yaml")

    [hallazgo] = resultado.hallazgos
    assert hallazgo.id_regla == "P-E00"
    assert "no existe" in hallazgo.mensaje
    assert resultado.hash_archivo is None
    assert resultado.estado is None
    assert not resultado.valido


def test_validar_archivo_mal_formado_da_p_e00_con_linea_y_columna(tmp_path: Path) -> None:
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text("version_esquema: 1\nestado: [borrador\n", encoding="utf-8")

    resultado = validar_archivo(archivo)

    [hallazgo] = resultado.hallazgos
    assert hallazgo.id_regla == "P-E00"
    assert hallazgo.linea is not None and hallazgo.columna is not None
    assert hallazgo.referencia == "Esquema del protocolo, versión 1 (ADR-0006)"
    assert resultado.hash_archivo is not None


def test_con_p_e00_no_se_evaluan_las_demas_reglas(tmp_path: Path) -> None:
    texto = texto_plantilla().replace("tamano_lote_llm: 25", "tamano_lote_llm: x")
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text(texto, encoding="utf-8", newline="\n")

    resultado = validar_archivo(archivo)

    assert {h.id_regla for h in resultado.hallazgos} == {"P-E00"}


def test_como_dict_incluye_version_del_agente_y_hash() -> None:
    datos = validar_archivo(RUTA_PROTOCOLO_SINTETICO).como_dict()

    assert set(datos) == {
        "ruta",
        "hash_archivo",
        "version_agente",
        "version_esquema",
        "estado",
        "version_protocolo",
        "valido",
        "errores",
        "advertencias",
        "hallazgos",
        "registro",
    }
    assert datos["hash_archivo"].startswith("sha256:")
    assert datos["version_esquema"] == 1
    assert datos["registro"]["ruta"] == "datos/eventos.jsonl"
    assert datos["registro"]["existe"] is False
