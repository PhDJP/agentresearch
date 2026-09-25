"""Pruebas de la interfaz de línea de comandos."""

import pytest

from agentresearch.cli import construir_analizador


def test_version_muestra_version_del_paquete(capsys: pytest.CaptureFixture[str]) -> None:
    """`--version` debe imprimir el nombre y la versión del paquete, y salir con código 0."""
    analizador = construir_analizador()

    with pytest.raises(SystemExit) as excepcion:
        analizador.parse_args(["--version"])

    assert excepcion.value.code == 0
    salida = capsys.readouterr().out
    assert salida.startswith("agentresearch ")
