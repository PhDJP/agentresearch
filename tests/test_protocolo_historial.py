"""Pruebas del historial del protocolo y de su anclaje (ADR-0008, puntos 18 a 21)."""

import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import ejecutar_protocolo_historial, main
from agentresearch.protocolo import RutasProtocolo
from agentresearch.protocolo.aprobacion import aprobar, enmendar
from agentresearch.protocolo.ciclo_de_vida import escribir_anclaje
from agentresearch.protocolo.decisiones import confirmar_decisiones, registrar_decision
from agentresearch.protocolo.historial import construir_historial, texto_historial
from agentresearch.trazabilidad import RegistroEncadenado

from .apoyo import TerminalSimulada, aprobar_protocolo, reemplazar_en, reloj_incremental


def _archivo_decision(tmp_path: Path, id_decision: str, **cambios: Any) -> Path:
    opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
    decision: dict[str, Any] = {
        "id_decision": id_decision,
        "tema": f"Tema de {id_decision}",
        "pregunta": "¿Pregunta?",
        "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
        "elegida": "B",
        "justificacion": "Justificación",
        "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
        "decidido_por": {"tipo": "humano", "id": "investigador-1"},
    }
    decision.update(cambios)
    archivo = tmp_path / f"{id_decision}.json"
    archivo.write_text(json.dumps(decision, ensure_ascii=False), encoding="utf-8")
    return archivo


def _recorrido_completo(ruta: Path, tmp_path: Path) -> None:
    """Decisión confirmada, aprobación con una advertencia, enmienda menor, parche y otra
    decisión pendiente que reemplaza a la primera."""
    reloj = reloj_incremental()
    registrar_decision(ruta, _archivo_decision(tmp_path, "O1"), reloj)
    confirmar_decisiones(ruta, "investigador-1", TerminalSimulada(["confirmar 1"]), reloj)
    reemplazar_en(ruta, "tamano: 20", "tamano: 0")
    aprobar(
        ruta,
        "investigador-1",
        TerminalSimulada(["Se fija tras la búsqueda.", "aprobar 1.0.0"]),
        reloj=reloj,
    )
    reemplazar_en(ruta, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    enmendar(
        ruta,
        "menor",
        "investigador-1",
        TerminalSimulada(["enmendar 1.1.0"]),
        justificacion="Lotes más grandes.",
        efecto_esperado="Menos lotes.",
        reloj=reloj,
    )
    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("# Nota.\n")
    enmendar(
        ruta,
        None,
        "investigador-1",
        TerminalSimulada(["enmendar 1.1.1"]),
        justificacion="Nota aclaratoria.",
        efecto_esperado="Ninguno sobre el contenido.",
        reloj=reloj,
    )
    registrar_decision(ruta, _archivo_decision(tmp_path, "O1b", reemplaza="O1"), reloj)


def _eliminar_ultima_linea(archivo: Path) -> None:
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    archivo.write_text("\n".join(lineas[:-1]) + "\n", encoding="utf-8", newline="\n")


# --- Contenido ------------------------------------------------------------------------


def test_historial_de_un_borrador_sin_registro(protocolo_de_estudio: Path) -> None:
    historial = construir_historial(protocolo_de_estudio)

    assert historial.integro
    assert texto_historial(historial) == [
        "protocolo: protocolo/protocolo.yaml (borrador, versión 0.1.0)",
        "registro: no existe protocolo/eventos.jsonl (sin eventos registrados)",
        "versiones: ninguna registrada",
        "decisiones: ninguna registrada",
    ]
    assert historial.como_dict()["estado_anclaje"] == "sin registro"


def test_historial_de_un_recorrido_completo(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _recorrido_completo(protocolo_de_estudio, tmp_path)
    eventos = RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").leer()

    historial = construir_historial(protocolo_de_estudio)
    texto = "\n".join(texto_historial(historial))

    assert historial.integro
    assert historial.hallazgos == []
    assert "protocolo: protocolo/protocolo.yaml (vigente, versión 1.1.1)" in texto
    assert "registro: protocolo/eventos.jsonl, íntegro, 6 eventos" in texto
    assert f"anclaje: evt-000006@{eventos[-1].hash}" in texto
    assert "anclaje guardado en protocolo/anclaje.json: coincide" in texto
    assert "  1.0.0  2026-09-26T12:00:02.000Z  aprobación por investigador-1 (evt-000003)" in (
        texto
    )
    assert "    advertencias justificadas: 1" in texto
    assert "      - P-A09 en seleccion.piloto.tamano: Se fija tras la búsqueda." in texto
    assert "  1.1.0  2026-09-26T12:00:03.000Z  enmienda menor por investigador-1 (evt-000004)" in (
        texto
    )
    assert "    justificación: Lotes más grandes." in texto
    assert "    efecto esperado: Menos lotes." in texto
    assert "    cambios: 1\n      - seleccion.tamano_lote_llm: 25 → 30" in texto
    assert "  1.1.1  2026-09-26T12:00:04.000Z  enmienda parche por investigador-1" in texto
    assert "    cambios: ninguno de contenido (solo formato o comentarios)" in texto
    assert (
        "  O1  reemplazada  Tema de O1: opción B (decidió investigador-1; propuso LLM "
        "claude-opus-5-5; confirmada en evt-000002; reemplazada por O1b)"
    ) in texto
    assert "  O1b  pendiente  Tema de O1b: opción B (" in texto
    assert "reemplaza a O1)" in texto


def test_historial_en_diccionario(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _recorrido_completo(protocolo_de_estudio, tmp_path)

    datos = construir_historial(protocolo_de_estudio).como_dict()

    assert datos["ruta_protocolo"] == "protocolo/protocolo.yaml"
    assert datos["estado"] == "vigente"
    assert datos["version_protocolo"] == "1.1.1"
    assert datos["estado_anclaje"] == "coincide"
    assert datos["registro"]["numero_eventos"] == 6
    assert [(v["version"], v["tipo"], v["evento"]) for v in datos["versiones"]] == [
        ("1.0.0", "aprobacion", "evt-000003"),
        ("1.1.0", "enmienda", "evt-000004"),
        ("1.1.1", "enmienda", "evt-000005"),
    ]
    assert datos["versiones"][1]["datos"]["nivel"] == "menor"
    [o1, o1b] = datos["decisiones"]
    assert o1["estado"] == "reemplazada"
    assert o1["evento_confirmacion"] == "evt-000002"
    assert o1["confirmado_por"] == "investigador-1"
    assert o1["reemplazada_por"] == "O1b"
    assert o1b["estado"] == "pendiente"
    assert o1b["evento_confirmacion"] is None
    assert o1b["datos"]["decision"]["reemplaza"] == "O1"


# --- Anclaje ----------------------------------------------------------------------------


def test_un_anclaje_atrasado_se_muestra_como_valido(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    anclaje_anterior = RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").anclaje()
    RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").agregar("nota", {})

    historial = construir_historial(protocolo_de_estudio)

    assert historial.integro
    assert (
        f"anclaje guardado en protocolo/anclaje.json: atrasado (válido como prefijo): "
        f"{anclaje_anterior}"
    ) in texto_historial(historial)


def test_el_truncamiento_del_registro_se_detecta_con_el_anclaje(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    reloj = reloj_incremental()
    registrar_decision(
        protocolo_de_estudio, _archivo_decision(protocolo_de_estudio.parent.parent, "O1"), reloj
    )
    _eliminar_ultima_linea(protocolo_de_estudio.parent / "eventos.jsonl")

    codigo = ejecutar_protocolo_historial(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "registro: protocolo/eventos.jsonl, con problemas (P-E10), 1 eventos" in salida
    assert "anclaje guardado en protocolo/anclaje.json: no se cumple: evt-000002@" in salida
    assert "error P-E10: protocolo/eventos.jsonl no cumple protocolo/anclaje.json" in salida
    assert "se eliminaron eventos del final" in salida


def test_el_truncamiento_en_json(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").agregar("nota", {})
    escribir_anclaje(RutasProtocolo.desde(protocolo_de_estudio))
    _eliminar_ultima_linea(protocolo_de_estudio.parent / "eventos.jsonl")

    codigo = ejecutar_protocolo_historial(protocolo_de_estudio, como_json=True)

    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert codigo == 1
    assert salida.isascii()
    assert datos["comando"] == "protocolo historial"
    assert datos["exito"] is False
    [error] = datos["errores"]
    assert error.startswith("error P-E10")
    assert datos["resultado"]["estado_anclaje"] == "no se cumple"


@pytest.mark.parametrize(
    ("preparar", "esperado"),
    [
        (lambda anclaje: anclaje.unlink(), "sin anclaje guardado"),
        (lambda anclaje: anclaje.write_text("{", encoding="utf-8"), "no válido"),
    ],
)
def test_estado_del_anclaje_guardado(
    protocolo_de_estudio: Path, preparar: Any, esperado: str
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    preparar(protocolo_de_estudio.parent / "anclaje.json")

    historial = construir_historial(protocolo_de_estudio)

    assert historial.como_dict()["estado_anclaje"] == esperado
    assert f"anclaje guardado en protocolo/anclaje.json: {esperado}" in texto_historial(historial)


def test_con_la_cadena_rota_el_historial_no_es_fiable(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio.parent / "eventos.jsonl", "investigador-1", "otra")

    historial = construir_historial(protocolo_de_estudio)

    assert not historial.integro
    assert historial.como_dict()["estado_anclaje"] == "registro dañado"
    assert not any(linea.startswith("anclaje:") for linea in texto_historial(historial))


# --- P-E09 y protocolo ilegible --------------------------------------------------------------


def test_p_e09_se_muestra_como_nota_sin_cambiar_el_codigo(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    codigo = ejecutar_protocolo_historial(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "hallazgos:\n  error P-E09: protocolo/protocolo.yaml cambió" in salida


def test_historial_con_un_protocolo_ilegible(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    protocolo_de_estudio.write_text("estado: [\n", encoding="utf-8", newline="\n")

    historial = construir_historial(protocolo_de_estudio)

    assert texto_historial(historial)[0] == (
        "protocolo: protocolo/protocolo.yaml (no se pudo leer; ejecute protocolo validar)"
    )
    assert historial.integro


def test_main_historial(
    protocolo_de_estudio: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["agentresearch", "protocolo", "historial", str(protocolo_de_estudio)]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert "versiones: ninguna registrada" in capsys.readouterr().out
