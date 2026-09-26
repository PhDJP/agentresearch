"""Pruebas de integracion por subproceso, usando el modulo instalado."""

import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

from agentresearch.trazabilidad import RegistroEncadenado


def test_el_comando_agentresearch_esta_registrado_como_punto_de_entrada() -> None:
    puntos = entry_points(group="console_scripts")
    nombres = {punto.name for punto in puntos}

    assert "agentresearch" in nombres


def test_modulo_muestra_la_version_por_subproceso() -> None:
    resultado = subprocess.run(
        [sys.executable, "-m", "agentresearch", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 0
    assert resultado.stdout.startswith("agentresearch ")


def test_modulo_verifica_una_cadena_integra_por_subproceso(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {"clave": "valor"})

    resultado = subprocess.run(
        [sys.executable, "-m", "agentresearch", "registro", "verificar", str(archivo)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 0
    assert "integro" in resultado.stdout


def test_modulo_detecta_una_cadena_rota_por_subproceso(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {})
    contenido = archivo.read_text(encoding="utf-8").replace('"uno"', '"otro"')
    archivo.write_text(contenido, encoding="utf-8", newline="\n")

    resultado = subprocess.run(
        [sys.executable, "-m", "agentresearch", "registro", "verificar", str(archivo)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 1
    assert "invalido" in resultado.stdout


def test_modulo_rechaza_argumentos_invalidos_por_subproceso() -> None:
    resultado = subprocess.run(
        [sys.executable, "-m", "agentresearch", "registro", "verificar"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode != 0
