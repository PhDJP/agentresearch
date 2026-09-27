"""Pruebas de la escritura atómica de archivos."""

import os
from pathlib import Path

import pytest

from agentresearch.trazabilidad import RegistroEncadenado, escribir_atomico, escritura, registro
from agentresearch.trazabilidad.escritura import sincronizar_directorio


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
    monkeypatch.setattr(escritura, "sincronizar_directorio", lambda _d: orden.append("directorio"))

    escribir_atomico(tmp_path / "archivo.yaml", b"contenido\n")

    assert orden == ["fsync", "replace", "directorio"]


def test_en_posix_sincroniza_el_directorio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: list[tuple[str, object]] = []

    def _abrir(ruta: object, _banderas: int) -> int:
        llamadas.append(("open", ruta))
        return 7

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "open", _abrir)
    monkeypatch.setattr(os, "fsync", lambda descriptor: llamadas.append(("fsync", descriptor)))
    monkeypatch.setattr(os, "close", lambda descriptor: llamadas.append(("close", descriptor)))

    sincronizar_directorio(tmp_path)

    assert llamadas == [("open", tmp_path), ("fsync", 7), ("close", 7)]


def test_en_posix_cierra_el_directorio_aunque_falle_la_sincronizacion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cerrados: list[int] = []

    def _fsync_fallido(_descriptor: int) -> None:
        raise OSError("sin soporte (simulado)")

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "open", lambda _ruta, _banderas: 7)
    monkeypatch.setattr(os, "fsync", _fsync_fallido)
    monkeypatch.setattr(os, "close", cerrados.append)

    with pytest.raises(OSError, match="simulado"):
        sincronizar_directorio(tmp_path)

    assert cerrados == [7]


def test_en_windows_no_sincroniza_el_directorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_debe_abrir(*_argumentos: object) -> int:
        raise AssertionError("no debe abrir el directorio")

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(os, "open", _no_debe_abrir)

    sincronizar_directorio(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="solo POSIX admite sincronizar un directorio")
def test_sincroniza_un_directorio_real_en_posix(tmp_path: Path) -> None:
    sincronizar_directorio(tmp_path)


def test_el_registro_sincroniza_el_directorio_solo_al_crear_el_archivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sincronizados: list[object] = []
    monkeypatch.setattr(registro, "sincronizar_directorio", sincronizados.append)
    ruta = tmp_path / "eventos.jsonl"

    RegistroEncadenado(ruta).agregar("prueba", {"n": 1})
    RegistroEncadenado(ruta).agregar("prueba", {"n": 2})

    assert sincronizados == [tmp_path]
