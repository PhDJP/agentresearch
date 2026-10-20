"""Pruebas del catálogo de reglas, los hallazgos y los resultados de lectura."""

import json

import pytest

from agentresearch.importacion.hallazgos import REGLAS, Hallazgo, crear_hallazgo
from agentresearch.importacion.resultado import (
    CAMPOS_COBERTURA,
    LineaCabecera,
    ResultadoLectura,
    calcular_cobertura,
)
from agentresearch.registros import RegistroNormalizado


def _registro(**campos: object) -> RegistroNormalizado:
    return RegistroNormalizado.model_validate(
        {"fuente": "scopus", "formato": "scopus_csv", "archivo": "a.csv", "posicion": 2, **campos}
    )


def test_el_catalogo_tiene_las_ocho_reglas_con_su_severidad() -> None:
    assert {r.id: r.severidad for r in REGLAS.values()} == {
        "L-E01": "error",
        "L-E02": "error",
        "L-E03": "error",
        "L-A01": "advertencia",
        "L-A02": "advertencia",
        "L-A03": "advertencia",
        "L-A04": "advertencia",
        "L-A05": "advertencia",
    }


def test_crear_hallazgo_toma_la_severidad_del_catalogo() -> None:
    hallazgo = crear_hallazgo("L-A02", "a.ris", "registro sin título", linea=7)
    assert hallazgo.severidad == "advertencia"
    assert hallazgo.linea == 7


def test_regla_desconocida() -> None:
    with pytest.raises(ValueError, match="regla desconocida"):
        crear_hallazgo("L-X99", "a.ris", "x")


def test_hallazgo_rechaza_campos_desconocidos_y_linea_cero() -> None:
    with pytest.raises(ValueError):
        Hallazgo.model_validate(
            {"regla": "L-E01", "severidad": "error", "archivo": "a", "mensaje": "m", "x": 1}
        )
    with pytest.raises(ValueError):
        crear_hallazgo("L-E01", "a", "m", linea=0)


def test_cobertura_cuenta_sobre_el_registro_normalizado() -> None:
    registros = [
        _registro(titulo="Uno", autores=("A", "B"), anio=2020, doi="10.5555/x"),
        _registro(titulo="   ", autores=("",), volumen=""),
        _registro(resumen="Texto", palabras_clave_autor=("k",)),
    ]
    cobertura = calcular_cobertura(registros)
    assert tuple(cobertura) == CAMPOS_COBERTURA
    assert cobertura["titulo"] == 1  # un título solo de espacios es ausente
    assert cobertura["autores"] == 1
    assert cobertura["volumen"] == 0
    assert cobertura["anio"] == 1
    assert cobertura["resumen"] == 1
    assert cobertura["palabras_clave_autor"] == 1
    assert cobertura["doi"] == 1


def test_resultado_resumen_no_lleva_registros_ni_valores() -> None:
    registro = _registro(titulo="Titulo-licenciado", resumen="Resumen-licenciado")
    resultado = ResultadoLectura(
        archivo="a.csv",
        formato="scopus_csv",
        fuente="scopus",
        hash_archivo="sha256:" + "0" * 64,
        registros=(registro,),
        hallazgos=(crear_hallazgo("L-A04", "a.csv", "no aparece la columna del resumen"),),
        lineas_cabecera=(LineaCabecera(linea=1, texto="Provider: X"),),
    )
    resumen = resultado.resumen()
    texto = json.dumps(resumen, ensure_ascii=True)
    assert "licenciado" not in texto
    assert resumen["registros"] == 1
    assert resumen["hallazgos"][0]["regla"] == "L-A04"
    assert resumen["lineas_cabecera"] == [{"linea": 1, "texto": "Provider: X"}]
    assert resumen["cobertura"]["titulo"] == 1
    assert resultado.errores == ()
    assert len(resultado.advertencias) == 1
