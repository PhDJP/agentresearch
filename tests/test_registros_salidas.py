"""Pruebas de la escritura determinista de `registros.jsonl` y `registros.csv`."""

import csv
import io
import json
from pathlib import Path

import pytest

from agentresearch.registros import Registro, RegistroNormalizado, construir_registros
from agentresearch.registros.politica import CAMPOS_HABILITABLES
from agentresearch.registros.salidas import (
    COLUMNAS_CSV,
    escribir_registros_jsonl,
    escribir_vista_csv,
    serializar_registros_jsonl,
    serializar_vista_csv,
)
from agentresearch.registros.versionado import CAMPOS_SIEMPRE_VERSIONADOS
from agentresearch.trazabilidad import hash_bytes

RESUMEN = "Resumen ficticio que no debe aparecer en ningún archivo versionado."
CAMPOS = ("titulo", "autores", "anio", "doi")


def normalizados() -> list[RegistroNormalizado]:
    return [
        RegistroNormalizado(
            fuente="fuente-a",
            formato="ris",
            archivo="exportacion-1.ris",
            posicion=1,
            tipo_id_fuente="doi",
            id_fuente="10.5555/miel.1",
            titulo="Fermentación de mieles: un estudio ficticio",
            autores=("Pérez, Ana", "Gómez, Luis"),
            anio=2021,
            doi="10.5555/miel.1",
            resumen=RESUMEN,
            palabras_clave_autor=("miel",),
            otros={"Y2": "no volátil"},
        ),
        RegistroNormalizado(
            fuente="fuente-a",
            formato="ris",
            archivo="exportacion-1.ris",
            posicion=9,
            titulo="=SUMA(1;2) no es una fórmula, es un título",
            autores=(),
            anio=None,
        ),
    ]


def registros() -> list[Registro]:
    return construir_registros("imp-0004", normalizados())


# ------------------------------------------------------------------ JSONL


def test_el_jsonl_tiene_una_linea_de_json_canonico_por_registro() -> None:
    contenido = serializar_registros_jsonl(registros(), CAMPOS)

    assert contenido.endswith(b"\n")
    lineas = contenido.decode("utf-8").split("\n")[:-1]
    assert len(lineas) == 2
    primero = json.loads(lineas[0])
    assert lineas[0] == json.dumps(
        primero, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    assert primero["id"] == "imp-0004-00001"
    assert primero["autores"] == ["Pérez, Ana", "Gómez, Luis"]
    assert set(primero) == {*CAMPOS_SIEMPRE_VERSIONADOS, "hash_completo", *CAMPOS}


def test_el_jsonl_usa_utf8_con_lf_y_sin_escapar_caracteres_no_ascii() -> None:
    contenido = serializar_registros_jsonl(registros(), CAMPOS)

    assert b"\r" not in contenido
    assert not contenido.startswith(b"\xef\xbb\xbf")
    assert "Fermentación".encode() in contenido
    assert b"\\u" not in contenido


def test_el_jsonl_no_contiene_resumen_ni_campos_no_habilitados() -> None:
    contenido = serializar_registros_jsonl(registros(), (*CAMPOS, "resumen", "otros")).decode()

    assert RESUMEN not in contenido
    assert "resumen" not in contenido
    assert "palabras_clave" not in contenido
    assert "no volátil" not in contenido


def test_el_jsonl_es_determinista() -> None:
    assert serializar_registros_jsonl(registros(), CAMPOS) == serializar_registros_jsonl(
        registros(), CAMPOS
    )


def test_el_jsonl_coincide_con_los_bytes_de_referencia() -> None:
    """Fija los bytes: la integración continua los compara en Windows y en Ubuntu."""
    (primero,) = construir_registros("imp-0004", normalizados()[1:])
    contenido = serializar_registros_jsonl([primero], ("titulo", "anio"))

    esperado = (
        '{"anio":null,"archivo":"exportacion-1.ris","formato":"ris","fuente":"fuente-a",'
        f'"hash_completo":"{primero.hash_completo}","id":"imp-0004-00001",'
        '"id_importacion":"imp-0004","posicion":9,'
        '"titulo":"=SUMA(1;2) no es una fórmula, es un título"}\n'
    ).encode()
    assert contenido == esperado


def test_un_jsonl_sin_registros_esta_vacio() -> None:
    assert serializar_registros_jsonl([], CAMPOS) == b""


# -------------------------------------------------------------------- CSV


def filas(contenido: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(contenido.decode("utf-8"), newline="")))


def test_el_csv_tiene_columnas_fijas_en_el_orden_del_esquema() -> None:
    jsonl = serializar_registros_jsonl(registros(), CAMPOS)

    cabecera, *datos = filas(serializar_vista_csv(jsonl))

    assert tuple(cabecera) == COLUMNAS_CSV
    assert len(datos) == 2
    assert all(len(fila) == len(COLUMNAS_CSV) for fila in datos)


def test_las_columnas_del_csv_son_las_del_registro_versionable() -> None:
    assert set(COLUMNAS_CSV) == {
        *CAMPOS_SIEMPRE_VERSIONADOS,
        "hash_completo",
        "tipo_id_fuente",
        *CAMPOS_HABILITABLES,
    }
    assert len(COLUMNAS_CSV) == len(set(COLUMNAS_CSV))


def test_el_csv_une_los_autores_y_deja_vacio_lo_que_no_se_versiono() -> None:
    jsonl = serializar_registros_jsonl(registros(), CAMPOS)

    cabecera, primera, segunda = filas(serializar_vista_csv(jsonl))
    celda = dict(zip(cabecera, primera, strict=True))

    assert celda["autores"] == "Pérez, Ana; Gómez, Luis"
    assert celda["anio"] == "2021"
    assert celda["posicion"] == "1"
    assert celda["volumen"] == ""  # no habilitado
    assert celda["id_fuente"] == ""  # no habilitado
    assert dict(zip(cabecera, segunda, strict=True))["anio"] == ""  # habilitado, sin valor


def test_el_csv_usa_utf8_sin_bom_y_lf() -> None:
    contenido = serializar_vista_csv(serializar_registros_jsonl(registros(), CAMPOS))

    assert not contenido.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in contenido
    assert contenido.endswith(b"\n")
    assert "Fermentación".encode() in contenido


def test_una_celda_que_empieza_por_igual_no_se_altera() -> None:
    contenido = serializar_vista_csv(serializar_registros_jsonl(registros(), CAMPOS))

    cabecera, _, segunda = filas(contenido)

    assert dict(zip(cabecera, segunda, strict=True))["titulo"] == (
        "=SUMA(1;2) no es una fórmula, es un título"
    )


def test_el_csv_es_derivado_y_determinista() -> None:
    jsonl = serializar_registros_jsonl(registros(), CAMPOS)

    assert serializar_vista_csv(jsonl) == serializar_vista_csv(jsonl)


def test_el_csv_de_un_jsonl_vacio_solo_tiene_la_cabecera() -> None:
    assert serializar_vista_csv(b"") == (",".join(COLUMNAS_CSV) + "\n").encode()


def test_una_clave_sin_columna_en_el_jsonl_es_un_error() -> None:
    with pytest.raises(ValueError, match="línea 1.*inventado"):
        serializar_vista_csv(b'{"id":"imp-0001-00001","inventado":1}\n')


# --------------------------------------------------------------- archivos


def test_escribir_el_jsonl_y_el_csv_devuelve_el_hash_de_lo_escrito(tmp_path: Path) -> None:
    carpeta = tmp_path / "importaciones" / "imp-0004"
    ruta_jsonl = carpeta / "registros.jsonl"
    ruta_csv = carpeta / "registros.csv"

    hash_jsonl = escribir_registros_jsonl(ruta_jsonl, registros(), CAMPOS)
    hash_csv = escribir_vista_csv(ruta_csv, ruta_jsonl.read_bytes())

    assert ruta_jsonl.read_bytes() == serializar_registros_jsonl(registros(), CAMPOS)
    assert hash_jsonl == hash_bytes(ruta_jsonl.read_bytes())
    assert ruta_csv.read_bytes() == serializar_vista_csv(ruta_jsonl.read_bytes())
    assert hash_csv == hash_bytes(ruta_csv.read_bytes())


def test_escribir_dos_veces_da_los_mismos_bytes(tmp_path: Path) -> None:
    ruta = tmp_path / "registros.jsonl"

    primero = escribir_registros_jsonl(ruta, registros(), CAMPOS)
    bytes_primero = ruta.read_bytes()
    segundo = escribir_registros_jsonl(ruta, registros(), CAMPOS)

    assert primero == segundo
    assert ruta.read_bytes() == bytes_primero
    assert list(tmp_path.glob(".*tmp")) == []  # sin temporales
