"""Pruebas del archivo de mapeo y del lector del CSV genérico (sintético; tema ficticio)."""

import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.importacion.entrada import ErrorDeArchivo
from agentresearch.importacion.mapeo import ErrorDeMapeo, Mapeo
from agentresearch.importacion.motor_csv import LIMITE_CAMPO
from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.importacion.servicio import formatos_disponibles, leer
from agentresearch.trazabilidad import hash_bytes

from .apoyo_importacion import csv_texto, escribir

ENCABEZADO = ["Identificador", "Titulo", "Autores", "Anio", "Paginas", "DOI", "Resumen", "Extra"]

MAPEO: dict[str, Any] = {
    "Identificador": "id_fuente:lens_id",
    "Titulo": "titulo",
    "Autores": {"campo": "autores", "separador": "; "},
    "Anio": "anio",
    "Paginas": "paginas",
    "DOI": "doi",
    "Resumen": "resumen",
}


def _fila(numero: int = 1, **cambios: str) -> list[str]:
    base = {
        "Identificador": f"000-000-000-{numero:03d}",
        "Titulo": f"Abejas de cristal {numero}",
        "Autores": "Cristal, A; Vidrio, B",
        "Anio": "2024-05-06",
        "Paginas": "10-20",
        "DOI": f"10.5555/ABEJA.{numero}",
        "Resumen": "Resumen ficticio.",
        "Extra": "dato extra",
    }
    base.update(cambios)
    return [base[c] for c in ENCABEZADO]


def _mapeo(tmp_path: Path, contenido: object, nombre: str = "mapeo.json") -> Mapeo:
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return Mapeo.cargar(ruta)


def _leer(
    tmp_path: Path, texto: str, mapeo: Mapeo | None, *, nombre: str = "lens.csv"
) -> ResultadoLectura:
    ruta = escribir(tmp_path / nombre, texto)
    return leer(ruta, "csv", "lens", mapeo)


def _reglas(resultado: ResultadoLectura) -> list[str]:
    return [h.regla for h in resultado.hallazgos]


def test_formato_disponible() -> None:
    assert "csv" in formatos_disponibles()


def test_registro_con_mapeo_valido_y_hash_del_mapeo(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, MAPEO)
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]), mapeo)
    assert resultado.hash_mapeo == hash_bytes((tmp_path / "mapeo.json").read_bytes())
    assert resultado.hash_mapeo == mapeo.hash
    registro = resultado.registros[0]
    assert registro.formato == "csv"
    assert registro.fuente == "lens"
    assert registro.posicion == 2
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("lens_id", "000-000-000-001")
    assert registro.titulo == "Abejas de cristal 1"
    assert registro.autores == ("Cristal, A", "Vidrio, B")
    assert registro.anio == 2024
    assert registro.paginas == "10-20"
    assert registro.doi == "10.5555/abeja.1"
    assert registro.resumen == "Resumen ficticio."
    assert registro.otros == {"Extra": "dato extra"}
    assert _reglas(resultado) == []


def test_celda_vacia_de_id_fuente_queda_ninguno(tmp_path: Path) -> None:
    resultado = _leer(
        tmp_path, csv_texto(ENCABEZADO, [_fila(1, Identificador="")]), _mapeo(tmp_path, MAPEO)
    )
    registro = resultado.registros[0]
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("ninguno", None)
    assert _reglas(resultado) == []  # tiene DOI: no es L-A01


def test_el_mismo_archivo_y_mapeo_dan_el_mismo_hash(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, MAPEO)
    texto = csv_texto(ENCABEZADO, [_fila(1)])
    uno = _leer(tmp_path, texto, mapeo, nombre="a.csv").registros[0]
    dos = _leer(tmp_path, texto, mapeo, nombre="b.csv").registros[0]
    assert uno.hash_completo == dos.hash_completo


@pytest.mark.parametrize(
    ("mapeo", "fragmento"),
    [
        ({"Titulo": "no_es_un_campo"}, "no es un campo del esquema"),
        ({"Autores": "autores"}, "exige un objeto con separador"),
        ({"Titulo": {"campo": "titulo", "separador": "; "}}, "no admite separador"),
        ({"Titulo": "titulo", "Resumen": "titulo"}, "mismo destino"),
        ({"Identificador": "id_fuente"}, "id_fuente:TIPO"),
        ({"Identificador": "id_fuente:ninguno"}, "tipo de identificador"),
        ({"Titulo": {"campo": "titulo"}}, "exactamente"),
        ({"Titulo": {"campo": "autores", "separador": ""}}, "texto no vacío"),
        ({"Titulo": 5}, "texto o un objeto"),
        (["titulo"], "objeto JSON"),
    ],
)
def test_l_e02_mapeo_con_contenido_invalido(tmp_path: Path, mapeo: object, fragmento: str) -> None:
    cargado = _mapeo(tmp_path, mapeo, nombre="mi_mapeo.json")
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]), cargado)
    assert resultado.numero_registros == 0
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert errores
    assert all(h.archivo == "mi_mapeo.json" for h in errores)
    assert fragmento in " ".join(h.mensaje for h in errores)
    assert resultado.hash_mapeo == cargado.hash


def test_l_e02_columna_del_mapeo_que_no_esta_en_el_encabezado(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, {**MAPEO, "Columna inexistente": "volumen"})
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]), mapeo)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [h.archivo for h in errores] == ["mapeo.json"]
    assert "Columna inexistente" in errores[0].mensaje
    assert resultado.numero_registros == 0


def test_error_de_mapeo_ilegible_o_no_json(tmp_path: Path) -> None:
    with pytest.raises(ErrorDeMapeo):
        Mapeo.cargar(tmp_path / "no_existe.json")
    malo = tmp_path / "malo.json"
    malo.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ErrorDeMapeo, match="JSON"):
        Mapeo.cargar(malo)
    latin = tmp_path / "latin.json"
    latin.write_bytes(b'{"T": "titulo", "caf\xe9": "doi"}')
    with pytest.raises(ErrorDeMapeo):
        Mapeo.cargar(latin)


def test_mapeo_con_bom_se_acepta(tmp_path: Path) -> None:
    ruta = tmp_path / "bom.json"
    ruta.write_bytes(b"\xef\xbb\xbf" + json.dumps(MAPEO).encode("utf-8"))
    assert Mapeo.cargar(ruta).problemas == ()


def test_leer_exige_mapeo_solo_con_csv(tmp_path: Path) -> None:
    ruta = escribir(tmp_path / "a.csv", csv_texto(ENCABEZADO, [_fila(1)]))
    with pytest.raises(ValueError, match="exige un archivo de mapeo"):
        leer(ruta, "csv", "lens")
    with pytest.raises(ValueError, match="solo el formato csv"):
        leer(ruta, "ris", "lens", _mapeo(tmp_path, MAPEO))
    with pytest.raises(ErrorDeArchivo):
        leer(tmp_path / "no_existe.csv", "csv", "lens", _mapeo(tmp_path, MAPEO))


def test_l_a04_campo_esperado_sin_columna_mapeada(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, {k: v for k, v in MAPEO.items() if k != "Resumen"})
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]), mapeo)
    avisos = [h for h in resultado.hallazgos if h.regla == "L-A04"]
    assert len(avisos) == 1
    assert "resumen" in avisos[0].mensaje
    assert resultado.registros[0].otros["Resumen"] == "Resumen ficticio."


def test_l_e02_filas_con_mas_y_menos_columnas(tmp_path: Path) -> None:
    texto = csv_texto(ENCABEZADO, [_fila(1), [*_fila(2), "sobra"], _fila(3)[:-2], _fila(4)])
    resultado = _leer(tmp_path, texto, _mapeo(tmp_path, MAPEO))
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [(h.fila, h.archivo) for h in errores] == [(3, "lens.csv"), (4, "lens.csv")]
    assert resultado.numero_registros == 2


def test_l_e03_l_a05_l_a01_y_l_a02(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, MAPEO)
    repetido = csv_texto(ENCABEZADO, [_fila(1), _fila(2), _fila(1)])
    assert _reglas(_leer(tmp_path, repetido, mapeo)).count("L-E03") == 1
    sin_id = csv_texto(
        ENCABEZADO,
        [_fila(1, Identificador=""), _fila(2, Identificador="", DOI="10.5555/ABEJA.1")],
    )
    assert _reglas(_leer(tmp_path, sin_id, mapeo)).count("L-A05") == 1
    huerfano = csv_texto(ENCABEZADO, [_fila(1, Identificador="", DOI="", Titulo="")])
    reglas = _reglas(_leer(tmp_path, huerfano, mapeo))
    assert "L-A01" in reglas
    assert "L-A02" in reglas


def test_archivo_vacio_solo_encabezado_y_celda_sobre_el_limite(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, MAPEO)
    assert _reglas(_leer(tmp_path, "", mapeo)) == ["L-E02"]
    assert _leer(tmp_path, csv_texto(ENCABEZADO, []), mapeo).numero_registros == 0
    grande = "x" * (LIMITE_CAMPO + 1)
    texto = csv_texto(ENCABEZADO, [_fila(1), _fila(2, Resumen=grande), _fila(3)])
    resultado = _leer(tmp_path, texto, mapeo)
    assert resultado.numero_registros == 1
    assert resultado.detenido_en_fila == 3
    encabezado_grande = _leer(tmp_path, csv_texto([grande], []), mapeo)
    assert encabezado_grande.detenido_en_fila == 1
    assert [h.regla for h in encabezado_grande.hallazgos] == ["L-E02"]


def test_l_e01_con_mapeo_conserva_el_hash_del_mapeo(tmp_path: Path) -> None:
    mapeo = _mapeo(tmp_path, MAPEO)
    ruta = tmp_path / "latin1.csv"
    ruta.write_bytes(b'"Titulo"\n"Caf\xe9"\n')
    resultado = leer(ruta, "csv", "lens", mapeo)
    assert _reglas(resultado) == ["L-E01"]
    assert resultado.hash_mapeo == mapeo.hash
