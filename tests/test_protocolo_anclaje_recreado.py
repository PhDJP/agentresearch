"""Pruebas del anclaje que falta y se vuelve a crear (ADR-0008, punto 21)."""

import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import (
    ejecutar_decision_confirmar,
    ejecutar_decision_registrar,
    ejecutar_protocolo_enmendar,
    ejecutar_protocolo_historial,
    ejecutar_protocolo_validar,
)
from agentresearch.protocolo import RutasProtocolo, validar_archivo
from agentresearch.protocolo.aprobacion import enmendar
from agentresearch.protocolo.ciclo_de_vida import MENSAJE_ANCLAJE_RECREADO
from agentresearch.protocolo.decisiones import confirmar_decisiones, registrar_decision
from agentresearch.trazabilidad import RegistroEncadenado

from .apoyo import TerminalSimulada, aprobar_protocolo, reemplazar_en, reloj_incremental

NOTA_FALTA = "nota: falta protocolo/anclaje.json: mientras falte, no se detecta"


def _archivo_decision(tmp_path: Path, id_decision: str = "O1") -> Path:
    opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
    decision = {
        "id_decision": id_decision,
        "tema": "Tema",
        "pregunta": "¿Pregunta?",
        "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
        "elegida": "A",
        "justificacion": "Justificación",
        "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
        "decidido_por": {"tipo": "humano", "id": "investigador-1"},
    }
    archivo = tmp_path / f"{id_decision}.json"
    archivo.write_text(json.dumps(decision, ensure_ascii=False), encoding="utf-8")
    return archivo


def _sin_anclaje(ruta: Path) -> Path:
    """Aprueba el protocolo y elimina `anclaje.json`; devuelve su ruta."""
    aprobar_protocolo(ruta)
    anclaje = RutasProtocolo.desde(ruta).anclaje
    anclaje.unlink()
    return anclaje


def _json(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(capsys.readouterr().out)
    return datos


# --- Operaciones que recrean el anclaje ----------------------------------------------


def test_la_primera_aprobacion_crea_el_anclaje_sin_recrearlo(protocolo_de_estudio: Path) -> None:
    resultado = aprobar_protocolo(protocolo_de_estudio)

    assert resultado.anclaje_recreado is False
    assert resultado.como_dict()["anclaje_recreado"] is False


def test_una_operacion_con_el_anclaje_presente_no_lo_recrea(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    resultado = registrar_decision(protocolo_de_estudio, _archivo_decision(tmp_path))

    assert resultado.anclaje_recreado is False


def test_registrar_una_decision_recrea_el_anclaje_que_faltaba(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    anclaje = _sin_anclaje(protocolo_de_estudio)

    resultado = registrar_decision(protocolo_de_estudio, _archivo_decision(tmp_path))

    assert resultado.anclaje_recreado is True
    assert resultado.como_dict()["anclaje_recreado"] is True
    assert anclaje.is_file()
    assert str(resultado.anclaje) == str(
        RegistroEncadenado(anclaje.parent / "eventos.jsonl").anclaje()
    )


def test_confirmar_decisiones_recrea_el_anclaje_que_faltaba(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    registrar_decision(protocolo_de_estudio, _archivo_decision(tmp_path))
    RutasProtocolo.desde(protocolo_de_estudio).anclaje.unlink()

    resultado = confirmar_decisiones(
        protocolo_de_estudio, "investigador-1", TerminalSimulada(["confirmar 1"])
    )

    assert resultado.anclaje_recreado is True
    assert resultado.como_dict()["anclaje_recreado"] is True


def test_enmendar_recrea_el_anclaje_que_faltaba(protocolo_de_estudio: Path) -> None:
    anclaje = _sin_anclaje(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    resultado = enmendar(
        protocolo_de_estudio,
        "menor",
        "investigador-1",
        TerminalSimulada(["enmendar 1.1.0"]),
        justificacion="j",
        efecto_esperado="e",
        reloj=reloj_incremental(),
    )

    assert resultado.anclaje_recreado is True
    assert anclaje.is_file()


# --- Salida de los comandos ---------------------------------------------------------


def test_decision_registrar_informa_el_anclaje_recreado_en_texto(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)

    assert codigo == 0
    assert f"aviso: {MENSAJE_ANCLAJE_RECREADO}" in capsys.readouterr().out


def test_decision_registrar_informa_el_anclaje_recreado_en_json(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)
    capsys.readouterr()

    ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio, como_json=True)

    assert _json(capsys)["resultado"]["anclaje_recreado"] is True


def test_decision_confirmar_informa_el_anclaje_recreado(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)
    RutasProtocolo.desde(protocolo_de_estudio).anclaje.unlink()
    capsys.readouterr()

    ejecutar_decision_confirmar(
        "investigador-1", protocolo_de_estudio, terminal=TerminalSimulada(["confirmar 1"])
    )

    assert f"aviso: {MENSAJE_ANCLAJE_RECREADO}" in capsys.readouterr().out


def test_enmendar_informa_el_anclaje_recreado(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    capsys.readouterr()

    ejecutar_protocolo_enmendar(
        protocolo_de_estudio,
        "menor",
        "investigador-1",
        "j",
        "e",
        como_json=True,
        terminal=TerminalSimulada(["enmendar 1.1.0"]),
    )

    assert _json(capsys)["resultado"]["anclaje_recreado"] is True


def test_una_operacion_normal_no_da_el_aviso(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    ejecutar_decision_registrar(_archivo_decision(tmp_path), protocolo_de_estudio)

    assert "aviso:" not in capsys.readouterr().out


# --- validar e historial avisan mientras falte ----------------------------------------


def test_validar_informa_que_falta_el_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)

    registro = validar_archivo(protocolo_de_estudio).registro
    assert registro is not None
    assert registro["falta_anclaje"] is True
    codigo = ejecutar_protocolo_validar(protocolo_de_estudio)

    assert codigo == 0  # no es un error: el siguiente comando lo recrea
    assert NOTA_FALTA in capsys.readouterr().out


def test_validar_en_json_informa_que_falta_el_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)

    ejecutar_protocolo_validar(protocolo_de_estudio, como_json=True)

    assert _json(capsys)["registro"]["falta_anclaje"] is True


def test_historial_informa_que_falta_el_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_protocolo_historial(protocolo_de_estudio)

    assert codigo == 0
    assert NOTA_FALTA in capsys.readouterr().out


def test_historial_en_json_informa_que_falta_el_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_anclaje(protocolo_de_estudio)
    capsys.readouterr()

    ejecutar_protocolo_historial(protocolo_de_estudio, como_json=True)

    assert _json(capsys)["resultado"]["registro"]["falta_anclaje"] is True


def test_con_el_anclaje_presente_no_hay_nota(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    capsys.readouterr()

    ejecutar_protocolo_validar(protocolo_de_estudio)
    ejecutar_protocolo_historial(protocolo_de_estudio)

    assert "nota: falta" not in capsys.readouterr().out
