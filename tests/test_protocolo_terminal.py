"""Pruebas de la detección de consola y de la terminal del sistema (ADR-0008, punto 11)."""

import io
import os
import sys
from pathlib import Path

import pytest

from agentresearch.protocolo.terminal import TerminalDelSistema, es_consola_interactiva


def test_el_dispositivo_nulo_no_es_una_consola() -> None:
    """En Windows, `isatty()` da verdadero con NUL; la detección no debe aceptarlo."""
    with open(os.devnull, encoding="utf-8") as nulo:
        assert es_consola_interactiva(nulo) is False


def test_una_tuberia_no_es_una_consola() -> None:
    lectura, escritura = os.pipe()
    try:
        with os.fdopen(lectura, encoding="utf-8") as flujo:
            assert es_consola_interactiva(flujo) is False
    finally:
        os.close(escritura)


def test_un_archivo_no_es_una_consola(tmp_path: Path) -> None:
    ruta = tmp_path / "entrada.txt"
    ruta.write_text("aprobar 1.0.0\n", encoding="utf-8")

    with ruta.open(encoding="utf-8") as flujo:
        assert es_consola_interactiva(flujo) is False


def test_un_flujo_sin_descriptor_no_es_una_consola() -> None:
    assert es_consola_interactiva(io.StringIO("aprobar 1.0.0\n")) is False


def test_un_flujo_cerrado_no_es_una_consola(tmp_path: Path) -> None:
    ruta = tmp_path / "entrada.txt"
    ruta.write_text("", encoding="utf-8")
    flujo = ruta.open(encoding="utf-8")
    flujo.close()

    assert es_consola_interactiva(flujo) is False


@pytest.mark.skipif(sys.platform != "win32", reason="GetConsoleMode solo existe en Windows")
def test_en_windows_un_descriptor_no_valido_no_es_una_consola() -> None:
    from agentresearch.protocolo.terminal import _es_consola_de_windows

    assert _es_consola_de_windows(9999) is False


def test_la_terminal_del_sistema_no_es_interactiva_bajo_pytest() -> None:
    assert TerminalDelSistema().es_interactiva() is False


def test_la_terminal_del_sistema_muestra_en_la_salida_de_errores(
    capsys: pytest.CaptureFixture[str],
) -> None:
    TerminalDelSistema().mostrar("resumen con tilde: versión")

    salida = capsys.readouterr()
    assert salida.out == ""
    assert salida.err == "resumen con tilde: versión\n"


def test_la_terminal_del_sistema_lee_una_linea(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("aprobar 1.0.0\r\nsobra\n"))

    respuesta = TerminalDelSistema().preguntar("Escriba: ")

    assert respuesta == "aprobar 1.0.0"
    assert capsys.readouterr().err == "Escriba: "


def test_la_terminal_del_sistema_devuelve_none_al_final_de_la_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    assert TerminalDelSistema().preguntar("Escriba: ") is None
