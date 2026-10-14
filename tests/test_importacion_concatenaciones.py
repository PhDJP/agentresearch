"""Pruebas del resolvedor de concatenaciones `#` y de la decodificación de LaTeX."""

import pytest

from agentresearch.importacion.concatenaciones import resolver_valor
from agentresearch.importacion.lector_bibtex import decodificar_latex

CADENAS = {"pub": '"Editorial Ficticia"', "anio": "2020", "ambas": 'pub # " " # anio'}


@pytest.mark.parametrize(
    ("expresion", "esperado"),
    [
        ("{Un texto}", "Un texto"),
        ('"Un texto"', "Un texto"),
        ("2024", "2024"),
        ('"Primera " # "parte"', "Primera parte"),
        ('"Primera " # {parte} # " " # 2020', "Primera parte 2020"),
        ('"Primera " #\n  "parte"', "Primera parte"),
        ("pub", "Editorial Ficticia"),
        ("PUB", "Editorial Ficticia"),
        ('"Por " # pub # { (' + "2020" + ")}", "Por Editorial Ficticia (2020)"),
        ("ambas", "Editorial Ficticia 2020"),
        ("{con {llaves} anidadas}", "con {llaves} anidadas"),
        ('"comilla {"} dentro de llaves"', 'comilla {"} dentro de llaves'),
        ("{a # b}", "a # b"),
        ("indefinida", "indefinida"),
        ('"x" # indefinida', "xindefinida"),
        ("jan", "jan"),
        (r"{\{ llave escapada}", r"\{ llave escapada"),
    ],
)
def test_resolver_valor(expresion: str, esperado: str) -> None:
    assert resolver_valor(expresion, CADENAS) == esperado


@pytest.mark.parametrize(
    "expresion", ["{sin cierre", '"sin cierre', '"a" # ', "# {a}", '"a" "b"', "{a} ?", "?x"]
)
def test_una_expresion_que_no_se_puede_analizar_se_devuelve_sin_cambios(expresion: str) -> None:
    assert resolver_valor(expresion, CADENAS) == expresion.strip()


def test_una_cadena_que_se_refiere_a_si_misma_no_cicla() -> None:
    assert resolver_valor("a", {"a": "b", "b": "a"}) in {"a", "b"}


@pytest.mark.parametrize(
    ("latex", "texto"),
    [
        (r"{\'e}tica", "ética"),
        (r"{\"u}n", "ün"),
        (r"\~{n}andú", "ñandú"),
        (r"{\o}", "ø"),
        (r"{\'a}rbol y {\`e}", "árbol y è"),
        (r"{CO}2", "CO2"),
        ("sin latex ni llaves", "sin latex ni llaves"),
        ("50% de 5 & 6 ~ 7", "50% de 5 & 6 ~ 7"),
        (r"{\'e} al 50% y a & b ~ c", "é al 50% y a & b ~ c"),
        (r"10\% escapado", "10% escapado"),
        ("Texto con <sub>2</sub> {x}", "Texto con <sub>2</sub> x"),
        ("CO$_2$ {y}", "CO$_2$ y"),
    ],
)
def test_decodificar_latex(latex: str, texto: str) -> None:
    assert decodificar_latex(latex) == texto
