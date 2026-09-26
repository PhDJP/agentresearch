"""Pruebas del subcomando `registro verificar` de la CLI (sin subproceso)."""

from pathlib import Path

import pytest

from agentresearch.cli import construir_analizador, ejecutar_registro_verificar
from agentresearch.trazabilidad import Anclaje, RegistroEncadenado


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


def test_ejecutar_registro_verificar_muestra_el_anclaje_actual(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(archivo)
    registro.agregar("uno", {})

    assert ejecutar_registro_verificar(archivo) == 0

    assert f"anclaje actual: {registro.anclaje()}" in capsys.readouterr().out


def test_ejecutar_registro_verificar_con_anclaje_cumplido_devuelve_cero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(archivo)
    registro.agregar("uno", {})
    anclaje = registro.anclaje()

    assert ejecutar_registro_verificar(archivo, anclaje) == 0
    assert f"cumple el anclaje: {anclaje}" in capsys.readouterr().out


def test_ejecutar_registro_verificar_detecta_el_truncamiento_con_el_anclaje(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(archivo)
    registro.agregar("uno", {})
    registro.agregar("dos", {})
    anclaje = registro.anclaje()
    primera_linea = archivo.read_text(encoding="utf-8").splitlines()[0]
    archivo.write_text(primera_linea + "\n", encoding="utf-8", newline="\n")

    assert ejecutar_registro_verificar(archivo) == 0
    assert ejecutar_registro_verificar(archivo, anclaje) == 1
    assert "se eliminaron eventos del final" in capsys.readouterr().out


def test_analizador_interpreta_el_anclaje(tmp_path: Path) -> None:
    texto = "evt-000002@sha256:" + "a" * 64

    argumentos = construir_analizador().parse_args(
        ["registro", "verificar", str(tmp_path / "e.jsonl"), "--anclaje", texto]
    )

    assert argumentos.anclaje == Anclaje.desde_texto(texto)


def test_analizador_rechaza_un_anclaje_mal_formado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as salida:
        construir_analizador().parse_args(
            ["registro", "verificar", str(tmp_path / "e.jsonl"), "--anclaje", "evt-1"]
        )

    assert salida.value.code == 2
    assert "anclaje no válido" in capsys.readouterr().err
