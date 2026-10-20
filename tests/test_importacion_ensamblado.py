"""Pruebas de las piezas comunes de ensamblado: `anio`, `paginas`, `otros` y L-A02 a L-A04."""

import pytest

from agentresearch.importacion.ensamblado import (
    CAMPOS_ESPERADOS,
    agregar_otros,
    componer_paginas,
    extraer_anio,
    hallazgo_de_cabecera,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
    unir_otros,
)

from .apoyo_importacion import registro


def test_unir_otros_une_con_punto_y_coma_y_descarta_vacios() -> None:
    assert unir_otros({"N1": ["uno", " ", "dos  tres"], "X": ["", "  "], "Y": ["solo"]}) == {
        "N1": "uno; dos tres",
        "Y": "solo",
    }


def test_agregar_otros_conserva_el_orden() -> None:
    destino: dict[str, list[str]] = {"A": ["1"]}
    agregar_otros(destino, {"A": ["2"], "B": ["3"]})
    assert destino == {"A": ["1", "2"], "B": ["3"]}


@pytest.mark.parametrize(
    ("valor", "anio", "otros"),
    [
        ("2024", 2024, {}),
        ("2024/03/05/", 2024, {}),
        ("  2019 ", 2019, {}),
        ("Early access 2023", 2023, {}),
        ("sin año", None, {"PY": ["sin año"]}),
        ("12345", None, {"PY": ["12345"]}),
        ("", None, {}),
        (None, None, {}),
    ],
)
def test_extraer_anio(valor: str | None, anio: int | None, otros: dict[str, list[str]]) -> None:
    assert extraer_anio("PY", valor) == (anio, otros)


@pytest.mark.parametrize(
    ("inicio", "fin", "paginas", "otros"),
    [
        ("101", "110", "101-110", {}),
        ("101", None, "101", {}),
        ("101", "", "101", {}),
        (None, "110", None, {"EP": ["110"]}),
        (None, None, None, {}),
        ("", "", None, {}),
    ],
)
def test_componer_paginas(
    inicio: str | None, fin: str | None, paginas: str | None, otros: dict[str, list[str]]
) -> None:
    assert componer_paginas(("BP", inicio), ("EP", fin)) == (paginas, otros)


def test_l_a02_registro_sin_titulo() -> None:
    hallazgos = hallazgos_de_calidad(
        "a.csv", [registro(titulo="Uno", posicion=2), registro(posicion=5), registro(titulo=" ")]
    )
    assert [(h.regla, h.linea, h.severidad) for h in hallazgos] == [
        ("L-A02", 5, "advertencia"),
        ("L-A02", 2, "advertencia"),
    ]


def test_l_a03_cabecera_con_lineas_no_vacias() -> None:
    cabecera, hallazgo = hallazgo_de_cabecera(
        "a.ris", [(1, "Provider: X"), (2, "Content: Y"), (3, "")]
    )
    assert [(c.linea, c.texto) for c in cabecera] == [(1, "Provider: X"), (2, "Content: Y")]
    assert hallazgo is not None
    assert (hallazgo.regla, hallazgo.linea) == ("L-A03", 1)
    assert "2" in hallazgo.mensaje
    assert "Provider" not in hallazgo.mensaje


def test_l_a03_sin_cabecera_o_solo_vacia_no_avisa() -> None:
    assert hallazgo_de_cabecera("a.ris", []) == ((), None)
    assert hallazgo_de_cabecera("a.ris", [(1, ""), (2, "  ")]) == ((), None)


def test_l_a04_campo_esperado_ausente() -> None:
    origen = {
        "titulo": ("TI",),
        "autores": ("AU",),
        "anio": ("PY",),
        "doi": ("DO",),
        "resumen": ("AB", "N2"),
    }
    hallazgos = hallazgos_de_campos_esperados("a.ris", origen, {"TI", "AU", "PY", "DO"})
    assert len(hallazgos) == 1
    assert hallazgos[0].regla == "L-A04"
    assert "resumen" in hallazgos[0].mensaje
    assert hallazgos[0].linea is None


def test_l_a04_alguna_de_las_etiquetas_basta() -> None:
    origen = {
        "titulo": ("TI",),
        "autores": ("AU",),
        "anio": ("PY",),
        "doi": ("DO",),
        "resumen": ("AB", "N2"),
    }
    assert hallazgos_de_campos_esperados("a.ris", origen, {"TI", "AU", "PY", "DO", "N2"}) == ()


def test_l_a04_sin_ninguna_etiqueta_avisa_de_los_cinco() -> None:
    hallazgos = hallazgos_de_campos_esperados("a.ris", {}, set())
    assert len(hallazgos) == len(CAMPOS_ESPERADOS)
