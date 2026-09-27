"""Pruebas de los comandos del ciclo de vida del protocolo en la CLI (ADR-0008, punto 26)."""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import (
    construir_analizador,
    ejecutar_decision_confirmar,
    ejecutar_decision_registrar,
    ejecutar_protocolo_aprobar,
    ejecutar_protocolo_enmendar,
    ejecutar_protocolo_validar,
    main,
)
from agentresearch.trazabilidad import hash_archivo

from .apoyo import TerminalSimulada, aprobar_protocolo, reemplazar_en, reloj_incremental


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


def test_validar_muestra_el_registro_y_su_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    resultado = aprobar_protocolo(protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_protocolo_validar(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "(vigente, versión 1.0.0)" in salida
    assert f"registro: protocolo/eventos.jsonl (1 eventos, anclaje {resultado.anclaje})" in salida


# --- protocolo enmendar ----------------------------------------------------------------


@pytest.fixture
def protocolo_editado(protocolo_de_estudio: Path) -> Path:
    """Protocolo aprobado y luego editado, pendiente de enmienda."""
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    return protocolo_de_estudio


def test_enmendar_imprime_el_resultado(
    protocolo_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_enmendar(
        protocolo_editado,
        "menor",
        "investigador-1",
        justificacion="j",
        efecto_esperado="e",
        terminal=TerminalSimulada(["enmendar 1.1.0"]),
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "protocolo enmendado: protocolo/protocolo.yaml (versión 1.0.0 → 1.1.0)" in salida
    assert "evento: evt-000002 (protocolo_enmendado)" in salida


def test_enmendar_en_json(protocolo_editado: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_enmendar(
        protocolo_editado,
        "mayor",
        "investigador-1",
        justificacion="j",
        efecto_esperado="e",
        como_json=True,
        terminal=TerminalSimulada(["enmendar 2.0.0"]),
    )

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo enmendar"
    assert datos["resultado"]["version_protocolo"] == "2.0.0"
    assert datos["resultado"]["datos"]["cambios"] == [
        {"ruta": "seleccion.tamano_lote_llm", "operacion": "modificado", "antes": 25, "despues": 30}
    ]


def test_enmendar_sin_terminal_devuelve_uno(
    protocolo_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_enmendar(
        protocolo_editado,
        "menor",
        "investigador-1",
        justificacion="j",
        efecto_esperado="e",
        terminal=TerminalSimulada(interactiva=False),
    )

    assert codigo == 1
    assert "exige una terminal interactiva" in capsys.readouterr().out


def test_simular_en_texto_sin_nivel(
    protocolo_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_enmendar(protocolo_editado, simular=True)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert salida == (
        "simulación de enmienda: protocolo/protocolo.yaml\n"
        "versión registrada: 1.0.0 (evt-000001)\n"
        "versión siguiente: 1.1.0 si es menor, 2.0.0 si es mayor\n"
        "Cambios: 1\n"
        "  - seleccion.tamano_lote_llm: 25 → 30\n"
    )


def test_simular_en_texto_con_nivel_y_problemas(
    protocolo_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reemplazar_en(protocolo_editado, 'version_protocolo: "1.0.0"', 'version_protocolo: "9.0.0"')

    codigo = ejecutar_protocolo_enmendar(protocolo_editado, "menor", simular=True)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "versión siguiente: 1.1.0 (nivel menor)" in salida
    assert "impedirían enmendar:\n  - la versión de protocolo/protocolo.yaml (9.0.0)" in salida


def test_simular_en_texto_lista_las_advertencias_nuevas(
    protocolo_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reemplazar_en(protocolo_editado, "tamano: 20", "tamano: 0")

    codigo = ejecutar_protocolo_enmendar(protocolo_editado, "menor", simular=True)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert (
        "advertencias nuevas (no activas en la versión 1.0.0), que exigirán justificación:\n"
        "  - advertencia P-A09"
    ) in salida


def test_simular_en_json(protocolo_editado: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_enmendar(protocolo_editado, "menor", simular=True, como_json=True)

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo enmendar --simular"
    assert datos["exito"] is True
    assert datos["resultado"]["version_siguiente"] == "1.1.0"
    assert datos["resultado"]["se_puede_enmendar"] is True


def test_simular_un_borrador_devuelve_uno(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_enmendar(protocolo_de_estudio, simular=True)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert salida.startswith("protocolo enmendar --simular: no se pudo simular\n")
    assert "el protocolo no está aprobado" in salida


def test_el_analizador_de_enmendar(tmp_path: Path) -> None:
    argumentos = construir_analizador().parse_args(
        [
            "protocolo",
            "enmendar",
            "--nivel",
            "mayor",
            "--enmendado-por",
            "investigador-1",
            "--archivo-enmienda",
            "e.json",
            "--simular",
            "--json",
        ]
    )

    assert argumentos.nivel == "mayor"
    assert argumentos.enmendado_por == "investigador-1"
    assert argumentos.archivo_enmienda == Path("e.json")
    assert argumentos.simular is True
    assert argumentos.como_json is True


def test_el_analizador_rechaza_el_nivel_parche(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        construir_analizador().parse_args(["protocolo", "enmendar", "--nivel", "parche"])

    assert salida.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_main_enmendar_simulado(
    protocolo_editado: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["agentresearch", "protocolo", "enmendar", str(protocolo_editado), "--simular"]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert "versión siguiente: 1.1.0 si es menor" in capsys.readouterr().out


# --- protocolo decision registrar | confirmar ------------------------------------------


def _archivo_decision(tmp_path: Path, **cambios: Any) -> Path:
    opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
    decision: dict[str, Any] = {
        "id_decision": "O1",
        "tema": "Tema",
        "pregunta": "¿Pregunta?",
        "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
        "elegida": "A",
        "justificacion": "Justificación",
        "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
        "decidido_por": {"tipo": "humano", "id": "investigador-1"},
    }
    decision.update(cambios)
    archivo = tmp_path / f"{decision['id_decision']}.json"
    archivo.write_text(json.dumps(decision, ensure_ascii=False), encoding="utf-8")
    return archivo


def test_decision_registrar_imprime_el_resultado(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "decisión O1 registrada como propuesta (evt-000001); queda pendiente de confirmar" in (
        salida
    )
    assert "decision confirmar --confirmado-por <id>" in salida


def test_decision_registrar_en_json(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_decision_registrar(
        _archivo_decision(tmp_path), protocolo_de_estudio, como_json=True
    )

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo decision registrar"
    assert datos["resultado"]["estado"] == "pendiente"
    assert datos["resultado"]["datos"]["decision"]["id_decision"] == "O1"


def test_decision_registrar_rechazada_devuelve_uno(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = _archivo_decision(tmp_path, decidido_por={"tipo": "llm", "id": "claude"})

    codigo = ejecutar_decision_registrar(archivo, protocolo_de_estudio, como_json=True)

    datos = _json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["errores"] == [
        "decidido_por debe ser un humano: el LLM propone, pero decide el investigador "
        "(CLAUDE.md, regla 1)"
    ]


def test_decision_confirmar_imprime_el_resultado(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)
    ejecutar_decision_registrar(
        _archivo_decision(tmp_path, id_decision="O1b", reemplaza="O1"), protocolo_de_estudio
    )
    ejecutar_decision_registrar(
        _archivo_decision(
            tmp_path, id_decision="O2", decidido_por={"tipo": "humano", "id": "investigador-2"}
        ),
        protocolo_de_estudio,
    )
    capsys.readouterr()
    terminal = TerminalSimulada(["confirmar 1"])

    codigo = ejecutar_decision_confirmar(
        "investigador-1", protocolo_de_estudio, terminal=terminal, reloj=reloj_incremental()
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "decisiones confirmadas por investigador-1: O1b" in salida
    assert "anclaje: evt-000004@sha256:" in salida
    assert "pendientes de otros revisores: O2" in salida
    assert "  reemplaza a: O1" in terminal.texto


def test_decision_confirmar_sin_pendientes(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_decision_confirmar(
        "investigador-1", protocolo_de_estudio, terminal=TerminalSimulada(interactiva=False)
    )

    assert codigo == 0
    assert capsys.readouterr().out == "no hay decisiones pendientes de investigador-1\n"


def test_decision_confirmar_en_json(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_decision_confirmar(
        "investigador-1",
        protocolo_de_estudio,
        como_json=True,
        terminal=TerminalSimulada(["confirmar 1"]),
    )

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo decision confirmar"
    assert datos["resultado"]["confirmadas"] == ["O1"]


def test_el_analizador_de_decisiones(tmp_path: Path) -> None:
    registrar = construir_analizador().parse_args(
        ["protocolo", "decision", "registrar", "--archivo", "d.json", "--protocolo", "p.yaml"]
    )
    confirmar = construir_analizador().parse_args(
        ["protocolo", "decision", "confirmar", "--confirmado-por", "investigador-1", "--json"]
    )

    assert registrar.accion == "registrar"
    assert registrar.archivo == Path("d.json")
    assert registrar.protocolo == Path("p.yaml")
    assert confirmar.accion == "confirmar"
    assert confirmar.confirmado_por == "investigador-1"
    assert confirmar.protocolo == Path("protocolo") / "protocolo.yaml"
    assert confirmar.como_json is True


@pytest.mark.parametrize(
    "argumentos",
    [
        ["protocolo", "decision"],
        ["protocolo", "decision", "registrar"],
        ["protocolo", "decision", "confirmar"],
    ],
)
def test_el_analizador_exige_la_accion_y_sus_opciones(argumentos: list[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        construir_analizador().parse_args(argumentos)

    assert salida.value.code == 2


def test_main_decision_registrar_y_confirmar_sin_terminal(
    protocolo_de_estudio: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archivo = _archivo_decision(tmp_path)
    base = ["agentresearch", "protocolo", "decision"]
    protocolo = ["--protocolo", str(protocolo_de_estudio)]

    monkeypatch.setattr(sys, "argv", [*base, "registrar", "--archivo", str(archivo), *protocolo])
    with pytest.raises(SystemExit) as registro:
        main()
    monkeypatch.setattr(
        sys, "argv", [*base, "confirmar", "--confirmado-por", "investigador-1", *protocolo]
    )
    with pytest.raises(SystemExit) as confirmacion:
        main()

    assert registro.value.code == 0
    assert confirmacion.value.code == 1
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
