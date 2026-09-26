"""Pruebas de los comandos del ciclo de vida del protocolo en la CLI (ADR-0008, punto 26)."""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import construir_analizador, ejecutar_protocolo_aprobar, main
from agentresearch.trazabilidad import hash_archivo

from .apoyo import TerminalSimulada, reemplazar_en, reloj_incremental


def _json(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    salida = capsys.readouterr().out
    assert salida.isascii()
    datos: dict[str, Any] = json.loads(salida)
    return datos


# --- protocolo aprobar ---------------------------------------------------------------


def test_aprobar_imprime_el_resultado(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_aprobar(
        protocolo_de_estudio,
        "investigador-1",
        terminal=TerminalSimulada(["aprobar 1.0.0"]),
        reloj=reloj_incremental(),
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "protocolo aprobado: protocolo/protocolo.yaml (versión 0.1.0 → 1.0.0)" in salida
    assert f"hash: {hash_archivo(protocolo_de_estudio)}" in salida
    assert "evento: evt-000001 (protocolo_aprobado)" in salida
    assert "copia de la versión: protocolo/versiones/1.0.0.yaml" in salida
    assert "anclaje: evt-000001@sha256:" in salida


def test_aprobar_en_json(protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_aprobar(
        protocolo_de_estudio,
        "investigador-1",
        como_json=True,
        terminal=TerminalSimulada(["aprobar 1.0.0"]),
    )

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo aprobar"
    assert datos["exito"] is True
    assert datos["errores"] == []
    assert datos["version_agente"] == version("agentresearch")
    resultado = datos["resultado"]
    assert isinstance(resultado, dict)
    assert resultado["version_protocolo"] == "1.0.0"
    assert resultado["evento"] == "evt-000001"
    assert resultado["tipo_evento"] == "protocolo_aprobado"
    assert resultado["hash_protocolo"] == hash_archivo(protocolo_de_estudio)
    assert resultado["datos"]["aprobado_por"] == {"tipo": "humano", "id": "investigador-1"}


def test_aprobar_con_errores_devuelve_uno(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 0")

    codigo = ejecutar_protocolo_aprobar(
        protocolo_de_estudio, "investigador-1", terminal=TerminalSimulada(["aprobar 1.0.0"])
    )

    salida = capsys.readouterr().out
    assert codigo == 1
    assert salida.startswith("protocolo aprobar: no se pudo completar\n  - error P-E08")


def test_aprobar_con_errores_en_json(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_aprobar(
        protocolo_de_estudio,
        "claude",
        como_json=True,
        terminal=TerminalSimulada(["aprobar 1.0.0"]),
    )

    datos = _json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["resultado"] is None
    [error] = datos["errores"]
    assert "es un revisor de tipo llm" in error


def test_aprobar_cancelado_devuelve_uno(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_aprobar(
        protocolo_de_estudio, "investigador-1", terminal=TerminalSimulada(["no"])
    )

    salida = capsys.readouterr().out
    assert codigo == 1
    assert salida == (
        "protocolo aprobar: cancelado\n  - cancelado: no se escribió «aprobar 1.0.0»\n"
    )


def test_el_analizador_exige_aprobado_por(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        construir_analizador().parse_args(["protocolo", "aprobar"])

    assert salida.value.code == 2
    assert "--aprobado-por" in capsys.readouterr().err


def test_el_analizador_de_aprobar(tmp_path: Path) -> None:
    argumentos = construir_analizador().parse_args(
        [
            "protocolo",
            "aprobar",
            str(tmp_path / "p.yaml"),
            "--aprobado-por",
            "investigador-1",
            "--justificaciones",
            "j.json",
            "--json",
        ]
    )

    assert argumentos.ruta == tmp_path / "p.yaml"
    assert argumentos.aprobado_por == "investigador-1"
    assert argumentos.justificaciones == Path("j.json")
    assert argumentos.como_json is True


def test_main_aprobar_sin_terminal_devuelve_uno(
    protocolo_de_estudio: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentresearch",
            "protocolo",
            "aprobar",
            str(protocolo_de_estudio),
            "--aprobado-por",
            "investigador-1",
        ],
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 1
    assert "exige una terminal interactiva" in capsys.readouterr().out


# --- Subproceso: la barrera frente a las herramientas del LLM -----------------------


def _aprobar_por_subproceso(
    ruta: Path, stdin: int | None = None, entrada: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "agentresearch",
            "protocolo",
            "aprobar",
            str(ruta),
            "--aprobado-por",
            "investigador-1",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # la consola del proceso hijo puede no usar UTF-8
        check=False,
        timeout=60,
        stdin=stdin,
        input=entrada,
    )


def test_aprobar_por_subproceso_con_la_entrada_nula_se_niega(protocolo_de_estudio: Path) -> None:
    original = protocolo_de_estudio.read_bytes()

    resultado = _aprobar_por_subproceso(protocolo_de_estudio, stdin=subprocess.DEVNULL)

    assert resultado.returncode == 1
    assert "exige una terminal interactiva" in resultado.stdout
    assert protocolo_de_estudio.read_bytes() == original


def test_aprobar_por_subproceso_con_la_frase_por_tuberia_se_niega(
    protocolo_de_estudio: Path,
) -> None:
    original = protocolo_de_estudio.read_bytes()

    resultado = _aprobar_por_subproceso(protocolo_de_estudio, entrada="aprobar 1.0.0\n")

    assert resultado.returncode == 1
    assert "exige una terminal interactiva" in resultado.stdout
    assert protocolo_de_estudio.read_bytes() == original
    assert not (protocolo_de_estudio.parent / "eventos.jsonl").exists()
