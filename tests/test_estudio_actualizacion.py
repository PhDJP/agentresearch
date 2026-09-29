"""Pruebas de `agentresearch estudio actualizar` (ADR-0007), con datos sintéticos."""

import json
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agentresearch.cli import ejecutar_estudio_actualizar, main
from agentresearch.estudio import actualizacion
from agentresearch.estudio.actualizacion import actualizar_estudio
from agentresearch.estudio.creacion import crear_estudio
from agentresearch.estudio.modelo import leer_estudio
from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.aprobacion import ErrorCicloDeVida, OperacionCancelada
from agentresearch.protocolo.eventos import DatosEstudioActualizado
from agentresearch.protocolo.historial import construir_historial, texto_historial
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL
from agentresearch.trazabilidad import RegistroEncadenado, hash_archivo, hash_bytes

from .apoyo import TerminalSimulada, agregar_evento, aprobar_protocolo, reloj_incremental
from .conftest import RUTA_PROTOCOLO_SINTETICO

MOMENTO = datetime(2026, 9, 27, 15, 30, 0, tzinfo=UTC)
MODELO = "claude-opus-5-5"
NUEVA = "9.9.9"
INSTALADA = version("agentresearch")
JUSTIFICACION = "Pasar a la versión que agrega las instrucciones del hito 2."


@pytest.fixture
def estudio(tmp_path: Path) -> Path:
    """Estudio sintético recién creado con la versión instalada del agente."""
    destino = tmp_path / "mapeo-zarambo"
    crear_estudio(destino, "Secado del zarambo", MODELO, reloj=lambda: MOMENTO)
    return destino


def _instalar(estudio: Path, monkeypatch: pytest.MonkeyPatch, nueva: str = NUEVA) -> None:
    """Simula que el investigador cambió la versión en pyproject.toml y ejecutó uv sync."""
    pyproject = estudio / "pyproject.toml"
    texto = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(texto.replace(f"@v{INSTALADA}", f"@v{nueva}"), encoding="utf-8")
    monkeypatch.setattr(actualizacion, "version", lambda _paquete: nueva)


def _actualizar(
    estudio: Path, respuestas: list[str | None] | None = None, **opciones: Any
) -> actualizacion.ResultadoActualizacion:
    terminal = opciones.pop("terminal", None) or TerminalSimulada(
        respuestas if respuestas is not None else [f"actualizar {NUEVA}"]
    )
    opciones.setdefault("justificacion", JUSTIFICACION)
    return actualizar_estudio(
        estudio, "investigador-1", terminal, reloj=reloj_incremental(), **opciones
    )


def _instantanea(estudio: Path) -> dict[str, bytes]:
    return {
        p.relative_to(estudio).as_posix(): p.read_bytes()
        for p in sorted(estudio.rglob("*"))
        if p.is_file()
    }


def _protocolo(estudio: Path) -> Path:
    return estudio / "protocolo" / "protocolo.yaml"


# --- Actualización -----------------------------------------------------------------


def test_actualiza_la_version_y_regenera_las_instrucciones(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    terminal = TerminalSimulada([f"actualizar {NUEVA}"])

    resultado = _actualizar(estudio, terminal=terminal)

    assert resultado.version_anterior == INSTALADA
    assert resultado.version_nueva == NUEVA
    assert not resultado.completada
    datos_estudio = leer_estudio(estudio / "estudio.yaml")
    assert datos_estudio.agente.version == NUEVA
    assert datos_estudio.agente.fuente == f"git+https://github.com/PhDJP/agentresearch@v{NUEVA}"
    assert f"agentresearch](https://github.com/PhDJP/agentresearch) {NUEVA}" in (
        estudio / "CLAUDE.md"
    ).read_text(encoding="utf-8")
    assert "CLAUDE.md" in resultado.archivos_cambiados
    assert "estudio.yaml" in resultado.archivos_cambiados
    # Muestra el diff y pide la frase de confirmación.
    assert "--- a/CLAUDE.md" in terminal.texto
    assert "+++ b/CLAUDE.md" in terminal.texto
    assert f"versión: {INSTALADA} → {NUEVA}" in terminal.texto
    assert f"justificación: {JUSTIFICACION}" in terminal.texto
    assert f"«actualizar {NUEVA}»" in terminal.preguntas[0]


def test_conserva_el_modelo_fijado(estudio: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(estudio, monkeypatch)

    _actualizar(estudio)

    configuracion = json.loads((estudio / ".claude" / "settings.json").read_text("utf-8"))
    assert configuracion["model"] == MODELO
    assert leer_estudio(estudio / "estudio.yaml").modelo == MODELO


def test_registra_el_evento_con_los_hashes_y_actualiza_el_anclaje(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = _instantanea(estudio)
    _instalar(estudio, monkeypatch)

    resultado = _actualizar(estudio)

    registro = RegistroEncadenado(estudio / "protocolo" / "eventos.jsonl")
    [creado, actualizado] = registro.leer()
    assert actualizado.tipo == "estudio_actualizado"
    assert resultado.evento.id == actualizado.id == "evt-000002"
    datos = actualizado.datos
    assert datos["version_anterior"] == INSTALADA
    assert datos["version_nueva"] == NUEVA
    assert datos["fuente_anterior"] == creado.datos["fuente_agente"]
    assert datos["justificacion"] == JUSTIFICACION
    assert datos["actualizado_por"] == {"tipo": "humano", "id": "investigador-1"}
    rutas = [archivo["ruta"] for archivo in datos["archivos"]]
    assert rutas == [
        "CLAUDE.md",
        ".gitignore",
        ".gitattributes",
        ".claude/settings.json",
        ".claude/skills/protocolo/SKILL.md",
        ".claude/skills/protocolo/secciones.md",
        ".claude/skills/protocolo/formatos.md",
        "estudio.yaml",
    ]
    for archivo in datos["archivos"]:
        ruta = archivo["ruta"]
        assert archivo["hash_anterior"] == hash_bytes(antes[ruta])
        assert archivo["hash_nuevo"] == hash_archivo(estudio / ruta)
    assert registro.verificar(resultado.anclaje).valido
    assert (
        json.loads((estudio / "protocolo" / "anclaje.json").read_text("utf-8"))["numero_eventos"]
        == 2
    )


def test_con_el_protocolo_en_borrador_no_advierte_desviacion(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    terminal = TerminalSimulada([f"actualizar {NUEVA}"])

    resultado = _actualizar(estudio, terminal=terminal)

    assert "protocolo: borrador" in terminal.texto
    assert "desviación" not in terminal.texto
    assert resultado.evento.datos["estado_protocolo"] == "borrador"
    assert resultado.evento.datos["version_protocolo"] is None


def test_con_el_protocolo_vigente_advierte_desviacion_y_la_registra(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _protocolo(estudio).write_bytes(RUTA_PROTOCOLO_SINTETICO.read_bytes())
    aprobacion = aprobar_protocolo(_protocolo(estudio))
    _instalar(estudio, monkeypatch)
    terminal = TerminalSimulada([f"actualizar {NUEVA}"])
    advertida_al_preguntar: list[bool] = []
    terminal.al_preguntar = lambda: advertida_al_preguntar.append("Advertencia:" in terminal.texto)

    resultado = _actualizar(estudio, terminal=terminal)

    assert advertida_al_preguntar == [True]
    assert "protocolo: vigente, versión 1.0.0" in terminal.texto
    assert (
        f"Advertencia: el protocolo está vigente (versión 1.0.0, registrada en "
        f"{aprobacion.evento.id}). Cambiar la versión del agente o sus instrucciones con el "
        "protocolo vigente es una desviación que el reporte debe declarar (PRISMA-ScR, "
        "ítem 20)."
    ) in terminal.texto
    assert resultado.evento.datos["estado_protocolo"] == "vigente"
    assert resultado.evento.datos["version_protocolo"] == "1.0.0"
    texto = "\n".join(texto_historial(construir_historial(_protocolo(estudio))))
    assert "con el protocolo vigente 1.0.0, desviación que el reporte declara" in texto
    assert validar_archivo(_protocolo(estudio)).valido


@pytest.mark.parametrize(
    ("estado", "version_protocolo"), [("vigente", None), ("borrador", "1.0.0")]
)
def test_el_evento_exige_version_si_y_solo_si_esta_vigente(
    estado: str, version_protocolo: str | None
) -> None:
    datos = _datos_actualizacion("1.0.0") | {
        "estado_protocolo": estado,
        "version_protocolo": version_protocolo,
    }

    with pytest.raises(ValidationError, match="si y solo si el protocolo está vigente"):
        DatosEstudioActualizado.model_validate(datos)


def test_despues_de_actualizar_no_hay_nota_de_instrucciones(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    _actualizar(estudio)

    assert validar_archivo(_protocolo(estudio)).notas() == []


def test_la_nota_compara_contra_la_ultima_actualizacion(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    _actualizar(estudio)
    (estudio / "CLAUDE.md").write_text("# Otro contenido\n", encoding="utf-8")

    [nota] = validar_archivo(_protocolo(estudio)).notas()

    assert nota.startswith(
        "instrucciones del agente modificadas desde su registro en evt-000002: cambiaron CLAUDE.md."
    )
    assert "use `agentresearch estudio actualizar` en su terminal" in nota


def test_historial_muestra_la_actualizacion(estudio: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(estudio, monkeypatch)
    _actualizar(estudio)

    historial = construir_historial(_protocolo(estudio))

    texto = "\n".join(texto_historial(historial))
    assert f"agente actualizado: {INSTALADA} → {NUEVA}, el " in texto
    assert (
        f"por investigador-1 (evt-000002), con el protocolo en borrador: {JUSTIFICACION}" in texto
    )
    [actualizacion_json] = historial.como_dict()["actualizaciones_agente"]
    assert actualizacion_json["evento"] == "evt-000002"


def test_con_la_misma_version_restaura_instrucciones_editadas_a_mano(
    estudio: Path,
) -> None:
    original = (estudio / "CLAUDE.md").read_bytes()
    (estudio / "CLAUDE.md").write_text("# Editado a mano\n", encoding="utf-8")

    resultado = _actualizar(estudio, [f"actualizar {INSTALADA}"])

    assert resultado.version_anterior == resultado.version_nueva == INSTALADA
    assert resultado.archivos_cambiados == ["CLAUDE.md"]
    assert (estudio / "CLAUDE.md").read_bytes() == original
    assert validar_archivo(_protocolo(estudio)).notas() == []


def test_recrea_un_archivo_administrado_que_falta(estudio: Path) -> None:
    original = (estudio / ".gitattributes").read_bytes()
    (estudio / ".gitattributes").unlink()
    terminal = TerminalSimulada([f"actualizar {INSTALADA}"])

    resultado = _actualizar(estudio, terminal=terminal)

    assert (estudio / ".gitattributes").read_bytes() == original
    assert "--- /dev/null" in terminal.texto
    [archivo] = [a for a in resultado.evento.datos["archivos"] if a["ruta"] == ".gitattributes"]
    assert archivo["hash_anterior"] is None


def test_la_justificacion_puede_venir_de_un_archivo(
    estudio: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    archivo = tmp_path / "justificacion.json"
    archivo.write_text(json.dumps({"justificacion": JUSTIFICACION}), encoding="utf-8")

    resultado = actualizar_estudio(
        estudio,
        "investigador-1",
        TerminalSimulada([f"actualizar {NUEVA}"]),
        archivo_justificacion=archivo,
    )

    assert resultado.evento.datos["justificacion"] == JUSTIFICACION


# --- Rechazos, sin escribir nada ------------------------------------------------------


def _rechazo(estudio: Path, **opciones: Any) -> list[str]:
    antes = _instantanea(estudio)
    with pytest.raises(ErrorCicloDeVida) as informacion:
        _actualizar(estudio, **opciones)
    assert _instantanea(estudio) == antes
    return informacion.value.errores


def test_rechaza_si_no_hay_nada_que_actualizar(estudio: Path) -> None:
    [error] = _rechazo(estudio)

    assert error.startswith(f"nada que actualizar: el estudio ya usa agentresearch {INSTALADA}")


def test_rechaza_sin_terminal_interactiva(estudio: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(estudio, monkeypatch)
    antes = _instantanea(estudio)

    with pytest.raises(ErrorCicloDeVida) as informacion:
        _actualizar(estudio, terminal=TerminalSimulada(interactiva=False))

    assert informacion.value.errores == [MENSAJE_SIN_TERMINAL]
    assert _instantanea(estudio) == antes


def test_se_cancela_sin_la_frase_exacta(estudio: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(estudio, monkeypatch)
    antes = _instantanea(estudio)

    with pytest.raises(OperacionCancelada, match=f"no se escribió «actualizar {NUEVA}»"):
        _actualizar(estudio, ["actualizar"])

    assert _instantanea(estudio) == antes


def test_se_cancela_si_un_archivo_cambia_mientras_se_confirma(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar(estudio, monkeypatch)
    claude_md = estudio / "CLAUDE.md"

    def editar_mientras_confirma() -> None:
        claude_md.write_text("# Edición ajena\n", encoding="utf-8")

    terminal = TerminalSimulada([f"actualizar {NUEVA}"], al_preguntar=editar_mientras_confirma)

    with pytest.raises(OperacionCancelada, match="CLAUDE.md cambió mientras se confirmaba"):
        _actualizar(estudio, terminal=terminal)

    assert len(RegistroEncadenado(estudio / "protocolo" / "eventos.jsonl").leer()) == 1


@pytest.mark.parametrize(
    ("revisor", "esperado"),
    [("claude", "es un revisor de tipo llm"), ("nadie", "no es un revisor humano declarado")],
)
def test_rechaza_un_revisor_que_no_es_humano_declarado(
    estudio: Path, monkeypatch: pytest.MonkeyPatch, revisor: str, esperado: str
) -> None:
    _instalar(estudio, monkeypatch)
    antes = _instantanea(estudio)

    with pytest.raises(ErrorCicloDeVida) as informacion:
        actualizar_estudio(
            estudio, revisor, TerminalSimulada([f"actualizar {NUEVA}"]), JUSTIFICACION
        )

    assert any(esperado in error for error in informacion.value.errores)
    assert _instantanea(estudio) == antes


def test_rechaza_si_pyproject_no_fija_la_version_instalada(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(actualizacion, "version", lambda _paquete: NUEVA)

    [error] = _rechazo(estudio)

    assert f"pero la versión instalada es {NUEVA}: ejecute `uv sync`" in error


@pytest.mark.parametrize(
    ("contenido", "esperado"),
    [
        (None, "no se pudo leer pyproject.toml"),
        ("[project\n", "no se pudo leer pyproject.toml"),
        ('[project]\ndependencies = ["pydantic"]\n', "una sola dependencia"),
    ],
    ids=["falta", "mal-formado", "sin-agente"],
)
def test_rechaza_un_pyproject_no_valido(
    estudio: Path, contenido: str | None, esperado: str
) -> None:
    pyproject = estudio / "pyproject.toml"
    if contenido is None:
        pyproject.unlink()
    else:
        pyproject.write_text(contenido, encoding="utf-8")

    errores = _rechazo(estudio)

    assert any(esperado in error for error in errores), errores


@pytest.mark.parametrize(
    ("opciones", "esperado"),
    [
        ({"justificacion": None}, "dé la justificación con --justificacion o con --archivo"),
        ({"justificacion": "   "}, "la justificación no puede estar vacía"),
    ],
)
def test_rechaza_una_justificacion_no_valida(
    estudio: Path, opciones: dict[str, Any], esperado: str
) -> None:
    [error] = _rechazo(estudio, **opciones)

    assert error.startswith(esperado)


def test_rechaza_un_archivo_de_justificacion_no_valido(estudio: Path, tmp_path: Path) -> None:
    archivo = tmp_path / "justificacion.json"
    archivo.write_text('{"justificacion": ""}', encoding="utf-8")

    errores = _rechazo(estudio, justificacion=None, archivo_justificacion=archivo)

    assert errores and "justificacion" in errores[0]


def test_rechaza_sin_estudio_yaml(estudio: Path) -> None:
    (estudio / "estudio.yaml").unlink()

    [error] = _rechazo(estudio)

    assert "no existe" in error and "use --estudio" in error


def test_rechaza_un_estudio_yaml_no_valido(estudio: Path) -> None:
    (estudio / "estudio.yaml").write_text("version_esquema: 2\n", encoding="utf-8")

    [error] = _rechazo(estudio)

    assert error.startswith("estudio.yaml no es válido")


def test_rechaza_un_registro_roto(estudio: Path) -> None:
    eventos = estudio / "protocolo" / "eventos.jsonl"
    eventos.write_text(eventos.read_text(encoding="utf-8").replace("zarambo", "otro"), "utf-8")

    errores = _rechazo(estudio)

    assert errores[0].startswith("el registro de eventos no es íntegro (P-E10)")


def test_rechaza_un_estudio_sin_evento_de_creacion(estudio: Path) -> None:
    (estudio / "protocolo" / "eventos.jsonl").unlink()
    (estudio / "protocolo" / "anclaje.json").unlink()

    [error] = _rechazo(estudio)

    assert "no tiene el evento estudio_creado" in error


def test_rechaza_si_estudio_yaml_no_coincide_con_el_registro(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = estudio / "estudio.yaml"
    ruta.write_text(
        ruta.read_text(encoding="utf-8").replace(f'version: "{INSTALADA}"', 'version: "0.0.9"'),
        encoding="utf-8",
    )

    errores = _rechazo(estudio)

    assert any("estudio.yaml dice que el agente es 0.0.9" in error for error in errores)


def test_rechaza_si_no_puede_leer_el_protocolo(estudio: Path) -> None:
    _protocolo(estudio).write_text("version_esquema: 1\nestado: [\n", encoding="utf-8")

    errores = _rechazo(estudio)

    assert any("para comprobar el revisor" in error for error in errores)


# --- Actualización interrumpida ------------------------------------------------------


def _interrumpir(estudio: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Registra la actualización y falla al escribir el primer archivo."""
    _instalar(estudio, monkeypatch)

    def fallar(_ruta: Path, _contenido: bytes) -> None:
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(actualizacion, "escribir_atomico", fallar)
    with pytest.raises(OSError, match="simulado"):
        _actualizar(estudio)
    monkeypatch.undo()


def test_volver_a_ejecutar_completa_una_actualizacion_interrumpida(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrumpir(estudio, monkeypatch)
    _instalar(estudio, monkeypatch)
    assert leer_estudio(estudio / "estudio.yaml").agente.version == INSTALADA

    resultado = _actualizar(estudio, terminal=TerminalSimulada(interactiva=False))

    assert resultado.completada
    assert resultado.evento.id == "evt-000002"
    assert leer_estudio(estudio / "estudio.yaml").agente.version == NUEVA
    assert len(RegistroEncadenado(estudio / "protocolo" / "eventos.jsonl").leer()) == 2
    assert validar_archivo(_protocolo(estudio)).notas() == []


def test_no_completa_con_otra_version_instalada(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrumpir(estudio, monkeypatch)
    monkeypatch.setattr(actualizacion, "version", lambda _paquete: "8.8.8")

    [error] = _rechazo(estudio)

    assert "se interrumpió antes de escribir los archivos, y la versión instalada es 8.8.8" in error


def test_no_completa_si_los_archivos_no_coinciden_con_los_registrados(
    estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrumpir(estudio, monkeypatch)
    _instalar(estudio, monkeypatch)
    monkeypatch.setattr(actualizacion, "texto_estudio", lambda _estudio: "otro contenido\n")

    [error] = _rechazo(estudio)

    assert "no coinciden con los registrados; restaure el estudio con Git" in error


# --- Coherencia del registro (P-E10) --------------------------------------------------


def _datos_actualizacion(version_anterior: str) -> dict[str, Any]:
    return {
        "version_anterior": version_anterior,
        "version_nueva": NUEVA,
        "fuente_anterior": "f",
        "fuente_nueva": "g",
        "archivos": [],
        "instrucciones": [],
        "estado_protocolo": "borrador",
        "version_protocolo": None,
        "justificacion": "j",
        "actualizado_por": {"tipo": "humano", "id": "investigador-1"},
    }


def test_una_actualizacion_sin_creacion_es_p_e10(protocolo_de_estudio: Path) -> None:
    agregar_evento(protocolo_de_estudio, "estudio_actualizado", _datos_actualizacion("1.0.0"))

    estado = leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio))

    assert estado.problemas == [
        "evt-000001 registra una actualización del agente sin la creación del estudio"
    ]


def test_una_actualizacion_que_no_encadena_versiones_es_p_e10(estudio: Path) -> None:
    agregar_evento(_protocolo(estudio), "estudio_actualizado", _datos_actualizacion("0.0.9"))

    estado = leer_estado_registro(RutasProtocolo.desde(_protocolo(estudio)))

    assert estado.problemas == [
        f"evt-000002 actualiza el agente desde 0.0.9, pero la versión registrada es {INSTALADA}"
    ]


# --- CLI ------------------------------------------------------------------------------


def test_cli_estudio_actualizar_en_texto(
    estudio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _instalar(estudio, monkeypatch)

    codigo = ejecutar_estudio_actualizar(
        "investigador-1",
        JUSTIFICACION,
        estudio=estudio,
        terminal=TerminalSimulada([f"actualizar {NUEVA}"]),
        reloj=reloj_incremental(),
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert f"estudio actualizado: agentresearch {INSTALADA} → {NUEVA}" in salida
    assert "evento: evt-000002 (estudio_actualizado)" in salida
    assert f'git commit -am "Actualizar el agente a {NUEVA} (anclaje evt-000002@sha256:' in salida


def test_cli_estudio_actualizar_en_json(
    estudio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _instalar(estudio, monkeypatch)

    codigo = ejecutar_estudio_actualizar(
        "investigador-1",
        JUSTIFICACION,
        estudio=estudio,
        como_json=True,
        terminal=TerminalSimulada([f"actualizar {NUEVA}"]),
    )

    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert salida.isascii()
    assert codigo == 0
    assert datos["exito"] is True
    resultado = datos["resultado"]
    assert resultado["completada"] is False
    assert resultado["version_nueva"] == NUEVA
    assert resultado["tipo_evento"] == "estudio_actualizado"
    assert resultado["anclaje"].startswith("evt-000002@sha256:")


def test_cli_estudio_actualizar_completada(
    estudio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _interrumpir(estudio, monkeypatch)
    _instalar(estudio, monkeypatch)
    capsys.readouterr()

    codigo = ejecutar_estudio_actualizar("investigador-1", JUSTIFICACION, estudio=estudio)

    assert codigo == 0
    assert "se completó la actualización a agentresearch 9.9.9 registrada en evt-000002" in (
        capsys.readouterr().out
    )


def test_cli_estudio_actualizar_rechazado_en_json(
    estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_estudio_actualizar(
        "investigador-1", JUSTIFICACION, estudio=estudio, como_json=True
    )

    datos = json.loads(capsys.readouterr().out)
    assert codigo == 1
    assert datos["comando"] == "estudio actualizar"
    assert datos["exito"] is False
    assert datos["errores"][0].startswith("nada que actualizar")


def test_main_estudio_actualizar_sin_terminal(
    estudio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _instalar(estudio, monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentresearch",
            "estudio",
            "actualizar",
            "--actualizado-por",
            "investigador-1",
            "--justificacion",
            JUSTIFICACION,
            "--estudio",
            str(estudio),
        ],
    )

    with pytest.raises(SystemExit) as salida:
        main()

    # La prueba no corre en una consola interactiva: el comando se niega.
    assert salida.value.code == 1
    assert "exige una terminal interactiva" in capsys.readouterr().out


def test_main_estudio_actualizar_exige_una_justificacion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["agentresearch", "estudio", "actualizar", "--actualizado-por", "x"]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 2
    assert "--justificacion" in capsys.readouterr().err
