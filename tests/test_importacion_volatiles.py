"""Pruebas de los volátiles y de la lectura del EID dentro de `N1` (H1 y H2)."""

import pytest

from agentresearch.importacion.volatiles import (
    COLUMNAS_VOLATILES_SCOPUS_CSV,
    procesar_n1_scopus,
    quitar_conteo_de_nota,
    tiene_prefijo,
)


@pytest.mark.parametrize(
    ("nota", "esperado"),
    [
        # La tabla de ejemplos de la especificación, «Regla exacta para `note`».
        ("Cited by: 12; All Open Access; Gold Open Access", "All Open Access; Gold Open Access"),
        (
            "All Open Access; Cited by: 3; Gold Open Access",
            "All Open Access; Gold Open Access",
        ),
        ("All Open Access; Cited by: 3", "All Open Access"),
        ("Cited by: 7", None),
        ("All Open Access", "All Open Access"),
        ("Cited by 7; Gold Open Access", "Cited by 7; Gold Open Access"),
        # Variantes que no coinciden se conservan; los repetidos se descartan todos.
        ("cited by: 5; Gold", "cited by: 5; Gold"),
        ("Cited by: 5 (2); Gold", "Cited by: 5 (2); Gold"),
        ("Cited by: 1; Gold; Cited by: 2", "Gold"),
        ("", None),
        ("  Cited by:  8 ", None),
    ],
)
def test_quitar_conteo_de_nota(nota: str, esperado: str | None) -> None:
    assert quitar_conteo_de_nota(nota) == esperado


def test_la_columna_cited_by_es_volatil() -> None:
    assert COLUMNAS_VOLATILES_SCOPUS_CSV == ("Cited by",)


def test_tiene_prefijo_colapsa_espacios() -> None:
    assert tiene_prefijo("  Export   Date: 1 enero", ("Export Date:",))
    assert not tiene_prefijo("Fecha: Export Date:", ("Export Date:",))


def test_n1_con_linea_eid_la_consume_y_conserva_el_resto() -> None:
    eid, resto = procesar_n1_scopus(
        ["CODEN: ABCD", "EID: 2-s2.0-000000000001", "Funding text 1: algo"]
    )
    assert eid == "2-s2.0-000000000001"
    assert resto == ["CODEN: ABCD", "Funding text 1: algo"]


def test_n1_sin_linea_eid_no_inventa_nada() -> None:
    eid, resto = procesar_n1_scopus(["CODEN: ABCD", "Funding details: x"])
    assert eid is None
    assert resto == ["CODEN: ABCD", "Funding details: x"]


def test_n1_con_eid_vacio_queda_sin_eid_y_la_linea_se_consume() -> None:
    eid, resto = procesar_n1_scopus(["EID:   ", "CODEN: ABCD"])
    assert eid is None
    assert resto == ["CODEN: ABCD"]


def test_n1_con_dos_lineas_eid_toma_la_primera_y_la_otra_sigue_a_otros() -> None:
    eid, resto = procesar_n1_scopus(["EID: 2-s2.0-1", "EID: 2-s2.0-2"])
    assert eid == "2-s2.0-1"
    assert resto == ["EID: 2-s2.0-2"]


def test_n1_descarta_export_date_y_cited_by() -> None:
    eid, resto = procesar_n1_scopus(
        ["Cited By: 4", "Export Date: 13 October 2026", "CODEN: ABCD", "EID: 2-s2.0-1"]
    )
    assert eid == "2-s2.0-1"
    assert resto == ["CODEN: ABCD"]
