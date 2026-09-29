"""Pruebas de la nota "instrucciones del agente modificadas" (ADR-0007)."""

import json
from pathlib import Path

import pytest

from agentresearch.cli import ejecutar_protocolo_historial, ejecutar_protocolo_validar
from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.historial import construir_historial
from agentresearch.protocolo.instrucciones import (
    estado_instrucciones,
    hashes_de_instrucciones,
    rutas_de_instrucciones,
)

from .apoyo import agregar_evento

SKILL = ".claude/skills/protocolo/SKILL.md"


def _escribir(estudio: Path, ruta: str, texto: str) -> None:
    destino = estudio.joinpath(*ruta.split("/"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")


@pytest.fixture
def estudio_registrado(protocolo_de_estudio: Path) -> Path:
    """Estudio sintético con instrucciones del agente registradas en `estudio_creado`."""
    estudio = RutasProtocolo.desde(protocolo_de_estudio).estudio
    _escribir(estudio, "CLAUDE.md", "# Estudio de prueba\n")
    _escribir(estudio, ".claude/settings.json", '{"model": "claude-opus-5-5"}\n')
    _escribir(estudio, SKILL, "---\nname: protocolo\n---\n")
    _escribir(estudio, ".claude/settings.local.json", "{}\n")
    instrucciones = [
        {"ruta": ruta, "hash": hash_} for ruta, hash_ in hashes_de_instrucciones(estudio).items()
    ]
    agregar_evento(
        protocolo_de_estudio,
        "estudio_creado",
        {
            "nombre": "estudio",
            "titulo": "Secado del zarambo",
            "modelo": "claude-opus-5-5",
            "fuente_agente": "git+https://example.org/agentresearch@v0.0.0",
            "archivos": [],
            "instrucciones": instrucciones,
            "insumos": [],
        },
    )
    return protocolo_de_estudio


def _estudio(protocolo: Path) -> Path:
    return RutasProtocolo.desde(protocolo).estudio


def test_las_instrucciones_son_claude_md_la_configuracion_y_las_skills(
    estudio_registrado: Path,
) -> None:
    assert rutas_de_instrucciones(_estudio(estudio_registrado)) == [
        ".claude/settings.json",
        SKILL,
        "CLAUDE.md",
    ]


def test_sin_cambios_no_hay_nota(estudio_registrado: Path) -> None:
    estado = estado_instrucciones(leer_estado_registro(RutasProtocolo.desde(estudio_registrado)))

    assert estado is not None
    assert estado.evento == "evt-000001"
    assert not estado.modificadas
    assert estado.nota() is None
    resultado = validar_archivo(estudio_registrado)
    assert resultado.notas() == []
    assert resultado.como_dict()["instrucciones_modificadas"] is False


def test_detecta_archivos_modificados_eliminados_y_agregados(estudio_registrado: Path) -> None:
    estudio = _estudio(estudio_registrado)
    _escribir(estudio, "CLAUDE.md", "# Estudio de prueba, con otra regla\n")
    (estudio / ".claude" / "settings.json").unlink()
    _escribir(estudio, ".claude/skills/otra/SKILL.md", "---\nname: otra\n---\n")
    _escribir(estudio, ".claude/settings.local.json", '{"cambio": "local"}\n')

    estado = estado_instrucciones(leer_estado_registro(RutasProtocolo.desde(estudio_registrado)))

    assert estado is not None
    assert estado.modificados == ["CLAUDE.md"]
    assert estado.eliminados == [".claude/settings.json"]
    assert estado.agregados == [".claude/skills/otra/SKILL.md"]
    nota = estado.nota()
    assert nota is not None
    assert nota.startswith(
        "instrucciones del agente modificadas desde su registro en evt-000001: cambiaron "
        "CLAUDE.md; faltan .claude/settings.json; no estaban registrados "
        ".claude/skills/otra/SKILL.md."
    )
    assert estado.como_dict()["modificadas"] is True


def test_sin_evento_de_creacion_no_se_comparan(protocolo_de_estudio: Path) -> None:
    assert (
        estado_instrucciones(leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio)))
        is None
    )
    assert validar_archivo(protocolo_de_estudio).como_dict()["instrucciones"] is None


def test_validar_e_historial_muestran_la_nota(
    estudio_registrado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escribir(_estudio(estudio_registrado), SKILL, "---\nname: protocolo\n---\nOtra cosa.\n")

    ejecutar_protocolo_validar(estudio_registrado)
    salida_validar = capsys.readouterr().out
    ejecutar_protocolo_historial(estudio_registrado)
    salida_historial = capsys.readouterr().out

    esperado = (
        "nota: instrucciones del agente modificadas desde su registro en evt-000001: "
        f"cambiaron {SKILL}."
    )
    assert esperado in salida_validar
    assert esperado in salida_historial


def test_historial_muestra_la_creacion_del_estudio(
    estudio_registrado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_protocolo_historial(estudio_registrado)

    salida = capsys.readouterr().out
    assert "estudio: Secado del zarambo (estudio), creado el " in salida
    assert "(evt-000001); modelo fijado: claude-opus-5-5" in salida


def test_historial_en_json_incluye_el_estudio_y_las_instrucciones(
    estudio_registrado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_protocolo_historial(estudio_registrado, como_json=True)

    resultado = json.loads(capsys.readouterr().out)["resultado"]
    assert resultado["estudio"]["evento"] == "evt-000001"
    assert resultado["estudio"]["datos"]["titulo"] == "Secado del zarambo"
    assert resultado["instrucciones"]["modificadas"] is False
    assert resultado["instrucciones_modificadas"] is False


def test_historial_sin_creacion(protocolo_de_estudio: Path) -> None:
    historial = construir_historial(protocolo_de_estudio)

    assert historial.como_dict()["estudio"] is None
    assert historial.como_dict()["instrucciones"] is None
