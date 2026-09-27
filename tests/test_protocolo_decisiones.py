"""Pruebas de las decisiones del protocolo en dos pasos (ADR-0008, puntos 16 y 17)."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.aprobacion import ErrorCicloDeVida, OperacionCancelada, aprobar
from agentresearch.protocolo.decisiones import confirmar_decisiones, registrar_decision
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL
from agentresearch.trazabilidad import RegistroEncadenado, hash_archivo

from .apoyo import TerminalSimulada, reemplazar_en, reloj_incremental

DECISION_VALIDA: dict[str, Any] = {
    "id_decision": "O1",
    "tema": "Límites de la población",
    "pregunta": "¿Qué cuenta como fruto de zarambo poscosecha?",
    "opciones": [
        {
            "id": "A",
            "descripcion": "Solo el fruto entero.",
            "pros": ["Criterio simple."],
            "contras": ["Deja fuera los derivados."],
            "referencias": ["Petersen et al. (2015), §5.1.2"],
        },
        {
            "id": "B",
            "descripcion": "El fruto y sus derivados.",
            "pros": ["Mayor cobertura."],
            "contras": ["Más registros que cribar."],
            "referencias": ["Peters et al. (2024), JBI"],
        },
    ],
    "elegida": "B",
    "justificacion": "Interesa la cadena completa.",
    "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
    "decidido_por": {"tipo": "humano", "id": "investigador-1"},
}


def _decision(**cambios: Any) -> dict[str, Any]:
    decision = copy.deepcopy(DECISION_VALIDA)
    decision.update(cambios)
    return decision


def _archivo(tmp_path: Path, decision: dict[str, Any], nombre: str = "decision.json") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(decision, ensure_ascii=False), encoding="utf-8")
    return ruta


def _registrar(protocolo: Path, tmp_path: Path, **cambios: Any) -> None:
    decision = _decision(**cambios)
    registrar_decision(
        protocolo,
        _archivo(tmp_path, decision, f"{decision['id_decision']}.json"),
        reloj_incremental(),
    )


def _errores(protocolo: Path, tmp_path: Path, decision: dict[str, Any]) -> list[str]:
    with pytest.raises(ErrorCicloDeVida) as error:
        registrar_decision(protocolo, _archivo(tmp_path, decision))
    return error.value.errores


def _estados(protocolo: Path) -> dict[str, str]:
    estado = leer_estado_registro(RutasProtocolo.desde(protocolo))
    return {id_decision: d.estado for id_decision, d in estado.decisiones.items()}


# --- Registrar ------------------------------------------------------------------------


def test_registrar_una_decision_la_deja_pendiente(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    hash_protocolo = hash_archivo(protocolo_de_estudio)

    resultado = registrar_decision(
        protocolo_de_estudio, _archivo(tmp_path, DECISION_VALIDA), reloj_incremental()
    )

    assert resultado.id_decision == "O1"
    assert resultado.evento.tipo == "decision_propuesta"
    assert resultado.evento.datos == {
        "decision": {
            **DECISION_VALIDA,
            "reemplaza": None,
            "propuesto_por": {"tipo": "llm", "id": "", "modelo": "claude-opus-5-5"},
        },
        "version_protocolo": "0.1.0",
        "estado_protocolo": "borrador",
        "hash_protocolo": hash_protocolo,
    }
    assert _estados(protocolo_de_estudio) == {"O1": "pendiente"}
    assert str(resultado.anclaje) == f"evt-000001@{resultado.evento.hash}"
    assert resultado.como_dict()["estado"] == "pendiente"
    validacion = validar_archivo(protocolo_de_estudio)
    assert validacion.hallazgos == []
    assert validacion.registro is not None
    assert validacion.registro["decisiones_pendientes"] == ["O1"]


def test_una_decision_tomada_por_un_llm_se_rechaza(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    decision = _decision(decidido_por={"tipo": "llm", "id": "claude"})

    assert _errores(protocolo_de_estudio, tmp_path, decision) == [
        "decidido_por debe ser un humano: el LLM propone, pero decide el investigador "
        "(CLAUDE.md, regla 1)"
    ]
    assert not (protocolo_de_estudio.parent / "eventos.jsonl").exists()


def test_registrar_no_exige_terminal_ni_un_protocolo_completo(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 0")

    resultado = registrar_decision(protocolo_de_estudio, _archivo(tmp_path, DECISION_VALIDA))

    assert resultado.evento.tipo == "decision_propuesta"


def _opcion(id_opcion: str, **cambios: Any) -> dict[str, Any]:
    opcion: dict[str, Any] = copy.deepcopy(DECISION_VALIDA["opciones"][0])
    opcion["id"] = id_opcion
    opcion.update(cambios)
    return opcion


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        (
            {"opciones": [_opcion("A")], "elegida": "A"},
            "hay 1 opciones; se presentan entre 2 y 4 (CLAUDE.md, regla 9)",
        ),
        (
            {"opciones": [_opcion(i) for i in "ABCDE"], "elegida": "A"},
            "hay 5 opciones; se presentan entre 2 y 4 (CLAUDE.md, regla 9)",
        ),
        ({"elegida": "Z"}, "elegida 'Z' no es el id de ninguna opción"),
        (
            {"opciones": [_opcion("A"), _opcion("A")], "elegida": "A"},
            "opciones[1].id 'A' está repetido",
        ),
        (
            {"opciones": [_opcion("A B"), _opcion("C")], "elegida": "C"},
            "opciones[0].id debe ser un identificador sin espacios (p. ej. A)",
        ),
        (
            {"opciones": [_opcion("A", descripcion=" "), _opcion("B")]},
            "opciones[0].descripcion está vacía",
        ),
        (
            {"opciones": [_opcion("A", pros=[]), _opcion("B")]},
            "opciones[0].pros necesita al menos un pro y ninguno vacío (CLAUDE.md, regla 9)",
        ),
        (
            {"opciones": [_opcion("A"), _opcion("B", contras=["ok", " "])]},
            "opciones[1].contras necesita al menos un contra y ninguno vacío (CLAUDE.md, regla 9)",
        ),
        (
            {"opciones": [_opcion("A", referencias=[]), _opcion("B")]},
            "opciones[0].referencias necesita al menos una referencia y ninguna vacía "
            "(CLAUDE.md, regla 9)",
        ),
        ({"tema": ""}, "tema está vacío"),
        ({"pregunta": " "}, "pregunta está vacío"),
        ({"justificacion": ""}, "justificacion está vacío"),
        ({"id_decision": "O 1"}, "id_decision debe ser un identificador sin espacios (p. ej. O1)"),
        (
            {"decidido_por": {"tipo": "humano", "id": "desconocido"}},
            "decidido_por.id 'desconocido' no es un revisor humano declarado en "
            "seleccion.revisores (humanos: investigador-1, investigador-2)",
        ),
        (
            {"decidido_por": {"tipo": "humano", "id": "claude"}},
            "decidido_por.id 'claude' es un revisor de tipo llm; el LLM propone, pero decide el "
            "investigador (CLAUDE.md, regla 1)",
        ),
        (
            {"propuesto_por": {"tipo": "llm"}},
            "propuesto_por.modelo está vacío: un LLM se identifica con el identificador exacto "
            "del modelo (p. ej. claude-opus-5-5)",
        ),
        (
            {"propuesto_por": {"tipo": "humano"}},
            "propuesto_por.id está vacío: un humano se identifica con su id",
        ),
        (
            {"propuesto_por": {"tipo": "humano", "id": "investigador-1", "modelo": "x-1"}},
            "propuesto_por.modelo solo se usa cuando propuesto_por.tipo es llm",
        ),
        ({"reemplaza": "O9"}, "reemplaza 'O9', que no está registrada"),
    ],
)
def test_registrar_rechaza_decisiones_no_validas(
    protocolo_de_estudio: Path, tmp_path: Path, cambios: dict[str, Any], esperado: str
) -> None:
    assert _errores(protocolo_de_estudio, tmp_path, _decision(**cambios)) == [esperado]


@pytest.mark.parametrize(
    "modelo",
    ["opus", "sonnet", "claude", "claude-opus-latest", "claude opus 5", "Opus-5 ", "fable"],
)
def test_registrar_exige_el_identificador_exacto_del_modelo(
    protocolo_de_estudio: Path, tmp_path: Path, modelo: str
) -> None:
    [error] = _errores(
        protocolo_de_estudio, tmp_path, _decision(propuesto_por={"tipo": "llm", "modelo": modelo})
    )

    assert error.startswith(f"propuesto_por.modelo {modelo!r} no es un identificador exacto")


@pytest.mark.parametrize(
    "modelo", ["claude-opus-5-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]
)
def test_registrar_acepta_identificadores_exactos(
    protocolo_de_estudio: Path, tmp_path: Path, modelo: str
) -> None:
    registrar_decision(
        protocolo_de_estudio,
        _archivo(tmp_path, _decision(propuesto_por={"tipo": "llm", "modelo": modelo})),
    )


def test_registrar_reporta_todos_los_errores_a_la_vez(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    decision = _decision(tema="", elegida="Z", decidido_por={"tipo": "llm", "id": "claude"})

    assert len(_errores(protocolo_de_estudio, tmp_path, decision)) == 3


@pytest.mark.parametrize(
    ("contenido", "fragmento"),
    [
        (b'{"id_decision": "O1", "id_decision": "O2"}', "repite la clave 'id_decision'"),
        (json.dumps({**DECISION_VALIDA, "extra": 1}).encode(), "extra: clave no permitida"),
        (
            json.dumps({**DECISION_VALIDA, "elegida": 1}).encode(),
            "elegida: se esperaba un texto",
        ),
        (b"[", "no es JSON válido"),
    ],
)
def test_registrar_rechaza_archivos_mal_formados(
    protocolo_de_estudio: Path, tmp_path: Path, contenido: bytes, fragmento: str
) -> None:
    archivo = tmp_path / "decision.json"
    archivo.write_bytes(contenido)

    with pytest.raises(ErrorCicloDeVida) as error:
        registrar_decision(protocolo_de_estudio, archivo)

    assert any(fragmento in mensaje for mensaje in error.value.errores), error.value.errores


def test_registrar_con_un_protocolo_ilegible_falla(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    protocolo_de_estudio.write_text("estado: [\n", encoding="utf-8", newline="\n")

    [error] = _errores(protocolo_de_estudio, tmp_path, DECISION_VALIDA)

    assert error.startswith("error P-E00")


def test_registrar_con_el_registro_danado_falla(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    (protocolo_de_estudio.parent / "versiones").mkdir()

    [error] = _errores(protocolo_de_estudio, tmp_path, DECISION_VALIDA)

    assert error.startswith("error P-E10")


def test_una_decision_no_se_registra_dos_veces(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _registrar(protocolo_de_estudio, tmp_path)

    assert _errores(protocolo_de_estudio, tmp_path, DECISION_VALIDA) == [
        "la decisión O1 ya está registrada; para cambiarla, registre otra con reemplaza"
    ]


def test_reemplazar_una_propuesta_pendiente(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _registrar(protocolo_de_estudio, tmp_path)
    _registrar(protocolo_de_estudio, tmp_path, id_decision="O1b", reemplaza="O1", elegida="A")

    assert _estados(protocolo_de_estudio) == {"O1": "reemplazada", "O1b": "pendiente"}
    assert _errores(
        protocolo_de_estudio, tmp_path, _decision(id_decision="O1c", reemplaza="O1")
    ) == ["reemplaza 'O1', que ya fue reemplazada por O1b"]


# --- Confirmar ------------------------------------------------------------------------


def test_confirmar_en_lote_las_decisiones_propias(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    _registrar(protocolo_de_estudio, tmp_path)
    _registrar(
        protocolo_de_estudio,
        tmp_path,
        id_decision="O2",
        decidido_por={"tipo": "humano", "id": "investigador-2"},
    )
    _registrar(protocolo_de_estudio, tmp_path, id_decision="O3")
    terminal = TerminalSimulada(["confirmar 2"])

    resultado = confirmar_decisiones(
        protocolo_de_estudio, "investigador-1", terminal, reloj_incremental()
    )

    assert resultado.confirmadas == ["O1", "O3"]
    assert resultado.pendientes_de_otros == ["O2"]
    assert _estados(protocolo_de_estudio) == {
        "O1": "confirmada",
        "O2": "pendiente",
        "O3": "confirmada",
    }
    eventos = RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").leer()
    assert eventos[3].tipo == "decision_confirmada"
    assert eventos[3].datos == {
        "id_decision": "O1",
        "evento_propuesta": "evt-000001",
        "hash_evento_propuesta": eventos[0].hash,
        "confirmado_por": {"tipo": "humano", "id": "investigador-1"},
    }
    assert str(resultado.anclaje) == f"evt-000005@{eventos[4].hash}"
    assert "Decisiones pendientes de investigador-1: 2" in terminal.texto
    assert "Decisión O1 (evt-000001): Límites de la población" in terminal.texto
    assert "  opción B (elegida): El fruto y sus derivados." in terminal.texto
    assert "    referencias: Petersen et al. (2015), §5.1.2" in terminal.texto
    assert "  propuesta por: LLM claude-opus-5-5" in terminal.texto
    assert "Pendientes de otros revisores (no se confirman aquí): O2" in terminal.texto
    assert resultado.como_dict() == {
        "confirmado_por": "investigador-1",
        "confirmadas": ["O1", "O3"],
        "eventos": ["evt-000004", "evt-000005"],
        "anclaje": str(resultado.anclaje),
        "anclaje_recreado": False,
        "pendientes_de_otros": ["O2"],
    }


def test_confirmar_sin_pendientes_no_exige_terminal(protocolo_de_estudio: Path) -> None:
    resultado = confirmar_decisiones(
        protocolo_de_estudio, "investigador-1", TerminalSimulada(interactiva=False)
    )

    assert resultado.eventos == []
    assert resultado.anclaje is None
    assert resultado.como_dict()["anclaje"] is None


def test_confirmar_sin_terminal_falla(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _registrar(protocolo_de_estudio, tmp_path)

    with pytest.raises(ErrorCicloDeVida) as error:
        confirmar_decisiones(
            protocolo_de_estudio, "investigador-1", TerminalSimulada(interactiva=False)
        )

    assert error.value.errores == [MENSAJE_SIN_TERMINAL]
    assert _estados(protocolo_de_estudio) == {"O1": "pendiente"}


def test_confirmar_sin_la_frase_exacta_se_cancela(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    _registrar(protocolo_de_estudio, tmp_path)

    with pytest.raises(OperacionCancelada, match="«confirmar 1»"):
        confirmar_decisiones(
            protocolo_de_estudio, "investigador-1", TerminalSimulada(["confirmar"])
        )

    assert _estados(protocolo_de_estudio) == {"O1": "pendiente"}


@pytest.mark.parametrize("persona", ["claude", "desconocido"])
def test_confirmar_exige_un_revisor_humano_declarado(
    protocolo_de_estudio: Path, persona: str
) -> None:
    with pytest.raises(ErrorCicloDeVida, match="--confirmado-por"):
        confirmar_decisiones(protocolo_de_estudio, persona, TerminalSimulada())


def test_con_el_registro_danado_no_se_confirma(protocolo_de_estudio: Path) -> None:
    (protocolo_de_estudio.parent / "anclaje.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ErrorCicloDeVida, match="P-E10"):
        confirmar_decisiones(protocolo_de_estudio, "investigador-1", TerminalSimulada())


# --- Relación con la aprobación ----------------------------------------------------------


def test_aprobar_tras_confirmar_las_decisiones(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    _registrar(protocolo_de_estudio, tmp_path)
    with pytest.raises(ErrorCicloDeVida, match="pendientes de confirmar \\(O1\\)"):
        aprobar(protocolo_de_estudio, "investigador-1", TerminalSimulada(["aprobar 1.0.0"]))
    confirmar_decisiones(protocolo_de_estudio, "investigador-1", TerminalSimulada(["confirmar 1"]))
    terminal = TerminalSimulada(["aprobar 1.0.0"])

    aprobar(protocolo_de_estudio, "investigador-1", terminal)

    assert "decisiones confirmadas: O1" in terminal.texto


def test_reemplazar_una_decision_confirmada_bloquea_la_enmienda_hasta_confirmar(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    _registrar(protocolo_de_estudio, tmp_path)
    confirmar_decisiones(protocolo_de_estudio, "investigador-1", TerminalSimulada(["confirmar 1"]))
    aprobar(protocolo_de_estudio, "investigador-1", TerminalSimulada(["aprobar 1.0.0"]))
    _registrar(protocolo_de_estudio, tmp_path, id_decision="O1b", reemplaza="O1", elegida="A")

    assert _estados(protocolo_de_estudio) == {"O1": "reemplazada", "O1b": "pendiente"}
    evento = RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").leer()[-1]
    assert evento.datos["estado_protocolo"] == "vigente"
    assert evento.datos["version_protocolo"] == "1.0.0"
