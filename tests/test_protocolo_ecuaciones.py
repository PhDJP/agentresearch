"""Pruebas de las ecuaciones de búsqueda por fuente (ADR-0009).

Las ecuaciones se comparan con archivos de referencia en
`tests/datos/ecuaciones/<escenario>/`. Para regenerarlos después de un
cambio intencional de sintaxis, ejecute las pruebas con la variable de
entorno `AGENTRESEARCH_ACTUALIZAR_REFERENCIAS=1` y revise el diff antes de
confirmarlo: un archivo de referencia es una afirmación sobre la sintaxis de
la fuente, verificada contra su documentación.
"""

import copy
import os
from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo.ecuaciones import (
    TRADUCTORES,
    ConjuntoEcuaciones,
    Ecuacion,
    generar_ecuaciones,
)
from agentresearch.protocolo.ecuaciones.documento import (
    OrigenEcuaciones,
    hash_de_ecuaciones,
    texto_ecuaciones,
)
from agentresearch.protocolo.ecuaciones.openalex import MAXIMO_URL, TraductorOpenalex
from agentresearch.protocolo.modelo import Protocolo

DATOS = Path(__file__).parent / "datos" / "ecuaciones"
ACTUALIZAR = os.environ.get("AGENTRESEARCH_ACTUALIZAR_REFERENCIAS") == "1"

ORIGEN = OrigenEcuaciones(
    ruta_protocolo="protocolo/protocolo.yaml",
    version_protocolo="1.0.0",
    estado="vigente",
    hash_protocolo="sha256:" + "0" * 64,
    version_agente="0.0.0-prueba",
)

FUENTES = [
    {"id": fuente, "tipo": "api", "cobertura": "", "limites": ""}
    for fuente in ("openalex", "pubmed", "scopus", "wos", "lens")
]

BLOQUES: list[dict[str, Any]] = [
    {
        "id": "B1",
        "nombre": "Zarambo y sus subproductos",
        "componente": "poblacion",
        "terminos": [
            "zarambo",
            '"Zarambus fictus"',
            "by-product*",
            "post-extraction",
            "fru*",
            '"zarambina"',
        ],
    },
    {
        "id": "B2",
        "nombre": "Secado",
        "componente": "concepto",
        "terminos": ["secado", "dehydrat*", '"freeze dr*"', '"fruto sec*"', "liofilización"],
    },
]

VARIANTES = {
    "B1": {"fru*": ["fruit", "fruits"], "by-product*": ["by-product", "by-products"]},
    "B2": {
        "dehydrat*": ["dehydration", "dehydrated"],
        '"freeze dr*"': ['"freeze drying"', '"freeze dried"'],
        '"fruto sec*"': ['"fruto seco"', '"frutos secos"'],
    },
}


def _protocolo(datos: dict[str, Any], escenario: str) -> Protocolo:
    """Protocolo sintético con los bloques de prueba, según el escenario.

    - `con_variantes`: todas las variantes; periodo cerrado; idiomas y tipos reconocidos.
    - `sin_variantes`: ninguna variante; periodo abierto; un idioma y un tipo no reconocidos.
    """
    datos = copy.deepcopy(datos)
    datos["fuentes"] = FUENTES
    bloques = copy.deepcopy(BLOQUES)
    busqueda = datos["busqueda"]
    if escenario == "con_variantes":
        for bloque in bloques:
            bloque["variantes"] = VARIANTES[bloque["id"]]
        busqueda["periodo"] = {"desde": 2010, "hasta": 2025, "justificacion": "j"}
        busqueda["idiomas"] = {"valores": ["en", "es"], "justificacion": "j"}
        busqueda["tipos_documento"] = ["articulo", "revision"]
    else:
        busqueda["periodo"] = {"desde": 2015, "hasta": None, "justificacion": "j"}
        busqueda["idiomas"] = {"valores": ["en", "español"], "justificacion": "j"}
        busqueda["tipos_documento"] = ["articulo", "poster"]
    busqueda["bloques"] = bloques
    return Protocolo.model_validate(datos)


def _texto_referencia(ecuacion: Ecuacion) -> str:
    lineas = [f"ecuacion: {ecuacion.texto if ecuacion.texto is not None else '(bloqueada)'}"]
    lineas.append("avisos:")
    lineas += [f"- {aviso}" for aviso in ecuacion.avisos]
    lineas.append("instrucciones de la interfaz:")
    lineas += [f"- {instruccion}" for instruccion in ecuacion.limites.instrucciones]
    return "\n".join(lineas) + "\n"


def _comparar(ruta: Path, obtenido: str) -> None:
    if ACTUALIZAR:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(obtenido.encode("utf-8"))
    assert obtenido == ruta.read_bytes().decode("utf-8"), f"difiere de {ruta}"


def _conjunto(datos: dict[str, Any], escenario: str) -> ConjuntoEcuaciones:
    return generar_ecuaciones(_protocolo(datos, escenario))


# --- Archivos de referencia -----------------------------------------------------------


@pytest.mark.parametrize("escenario", ["con_variantes", "sin_variantes"])
@pytest.mark.parametrize("fuente", [*TRADUCTORES, "generica"])
def test_ecuacion_de_referencia(
    datos_sinteticos: dict[str, Any], escenario: str, fuente: str
) -> None:
    conjunto = _conjunto(datos_sinteticos, escenario)
    [ecuacion] = [e for e in conjunto.ecuaciones if e.fuente == fuente]

    _comparar(DATOS / escenario / f"{fuente}.txt", _texto_referencia(ecuacion))


@pytest.mark.parametrize("escenario", ["con_variantes", "sin_variantes"])
def test_ecuaciones_md_de_referencia(datos_sinteticos: dict[str, Any], escenario: str) -> None:
    texto = texto_ecuaciones(_conjunto(datos_sinteticos, escenario), ORIGEN)

    _comparar(DATOS / escenario / "ecuaciones.md", texto)


# --- Propiedades que los archivos de referencia fijan ---------------------------------


def test_con_todas_las_variantes_ninguna_fuente_queda_bloqueada(
    datos_sinteticos: dict[str, Any],
) -> None:
    conjunto = _conjunto(datos_sinteticos, "con_variantes")

    assert conjunto.bloqueadas == []
    assert conjunto.sin_traductor == ["lens"]
    assert [e.fuente for e in conjunto.ecuaciones] == [
        "openalex",
        "pubmed",
        "scopus",
        "wos",
        "generica",
    ]


def test_sin_variantes_se_bloquean_las_fuentes_que_no_admiten_el_truncamiento(
    datos_sinteticos: dict[str, Any],
) -> None:
    conjunto = _conjunto(datos_sinteticos, "sin_variantes")

    # PubMed: raíces de menos de 4 letras (fru*, "freeze dr*", "fruto sec*").
    # Scopus: "freeze dr*" (menos de 3). Web of Science: frases truncadas.
    # OpenAlex usa search.exact; "freeze dr*" tiene una raíz de 2 letras.
    assert conjunto.bloqueadas == ["openalex", "pubmed", "scopus", "wos"]
    [pubmed] = [e for e in conjunto.ecuaciones if e.fuente == "pubmed"]
    bloqueantes = [a.termino for a in pubmed.avisos if a.tipo == "bloqueante"]
    assert bloqueantes == ["fru*", '"freeze dr*"', '"fruto sec*"']


def test_openalex_conserva_la_lematizacion_si_todos_los_truncados_tienen_variantes(
    datos_sinteticos: dict[str, Any],
) -> None:
    [openalex] = [
        e for e in _conjunto(datos_sinteticos, "con_variantes").ecuaciones if e.fuente == "openalex"
    ]

    assert openalex.texto is not None
    assert openalex.texto.startswith("title_and_abstract.search:(")
    assert "*" not in openalex.texto
    assert not any("search.exact" in a.mensaje for a in openalex.avisos)


def test_openalex_usa_search_exact_si_falta_alguna_variante(
    datos_sinteticos: dict[str, Any],
) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    del datos["busqueda"]["bloques"][1]["variantes"]["dehydrat*"]
    protocolo = Protocolo.model_validate(datos)

    ecuacion = TraductorOpenalex().traducir(protocolo.busqueda)

    assert ecuacion.texto is not None
    assert ecuacion.texto.startswith("title_and_abstract.search.exact:(")
    assert "dehydrat*" in ecuacion.texto
    assert '"freeze drying"' in ecuacion.texto  # raíz corta: usa sus variantes
    [aviso] = [a for a in ecuacion.avisos if "search.exact" in a.mensaje]
    assert "(dehydrat*)" in aviso.mensaje


def test_openalex_avisa_si_la_url_supera_el_maximo(datos_sinteticos: dict[str, Any]) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["busqueda"]["bloques"][0]["terminos"] += [f"termino{n:04d}" for n in range(400)]

    ecuacion = TraductorOpenalex().traducir(Protocolo.model_validate(datos).busqueda)

    assert ecuacion.longitud is not None and ecuacion.longitud > MAXIMO_URL
    assert any("supera el máximo conocido de OpenAlex" in a.mensaje for a in ecuacion.avisos)
    assert ecuacion.texto is not None  # es una advertencia, no un bloqueo


def test_un_solo_bloque_no_lleva_parentesis_de_mas(datos_sinteticos: dict[str, Any]) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["busqueda"]["bloques"] = [
        {"id": "B1", "nombre": "n", "componente": "poblacion", "terminos": ["zarambo", "secado"]}
    ]
    datos["busqueda"]["periodo"] = {"desde": None, "hasta": None, "justificacion": ""}
    datos["busqueda"]["idiomas"] = {"valores": [], "justificacion": ""}
    datos["busqueda"]["tipos_documento"] = []
    conjunto = generar_ecuaciones(Protocolo.model_validate(datos))

    textos = {e.fuente: e.texto for e in conjunto.ecuaciones}
    assert textos == {
        "openalex": "title_and_abstract.search:(zarambo OR secado)",
        "pubmed": "(zarambo[tiab] OR secado[tiab])",
        "scopus": "TITLE-ABS-KEY((zarambo OR secado))",
        "wos": "TS=((zarambo OR secado))",
        "generica": "(zarambo OR secado)",
    }


def test_una_fuente_repetida_se_traduce_una_vez(datos_sinteticos: dict[str, Any]) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["fuentes"] = [*datos["fuentes"], {**datos["fuentes"][0], "id": "OpenAlex"}]

    conjunto = generar_ecuaciones(Protocolo.model_validate(datos))

    assert [e.fuente for e in conjunto.ecuaciones].count("openalex") == 1


def test_como_dict_distingue_bloqueadas_y_sin_traductor(datos_sinteticos: dict[str, Any]) -> None:
    datos = _conjunto(datos_sinteticos, "sin_variantes").como_dict()

    assert datos["fuentes_bloqueadas"] == ["openalex", "pubmed", "scopus", "wos"]
    assert datos["fuentes_sin_traductor"] == ["lens"]
    [scopus] = [e for e in datos["ecuaciones"] if e["fuente"] == "scopus"]
    assert scopus["ecuacion"] is None
    assert scopus["bloqueada"] is True
    assert scopus["manual"] is True
    assert scopus["documentacion"][0]["verificada"] == "2026-09-26"


# --- ecuaciones.md -------------------------------------------------------------------


def test_el_hash_de_la_cabecera_se_lee_de_vuelta(datos_sinteticos: dict[str, Any]) -> None:
    texto = texto_ecuaciones(_conjunto(datos_sinteticos, "con_variantes"), ORIGEN)

    assert hash_de_ecuaciones(texto) == ORIGEN.hash_protocolo
    assert hash_de_ecuaciones("# Ecuaciones\n") is None


def test_ecuaciones_md_es_determinista(datos_sinteticos: dict[str, Any]) -> None:
    primero = texto_ecuaciones(_conjunto(datos_sinteticos, "sin_variantes"), ORIGEN)
    segundo = texto_ecuaciones(_conjunto(datos_sinteticos, "sin_variantes"), ORIGEN)

    assert primero == segundo
    assert "\r" not in primero
    assert primero.endswith("\n")


def test_web_of_science_usa_variantes_si_la_raiz_es_corta(
    datos_sinteticos: dict[str, Any],
) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["busqueda"]["bloques"][0]["terminos"].append("ze*")
    protocolo = Protocolo.model_validate(datos)
    [wos] = [e for e in generar_ecuaciones(protocolo).ecuaciones if e.fuente == "wos"]

    assert wos.bloqueada
    [aviso] = [a for a in wos.avisos if a.tipo == "bloqueante"]
    assert aviso.termino == "ze*"
    assert "exige al menos 3 letras antes del *" in aviso.mensaje


def test_periodo_solo_con_anio_final(datos_sinteticos: dict[str, Any]) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["busqueda"]["periodo"] = {"desde": None, "hasta": 2020, "justificacion": "j"}
    conjunto = generar_ecuaciones(Protocolo.model_validate(datos))
    textos = {e.fuente: e for e in conjunto.ecuaciones}

    assert textos["scopus"].texto is not None
    assert " AND PUBYEAR < 2021 AND " in textos["scopus"].texto
    assert "Periodo: hasta 2020, inclusive" in textos["generica"].limites.descripcion
    assert (
        textos["wos"]
        .limites.instrucciones[0]
        .startswith("Periodo: ajuste los años de publicación en la interfaz: hasta 2020, inclusive")
    )


def test_una_fuente_sin_limites_lo_dice(datos_sinteticos: dict[str, Any]) -> None:
    datos = _protocolo(datos_sinteticos, "con_variantes").model_dump()
    datos["busqueda"]["periodo"] = {"desde": None, "hasta": None, "justificacion": ""}
    datos["busqueda"]["idiomas"] = {"valores": [], "justificacion": ""}
    datos["busqueda"]["tipos_documento"] = []

    texto = texto_ecuaciones(generar_ecuaciones(Protocolo.model_validate(datos)), ORIGEN)

    assert "- Límites: no hay límites que aplicar" in texto
    assert "2. No hace falta aplicar filtros en la interfaz" in texto
