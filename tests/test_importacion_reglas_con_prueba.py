"""Cada regla del catálogo `REGLAS` aparece en alguna prueba de la importación.

Si se agrega una regla al catálogo y ninguna prueba la nombra, esta prueba falla.
Se miran los literales de cadena del código de las pruebas: un ID que solo está
en un comentario o en un docstring no cuenta.
"""

import ast
from collections.abc import Iterable
from pathlib import Path

from agentresearch.importacion.hallazgos import REGLAS

_CARPETA = Path(__file__).parent


def literales_de_codigo(fuente: str) -> set[str]:
    """Las cadenas del código, sin docstrings (los comentarios no llegan al árbol)."""
    arbol = ast.parse(fuente)
    docstrings: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            primero = nodo.body[0] if nodo.body else None
            if isinstance(primero, ast.Expr) and isinstance(primero.value, ast.Constant):
                docstrings.add(id(primero.value))
    return {
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant)
        and isinstance(nodo.value, str)
        and id(nodo) not in docstrings
    }


def reglas_sin_prueba(reglas: Iterable[str], fuentes: Iterable[str]) -> list[str]:
    """Las reglas cuyo ID no está en ningún literal de las fuentes dadas."""
    literales: set[str] = set()
    for fuente in fuentes:
        literales |= literales_de_codigo(fuente)
    return sorted(regla for regla in reglas if not any(regla in lit for lit in literales))


def test_todas_las_reglas_del_catalogo_tienen_prueba() -> None:
    propio = Path(__file__).name
    archivos = [ruta for ruta in _CARPETA.glob("test_importacion_*.py") if ruta.name != propio]
    assert archivos
    fuentes = [ruta.read_text(encoding="utf-8") for ruta in archivos]
    assert reglas_sin_prueba(REGLAS, fuentes) == []


def test_el_comprobador_falla_si_una_regla_no_aparece() -> None:
    fuentes = ['def test_a() -> None:\n    assert "L-E01" == "L-E01"\n']
    assert reglas_sin_prueba(["L-E01", "L-X99"], fuentes) == ["L-X99"]


def test_un_id_solo_en_un_comentario_o_docstring_no_cuenta() -> None:
    fuente = "\n".join(
        [
            '"""Módulo que habla de L-E02."""',
            "# L-A01 en un comentario",
            "def f() -> None:",
            '    """L-A02."""',
        ]
    )
    esperadas = ["L-A01", "L-A02", "L-E02"]
    assert reglas_sin_prueba(["L-E02", "L-A01", "L-A02"], [fuente]) == esperadas


def test_un_id_dentro_de_un_literal_cuenta() -> None:
    fuente = 'x = "regla L-A03 en un mensaje"\n'
    assert reglas_sin_prueba(["L-A03"], [fuente]) == []
