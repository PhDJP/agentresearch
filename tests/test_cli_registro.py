"""Pruebas del subcomando `registro verificar` de la CLI (sin subproceso)."""

from pathlib import Path

import pytest

from agentresearch.cli import construir_analizador, ejecutar_registro_verificar
from agentresearch.trazabilidad import RegistroEncadenado


def test_ejecutar_registro_verificar_devuelve_cero_si_es_integro(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {})

    assert ejecutar_registro_verificar(archivo) == 0


def test_ejecutar_registro_verificar_devuelve_uno_si_esta_roto(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {})
    contenido = archivo.read_text(encoding="utf-8").replace('"uno"', '"otro"')
    archivo.write_text(contenido, encoding="utf-8", newline="\n")

    assert ejecutar_registro_verificar(archivo) == 1


def test_ejecutar_registro_verificar_devuelve_uno_si_el_archivo_no_existe(
    tmp_path: Path,
) -> None:
    assert ejecutar_registro_verificar(tmp_path / "no_existe.jsonl") == 1


def test_ejecutar_registro_verificar_imprime_mensaje_claro_si_no_existe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_registro_verificar(tmp_path / "no_existe.jsonl")

    salida = capsys.readouterr().out
    assert "no existe" in salida


def test_analizador_asigna_comando_y_subcomando_de_registro(tmp_path: Path) -> None:
    analizador = construir_analizador()
    archivo = tmp_path / "eventos.jsonl"

    argumentos = analizador.parse_args(["registro", "verificar", str(archivo)])

    assert argumentos.comando == "registro"
    assert argumentos.subcomando == "verificar"
    assert argumentos.archivo == archivo


def test_analizador_exige_subcomando_de_registro() -> None:
    analizador = construir_analizador()

    with pytest.raises(SystemExit):
        analizador.parse_args(["registro"])


def test_analizador_rechaza_comando_desconocido() -> None:
    analizador = construir_analizador()

    with pytest.raises(SystemExit):
        analizador.parse_args(["comando-inexistente"])
