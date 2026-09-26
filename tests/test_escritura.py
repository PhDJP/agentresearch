"""Pruebas de la escritura atómica de archivos."""

import os
from pathlib import Path

import pytest

from agentresearch.trazabilidad import escribir_atomico


def test_escribe_el_contenido_exacto(tmp_path: Path) -> None:
    ruta = tmp_path / "archivo.yaml"

    escribir_atomico(ruta, "línea con tilde\n".encode())

    assert ruta.read_bytes() == "línea con tilde\n".encode()


def test_reemplaza_un_archivo_existente(tmp_path: Path) -> None:
    ruta = tmp_path / "archivo.yaml"
    ruta.write_bytes(b"viejo\n")

    escribir_atomico(ruta, b"nuevo\n")

    assert ruta.read_bytes() == b"nuevo\n"


def test_crea_el_directorio_si_no_existe(tmp_path: Path) -> None:
    ruta = tmp_path / "versiones" / "1.0.0.yaml"

    escribir_atomico(ruta, b"contenido\n")

    assert ruta.read_bytes() == b"contenido\n"


def test_no_deja_temporales(tmp_path: Path) -> None:
    escribir_atomico(tmp_path / "archivo.yaml", b"contenido\n")

    assert [p.name for p in tmp_path.iterdir()] == ["archivo.yaml"]


def test_conserva_el_original_y_borra_el_temporal_si_falla_el_reemplazo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = tmp_path / "archivo.yaml"
    ruta.write_bytes(b"original\n")

    def _reemplazo_fallido(origen: object, destino: object) -> None:
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(os, "replace", _reemplazo_fallido)

    with pytest.raises(OSError, match="simulado"):
        escribir_atomico(ruta, b"nuevo\n")

    assert ruta.read_bytes() == b"original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["archivo.yaml"]


def test_sincroniza_el_temporal_antes_de_reemplazar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orden: list[str] = []
    fsync_original = os.fsync
    replace_original = os.replace

    def _fsync(descriptor: int) -> None:
        orden.append("fsync")
        fsync_original(descriptor)

    def _replace(origen: str, destino: str) -> None:
        orden.append("replace")
        replace_original(origen, destino)

    monkeypatch.setattr(os, "fsync", _fsync)
    monkeypatch.setattr(os, "replace", _replace)

    escribir_atomico(tmp_path / "archivo.yaml", b"contenido\n")

    assert orden == ["fsync", "replace"]
