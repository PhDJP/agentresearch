"""Pruebas de las utilidades de hash."""

from pathlib import Path

from agentresearch.trazabilidad.hashes import hash_archivo, hash_texto


def test_hash_texto_tiene_el_formato_esperado() -> None:
    resultado = hash_texto("hola")
    assert resultado.startswith("sha256:")
    assert len(resultado) == len("sha256:") + 64


def test_hash_texto_es_determinista() -> None:
    assert hash_texto("hola") == hash_texto("hola")


def test_hash_texto_distingue_contenidos_distintos() -> None:
    assert hash_texto("hola") != hash_texto("chao")


def test_hash_archivo_coincide_con_hash_texto_del_mismo_contenido(tmp_path: Path) -> None:
    archivo = tmp_path / "datos.txt"
    archivo.write_text("contenido de prueba", encoding="utf-8", newline="\n")

    assert hash_archivo(archivo) == hash_texto("contenido de prueba")
