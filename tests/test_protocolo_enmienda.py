"""Pruebas de la enmienda del protocolo (ADR-0008, puntos 6, 12, 13 y 23)."""

import json
from pathlib import Path

import pytest

from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.aprobacion import (
    ErrorCicloDeVida,
    NivelElegido,
    OperacionCancelada,
    ResultadoOperacion,
    enmendar,
    simular_enmienda,
)
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL
from agentresearch.trazabilidad import RegistroEncadenado, hash_archivo

from .apoyo import (
    TerminalSimulada,
    agregar_evento,
    aprobar_protocolo,
    decision_propuesta,
    reemplazar_en,
    reloj_incremental,
)

TEXTO_CI1 = "Estudia el secado del fruto de zarambo."


def _enmendar(
    ruta: Path, nivel: NivelElegido | None = "menor", frase: str | None = None
) -> ResultadoOperacion:
    version = simular_enmienda(ruta, nivel).version_siguiente
    terminal = TerminalSimulada([frase if frase is not None else f"enmendar {version}"])
    return enmendar(
        ruta,
        nivel,
        "investigador-1",
        terminal,
        justificacion="El piloto mostró ambigüedad.",
        efecto_esperado="Menos desacuerdos en el cribado.",
        reloj=reloj_incremental(),
    )


@pytest.fixture
def protocolo_vigente(protocolo_de_estudio: Path) -> Path:
    aprobar_protocolo(protocolo_de_estudio)
    return protocolo_de_estudio


def _texto_ci1(ruta: Path) -> str:
    texto = ruta.read_text(encoding="utf-8")
    inicio = texto.index("  inclusion:\n    - id: CI1\n      texto: ") + len(
        "  inclusion:\n    - id: CI1\n      texto: "
    )
    return texto[inicio : texto.index("\n", inicio)]


def _archivos_de_versiones(ruta: Path) -> list[str]:
    return sorted(p.name for p in (ruta.parent / "versiones").iterdir())


# --- Enmienda correcta ---------------------------------------------------------------


def test_una_enmienda_incrementa_la_version_y_registra_el_diff(protocolo_vigente: Path) -> None:
    rutas = RutasProtocolo.desde(protocolo_vigente)
    [aprobacion] = RegistroEncadenado(rutas.eventos).leer()
    texto_ci1 = _texto_ci1(protocolo_vigente)
    reemplazar_en(protocolo_vigente, texto_ci1, '"Estudia el secado o la deshidratación."')
    reemplazar_en(
        protocolo_vigente, '["zarambo", "\\"Zarambus', '["zarambo", "zarambos", "\\"Zarambus'
    )
    hash_editado = hash_archivo(protocolo_vigente)

    resultado = _enmendar(protocolo_vigente, "menor")

    assert resultado.version_anterior == "1.0.0"
    assert resultado.version_protocolo == "1.1.0"
    assert resultado.hash_protocolo == hash_archivo(protocolo_vigente)
    assert b'version_protocolo: "1.1.0"' in protocolo_vigente.read_bytes()
    assert rutas.copia_de_version("1.1.0").read_bytes() == protocolo_vigente.read_bytes()
    datos = resultado.evento.datos
    assert resultado.evento.tipo == "protocolo_enmendado"
    assert datos["version_anterior"] == "1.0.0"
    assert datos["version_protocolo"] == "1.1.0"
    assert datos["nivel"] == "menor"
    assert datos["hash_protocolo_anterior"] == aprobacion.datos["hash_protocolo"]
    assert datos["hash_revisado"] == hash_editado
    assert datos["hash_protocolo"] == resultado.hash_protocolo
    assert datos["ruta_version"] == "protocolo/versiones/1.1.0.yaml"
    assert datos["justificacion"] == "El piloto mostró ambigüedad."
    assert datos["efecto_esperado"] == "Menos desacuerdos en el cribado."
    assert datos["enmendado_por"] == {"tipo": "humano", "id": "investigador-1"}
    assert datos["solo_formato"] is False
    assert datos["advertencias"] == []
    assert datos["cambios"] == [
        {
            "ruta": "busqueda.bloques[B1].terminos",
            "operacion": "modificado",
            "antes": ["zarambo", '"Zarambus fictus"'],
            "despues": ["zarambo", "zarambos", '"Zarambus fictus"'],
            "agregados": ["zarambos"],
            "eliminados": [],
        },
        {
            "ruta": "criterios.inclusion[CI1].texto",
            "operacion": "modificado",
            "antes": json.loads(texto_ci1),
            "despues": "Estudia el secado o la deshidratación.",
        },
    ]
    assert validar_archivo(protocolo_vigente).hallazgos == []
    versiones = leer_estado_registro(rutas).versiones
    assert [v.version for v in versiones] == ["1.0.0", "1.1.0"]


def test_una_enmienda_mayor_y_otra_menor_encadenan_sus_hashes(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    primera = _enmendar(protocolo_vigente, "mayor")
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 30", "tamano_lote_llm: 20")
    segunda = _enmendar(protocolo_vigente, "menor")

    assert primera.version_protocolo == "2.0.0"
    assert segunda.version_protocolo == "2.1.0"
    assert segunda.evento.datos["hash_protocolo_anterior"] == primera.hash_protocolo
    assert _archivos_de_versiones(protocolo_vigente) == ["1.0.0.yaml", "2.0.0.yaml", "2.1.0.yaml"]
    assert validar_archivo(protocolo_vigente).hallazgos == []


def test_un_cambio_de_solo_comentarios_es_un_parche(protocolo_vigente: Path) -> None:
    with protocolo_vigente.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("# Nota agregada después de aprobar.\n")

    propuesta = simular_enmienda(protocolo_vigente)
    resultado = _enmendar(protocolo_vigente, None)

    assert propuesta.solo_formato
    assert propuesta.nivel == "parche"
    assert propuesta.version_siguiente == "1.0.1"
    assert resultado.version_protocolo == "1.0.1"
    assert resultado.evento.datos["nivel"] == "parche"
    assert resultado.evento.datos["solo_formato"] is True
    assert resultado.evento.datos["cambios"] == []


def test_un_parche_no_admite_nivel(protocolo_vigente: Path) -> None:
    with protocolo_vigente.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("# Nota.\n")

    with pytest.raises(ErrorCicloDeVida) as error:
        enmendar(
            protocolo_vigente,
            "menor",
            "investigador-1",
            TerminalSimulada(),
            justificacion="j",
            efecto_esperado="e",
        )

    assert error.value.errores == [
        "el cambio es solo de formato o comentarios: el nivel es parche y lo asigna el "
        "paquete, así que no se da --nivel"
    ]


def test_reordenar_criterios_es_un_cambio_de_contenido(protocolo_vigente: Path) -> None:
    texto = protocolo_vigente.read_text(encoding="utf-8")
    inicio = texto.index("    - id: CE1\n")
    medio = texto.index("    - id: CE2\n")
    fin = texto.index("seleccion:\n", medio)
    reordenado = texto[:inicio] + texto[medio:fin] + texto[inicio:medio] + texto[fin:]
    protocolo_vigente.write_text(reordenado, encoding="utf-8", newline="\n")

    propuesta = simular_enmienda(protocolo_vigente)

    [cambio] = propuesta.cambios
    assert cambio.ruta == "criterios.exclusion"
    assert cambio.operacion == "reordenado"
    assert propuesta.nivel is None
    assert propuesta.opciones_de_version == {"menor": "1.1.0", "mayor": "2.0.0"}


def test_el_resumen_muestra_el_diff_y_los_textos_completos(
    protocolo_vigente: Path, tmp_path: Path
) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    archivo = tmp_path / "enmienda.json"
    justificacion = "Justificación larga " * 20
    archivo.write_text(
        json.dumps({"justificacion": justificacion, "efecto_esperado": "Lotes más grandes."}),
        encoding="utf-8",
    )
    terminal = TerminalSimulada(["enmendar 1.1.0"])

    resultado = enmendar(
        protocolo_vigente, "menor", "investigador-1", terminal, archivo_enmienda=archivo
    )

    assert f"  justificación: {justificacion.strip()}" in terminal.texto
    assert "  efecto esperado: Lotes más grandes." in terminal.texto
    assert "versión: 1.0.0 → 1.1.0 (nivel menor)" in terminal.texto
    assert "Cambios: 1\n  - seleccion.tamano_lote_llm: 25 → 30" in terminal.texto
    assert "Advertencias activas: ninguna" in terminal.texto
    assert resultado.evento.datos["justificacion"] == justificacion.strip()
    assert terminal.preguntas == [
        "Escriba «enmendar 1.1.0» para confirmar, o cualquier otra cosa para cancelar: "
    ]


def test_la_enmienda_registra_las_advertencias_sin_exigir_justificacion(
    protocolo_vigente: Path,
) -> None:
    reemplazar_en(protocolo_vigente, "tamano: 20", "tamano: 0")

    resultado = _enmendar(protocolo_vigente, "menor")

    [advertencia] = resultado.evento.datos["advertencias"]
    assert advertencia["id_regla"] == "P-A09"
    assert "justificacion" not in advertencia


# --- Rechazos (no se escribe nada) --------------------------------------------------


def test_enmendar_sin_cambios_falla(protocolo_vigente: Path) -> None:
    with pytest.raises(ErrorCicloDeVida) as error:
        _enmendar(protocolo_vigente, None)

    assert error.value.errores[0] == (
        "no hay cambios que enmendar: protocolo/protocolo.yaml coincide con la versión 1.0.0 "
        "registrada en evt-000001"
    )


def test_enmendar_un_borrador_falla(protocolo_de_estudio: Path) -> None:
    with pytest.raises(ErrorCicloDeVida) as error:
        simular_enmienda(protocolo_de_estudio, "menor")

    assert error.value.errores == [
        "el protocolo no está aprobado: un borrador se edita libremente y se aprueba con "
        "`agentresearch protocolo aprobar`"
    ]


def test_enmendar_con_la_version_editada_a_mano_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, 'version_protocolo: "1.0.0"', 'version_protocolo: "1.1.0"')

    propuesta = simular_enmienda(protocolo_vigente, "menor")

    assert propuesta.problemas == [
        "la versión de protocolo/protocolo.yaml (1.1.0) no es la registrada (1.0.0); la "
        "versión la asigna el paquete, no se edita a mano"
    ]


def test_enmendar_con_el_estado_devuelto_a_borrador_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "estado: vigente", "estado: borrador")

    propuesta = simular_enmienda(protocolo_vigente, "menor")

    assert propuesta.problemas == [
        "el estado de protocolo/protocolo.yaml es «borrador»; un protocolo aprobado no vuelve "
        "a borrador, y el estado no se edita a mano"
    ]


def test_enmendar_con_errores_en_el_protocolo_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 0")

    with pytest.raises(ErrorCicloDeVida) as error:
        _enmendar(protocolo_vigente, "menor")

    [mensaje] = error.value.errores
    assert mensaje.startswith("error P-E08")  # el P-E09 del cambio sin enmienda se admite


def test_enmendar_con_la_copia_alterada_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    copia = protocolo_vigente.parent / "versiones" / "1.0.0.yaml"
    copia.write_bytes(copia.read_bytes() + b"# alterada\n")

    with pytest.raises(ErrorCicloDeVida) as error:
        simular_enmienda(protocolo_vigente, "menor")

    [mensaje] = error.value.errores
    assert mensaje.startswith("error P-E10")
    assert "no coincide con el hash" in mensaje


def test_enmendar_con_un_protocolo_ilegible_falla(protocolo_vigente: Path) -> None:
    protocolo_vigente.write_text("estado: [\n", encoding="utf-8", newline="\n")

    with pytest.raises(ErrorCicloDeVida) as error:
        simular_enmienda(protocolo_vigente, "menor")

    assert error.value.errores[0].startswith("error P-E00")


def test_enmendar_tras_una_operacion_interrumpida_falla(
    protocolo_vigente: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    from agentresearch.trazabilidad import escribir_atomico

    def _escribir(ruta: Path | str, contenido: bytes) -> None:
        if Path(ruta).name == "protocolo.yaml":
            raise OSError("fallo simulado")
        escribir_atomico(ruta, contenido)

    monkeypatch.setattr("agentresearch.protocolo.aprobacion.escribir_atomico", _escribir)
    with pytest.raises(OSError):
        _enmendar(protocolo_vigente, "menor")
    monkeypatch.undo()

    propuesta = simular_enmienda(protocolo_vigente, "menor")

    problema = propuesta.problemas[0]
    assert problema.startswith("error P-E09: la enmienda de la versión 1.1.0")
    assert "copie protocolo/versiones/1.1.0.yaml sobre protocolo/protocolo.yaml" in problema


def test_enmendar_con_decisiones_pendientes_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    agregar_evento(protocolo_vigente, "decision_propuesta", decision_propuesta("O11"))

    propuesta = simular_enmienda(protocolo_vigente, "menor")

    [problema] = propuesta.problemas
    assert problema.startswith("hay decisiones pendientes de confirmar (O11)")


@pytest.mark.parametrize(
    ("nivel", "enmendado_por", "justificacion", "efecto", "esperados"),
    [
        (None, "investigador-1", "j", "e", ["falta --nivel mayor|menor"]),
        ("menor", None, "j", "e", ["falta --enmendado-por"]),
        (
            "menor",
            "claude",
            "j",
            "e",
            [
                "--enmendado-por 'claude' es un revisor de tipo llm; el LLM propone, pero "
                "decide el investigador (CLAUDE.md, regla 1)"
            ],
        ),
        (
            "menor",
            "investigador-1",
            " ",
            None,
            [
                "falta la justificación de la enmienda (--justificacion)",
                "falta el efecto esperado de la enmienda (--efecto-esperado)",
            ],
        ),
    ],
)
def test_enmendar_exige_nivel_persona_y_textos(
    protocolo_vigente: Path,
    nivel: NivelElegido | None,
    enmendado_por: str | None,
    justificacion: str | None,
    efecto: str | None,
    esperados: list[str],
) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    with pytest.raises(ErrorCicloDeVida) as error:
        enmendar(
            protocolo_vigente,
            nivel,
            enmendado_por,
            TerminalSimulada(),
            justificacion=justificacion,
            efecto_esperado=efecto,
        )

    assert error.value.errores == esperados


def test_archivo_de_enmienda_y_opciones_a_la_vez_falla(
    protocolo_vigente: Path, tmp_path: Path
) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    archivo = tmp_path / "enmienda.json"
    archivo.write_text('{"justificacion": "j", "efecto_esperado": "e"}', encoding="utf-8")

    with pytest.raises(ErrorCicloDeVida) as error:
        enmendar(
            protocolo_vigente,
            "menor",
            "investigador-1",
            TerminalSimulada(),
            justificacion="otra",
            archivo_enmienda=archivo,
        )

    assert error.value.errores == [
        "use --archivo-enmienda o --justificacion y --efecto-esperado, pero no ambos"
    ]


def test_archivo_de_enmienda_no_valido_falla(protocolo_vigente: Path, tmp_path: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    archivo = tmp_path / "enmienda.json"
    archivo.write_text('{"justificacion": "j"}', encoding="utf-8")

    with pytest.raises(ErrorCicloDeVida) as error:
        enmendar(
            protocolo_vigente,
            "menor",
            "investigador-1",
            TerminalSimulada(),
            archivo_enmienda=archivo,
        )

    assert error.value.errores == [f"{archivo}: efecto_esperado: falta este campo obligatorio"]


def test_enmendar_sin_terminal_falla(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    original = protocolo_vigente.read_bytes()

    with pytest.raises(ErrorCicloDeVida) as error:
        enmendar(
            protocolo_vigente,
            "menor",
            "investigador-1",
            TerminalSimulada(interactiva=False),
            justificacion="j",
            efecto_esperado="e",
        )

    assert error.value.errores == [MENSAJE_SIN_TERMINAL]
    assert protocolo_vigente.read_bytes() == original
    assert _archivos_de_versiones(protocolo_vigente) == ["1.0.0.yaml"]


def test_enmendar_sin_la_frase_exacta_se_cancela(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    with pytest.raises(OperacionCancelada, match="«enmendar 1.1.0»"):
        _enmendar(protocolo_vigente, "menor", frase="enmendar 2.0.0")

    assert _archivos_de_versiones(protocolo_vigente) == ["1.0.0.yaml"]
    assert len(RegistroEncadenado(protocolo_vigente.parent / "eventos.jsonl").leer()) == 1


# --- Simulación ---------------------------------------------------------------------


def test_simular_no_escribe_ni_exige_terminal(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    antes = sorted(p.name for p in protocolo_vigente.parent.rglob("*"))
    contenido = protocolo_vigente.read_bytes()

    propuesta = simular_enmienda(protocolo_vigente)

    assert sorted(p.name for p in protocolo_vigente.parent.rglob("*")) == antes
    assert protocolo_vigente.read_bytes() == contenido
    assert propuesta.problemas == []
    assert propuesta.version_siguiente is None
    assert propuesta.como_dict() == {
        "ruta_protocolo": "protocolo/protocolo.yaml",
        "version_registrada": "1.0.0",
        "evento_registrado": "evt-000001",
        "nivel": None,
        "version_siguiente": None,
        "opciones_de_version": {"menor": "1.1.0", "mayor": "2.0.0"},
        "solo_formato": False,
        "cambios": [
            {
                "ruta": "seleccion.tamano_lote_llm",
                "operacion": "modificado",
                "antes": 25,
                "despues": 30,
            }
        ],
        "problemas": [],
        "se_puede_enmendar": True,
    }


def test_simular_con_nivel_da_la_version_siguiente(protocolo_vigente: Path) -> None:
    reemplazar_en(protocolo_vigente, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    propuesta = simular_enmienda(protocolo_vigente, "mayor")

    assert propuesta.version_siguiente == "2.0.0"
    assert propuesta.opciones_de_version == {}
