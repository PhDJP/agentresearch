"""Pruebas de la lectura de bytes: codificación, fin de línea, hash y L-E01."""

from pathlib import Path

import pytest

from agentresearch.importacion.entrada import ErrorDeArchivo, cargar, dividir_lineas
from agentresearch.trazabilidad import hash_bytes


def _escribir(ruta: Path, datos: bytes) -> Path:
    ruta.write_bytes(datos)
    return ruta


def test_utf8_sin_bom(tmp_path: Path) -> None:
    carga = cargar(_escribir(tmp_path / "a.txt", "uno\ndós\n".encode()))
    assert carga.hallazgo is None
    assert carga.texto == "uno\ndós\n"
    assert carga.lineas == ("uno", "dós")
    assert carga.nombre == "a.txt"


def test_utf8_con_bom_se_descarta_el_bom_y_el_hash_es_del_archivo(tmp_path: Path) -> None:
    datos = b"\xef\xbb\xbfuno\n"
    carga = cargar(_escribir(tmp_path / "a.txt", datos))
    assert carga.texto == "uno\n"
    assert carga.hash == hash_bytes(datos)


@pytest.mark.parametrize(
    ("datos", "esperadas"),
    [
        (b"a\r\nb\r\nc", ("a", "b", "c")),
        (b"a\nb\nc\n", ("a", "b", "c")),
        (b"a\rb\rc\r", ("a", "b", "c")),
        (b"a\n\nb\n", ("a", "", "b")),
        (b"", ()),
    ],
)
def test_fin_de_linea_lf_crlf_y_cr(
    tmp_path: Path, datos: bytes, esperadas: tuple[str, ...]
) -> None:
    assert cargar(_escribir(tmp_path / "a.txt", datos)).lineas == esperadas


def test_dividir_lineas_no_parte_por_separadores_unicode() -> None:
    # U+2028 no es un terminador de línea física: un editor no lo cuenta como salto.
    assert dividir_lineas("a b\nc") == ("a b", "c")


def test_l_e01_latin1_informa_la_linea_del_primer_byte_invalido(tmp_path: Path) -> None:
    datos = b"uno\ndos\ntres \xe9 cuatro\n"
    carga = cargar(_escribir(tmp_path / "a.txt", datos))
    assert carga.texto is None
    assert carga.hallazgo is not None
    assert carga.hallazgo.regla == "L-E01"
    assert carga.hallazgo.severidad == "error"
    assert carga.hallazgo.linea == 3
    assert carga.hash == hash_bytes(datos)


def test_l_e01_utf16_con_bom(tmp_path: Path) -> None:
    carga = cargar(_escribir(tmp_path / "a.txt", "uno\ndos\n".encode("utf-16")))
    assert carga.hallazgo is not None
    assert carga.hallazgo.regla == "L-E01"
    assert carga.hallazgo.linea == 1


def test_l_e01_utf16_sin_bom_por_bytes_nulos(tmp_path: Path) -> None:
    datos = "uno\ndos\n".encode("utf-16-le")
    carga = cargar(_escribir(tmp_path / "a.txt", datos))
    assert carga.hallazgo is not None
    assert carga.hallazgo.regla == "L-E01"
    assert carga.hallazgo.linea is not None


def test_el_mensaje_de_l_e01_no_contiene_el_contenido(tmp_path: Path) -> None:
    carga = cargar(_escribir(tmp_path / "a.txt", b"secreto-licenciado \xe9\n"))
    assert carga.hallazgo is not None
    assert "secreto" not in carga.hallazgo.mensaje


def test_archivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ErrorDeArchivo) as error:
        cargar(tmp_path / "no_existe.txt")
    assert error.value.ruta.name == "no_existe.txt"


def test_una_carpeta_no_es_un_archivo(tmp_path: Path) -> None:
    with pytest.raises(ErrorDeArchivo):
        cargar(tmp_path)
