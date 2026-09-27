"""Pruebas de `agentresearch nuevo-estudio` (ADR-0007), con datos sintéticos."""

import json
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from agentresearch.cli import ejecutar_nuevo_estudio, main
from agentresearch.estudio import creacion
from agentresearch.estudio.creacion import (
    PLANTILLAS,
    ErrorCreacion,
    crear_estudio,
    fuente_del_agente,
    renderizar,
    texto_de_plantilla,
)
from agentresearch.estudio.modelo import leer_estudio
from agentresearch.protocolo import (
    RutasProtocolo,
    leer_estado_registro,
    leer_protocolo,
    validar_archivo,
)
from agentresearch.protocolo.aprobacion import aprobar
from agentresearch.protocolo.decisiones import confirmar_decisiones, registrar_decision
from agentresearch.protocolo.ecuaciones.servicio import generar
from agentresearch.protocolo.historial import construir_historial, texto_historial
from agentresearch.protocolo.instrucciones import estado_instrucciones
from agentresearch.protocolo.secciones import SECCIONES, escribir_seccion
from agentresearch.trazabilidad import RegistroEncadenado, hash_archivo

from .apoyo import TerminalSimulada, reloj_incremental
from .conftest import RUTA_PROTOCOLO_SINTETICO

MOMENTO = datetime(2026, 9, 27, 15, 30, 0, tzinfo=UTC)
TITULO = "Secado del zarambo: un mapeo de prueba"
MODELO = "claude-opus-5-5"

ARCHIVOS_ESPERADOS = [
    ".claude/settings.json",
    ".claude/skills/protocolo/SKILL.md",
    ".claude/skills/protocolo/formatos.md",
    ".claude/skills/protocolo/secciones.md",
    ".gitattributes",
    ".gitignore",
    "CLAUDE.md",
    "README.md",
    "estudio.yaml",
    "protocolo/anclaje.json",
    "protocolo/eventos.jsonl",
    "protocolo/protocolo.yaml",
    "pyproject.toml",
]


def _crear(destino: Path, contexto: Path | None = None) -> creacion.ResultadoCreacion:
    return crear_estudio(destino, TITULO, MODELO, contexto, reloj=lambda: MOMENTO)


def _protocolo(estudio: Path) -> Path:
    return estudio / "protocolo" / "protocolo.yaml"


def _texto(estudio: Path, relativa: str) -> str:
    return estudio.joinpath(*relativa.split("/")).read_text(encoding="utf-8")


# --- Estructura -----------------------------------------------------------------------


def test_crea_todos_los_archivos_del_estudio(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"

    resultado = _crear(destino)

    assert resultado.ruta == destino.resolve()
    assert resultado.archivos == ARCHIVOS_ESPERADOS
    assert (
        sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*") if p.is_file())
        == ARCHIVOS_ESPERADOS
    )
    # No queda el directorio temporal junto al destino.
    assert [p.name for p in tmp_path.iterdir()] == ["mapeo-zarambo"]


def test_estudio_yaml_tiene_los_metadatos_y_la_version_exacta(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    estudio = leer_estudio(destino / "estudio.yaml")

    assert estudio.nombre == "mapeo-zarambo"
    assert estudio.titulo == TITULO
    assert estudio.fecha_creacion == "2026-09-27"
    assert estudio.agente.version == version("agentresearch")
    assert estudio.agente.fuente == fuente_del_agente(version("agentresearch"))
    assert estudio.modelo == MODELO
    assert estudio.licencia_datos == "CC-BY-4.0"
    assert _texto(destino, "estudio.yaml").startswith("# Metadatos del estudio")


def test_el_proyecto_uv_fija_el_agente_a_la_etiqueta_de_su_version(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    texto = _texto(destino, "pyproject.toml")

    fuente = f"git+https://github.com/PhDJP/agentresearch@v{version('agentresearch')}"
    assert f'    "agentresearch @ {fuente}",\n' in texto
    assert 'name = "mapeo-zarambo"\n' in texto
    assert "package = false\n" in texto


def test_el_protocolo_nace_de_la_plantilla_con_el_titulo(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    documento = leer_protocolo(_protocolo(destino))

    assert documento.protocolo.metadatos.titulo == TITULO
    assert documento.protocolo.estado == "borrador"
    assert f'  titulo: "{TITULO}"\n' in _texto(destino, "protocolo/protocolo.yaml")


def test_las_plantillas_no_dejan_marcadores_sin_reemplazar(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    for relativa in PLANTILLAS.values():
        texto = _texto(destino, relativa)
        assert "{{" not in texto and "}}" not in texto, relativa
        assert "\r" not in texto, relativa


def test_git_normaliza_a_lf_e_ignora_lo_que_no_se_versiona(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    assert "* text=auto eol=lf\n" in _texto(destino, ".gitattributes")
    ignorados = _texto(destino, ".gitignore").splitlines()
    for patron in (".env", ".venv/", ".borradores/", ".claude/settings.local.json", "*.pdf"):
        assert patron in ignorados
    # El ejemplo de variables de entorno, sin claves, sí se versiona.
    assert ignorados[ignorados.index(".env.*") + 1] == "!.env.ejemplo"


def test_claude_md_nombra_el_modelo_y_las_reglas(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    texto = _texto(destino, "CLAUDE.md")

    assert texto.startswith(f"# {TITULO}\n")
    assert f"fija el modelo `{MODELO}`" in texto
    assert "es de mejor esfuerzo" in texto
    assert "`protocolo aprobar`, `protocolo enmendar` y `protocolo decision confirmar`" in texto


# --- Configuración de Claude Code -----------------------------------------------------


def _configuracion(destino: Path) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(_texto(destino, ".claude/settings.json"))
    return datos


def test_la_configuracion_fija_el_modelo_exacto(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    assert _configuracion(destino)["model"] == MODELO


@pytest.mark.parametrize("herramienta", ["Bash", "PowerShell"])
def test_la_configuracion_niega_aprobar_y_confirmar_y_pregunta_al_enmendar(
    tmp_path: Path, herramienta: str
) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    permisos = _configuracion(destino)["permissions"]

    assert f"{herramienta}(*agentresearch protocolo aprobar*)" in permisos["deny"]
    assert f"{herramienta}(*agentresearch protocolo decision confirmar*)" in permisos["deny"]
    assert f"{herramienta}(*agentresearch protocolo enmendar*)" in permisos["ask"]
    for regla in permisos["allow"]:
        assert "aprobar" not in regla and "confirmar" not in regla and "enmendar" not in regla


def test_la_configuracion_niega_editar_el_protocolo_y_las_instrucciones(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    permisos = _configuracion(destino)["permissions"]

    for regla in (
        "Edit(/protocolo/**)",
        "Edit(/estudio.yaml)",
        "Edit(/CLAUDE.md)",
        "Edit(/.claude/**)",
        "Edit(/pyproject.toml)",
        "Edit(/uv.lock)",
        "Read(/.env)",
        "Read(/.env.*)",
    ):
        assert regla in permisos["deny"]
    assert "Edit(/.borradores/**)" in permisos["allow"]


def test_la_skill_protocolo_solo_la_invoca_el_investigador(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)

    texto = _texto(destino, ".claude/skills/protocolo/SKILL.md")
    _, frontmatter, cuerpo = texto.split("---\n", 2)
    datos = YAML(typ="safe").load(frontmatter)

    assert datos["name"] == "protocolo"
    assert datos["disable-model-invocation"] is True
    assert 0 < len(datos["description"]) <= 1536
    assert "[secciones.md](secciones.md)" in cuerpo
    assert "[formatos.md](formatos.md)" in cuerpo
    assert "PubMed cuando la raíz tiene menos de 4 letras" in cuerpo
    assert "ecuaciones --escribir" in cuerpo
    assert "anclaje" in cuerpo


# --- Evento inicial y anclaje ---------------------------------------------------------


def test_registra_el_evento_inicial_con_el_hash_de_cada_archivo(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    resultado = _crear(destino)
    registro = RegistroEncadenado(destino / "protocolo" / "eventos.jsonl")

    [evento] = registro.leer()

    assert registro.verificar(resultado.anclaje).valido
    assert evento.tipo == "estudio_creado"
    assert evento.fecha_hora_utc == "2026-09-27T15:30:00.000Z"
    datos = evento.datos
    assert datos["modelo"] == MODELO
    assert [a["ruta"] for a in datos["instrucciones"]] == [
        ".claude/settings.json",
        ".claude/skills/protocolo/SKILL.md",
        ".claude/skills/protocolo/formatos.md",
        ".claude/skills/protocolo/secciones.md",
        "CLAUDE.md",
    ]
    assert [a["ruta"] for a in datos["archivos"]] == [
        ".gitattributes",
        ".gitignore",
        "README.md",
        "estudio.yaml",
        "protocolo/protocolo.yaml",
        "pyproject.toml",
    ]
    for archivo in datos["archivos"] + datos["instrucciones"]:
        assert archivo["hash"] == hash_archivo(destino.joinpath(*archivo["ruta"].split("/")))
    assert datos["insumos"] == []


def test_el_estudio_recien_creado_esta_integro_y_sin_notas(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    resultado = _crear(destino)

    estado = leer_estado_registro(RutasProtocolo.desde(_protocolo(destino)))
    validacion = validar_archivo(_protocolo(destino))

    assert estado.integro
    assert estado.creacion is not None
    assert str(estado.anclaje_guardado) == str(resultado.anclaje)
    assert validacion.notas() == []
    assert not {h.id_regla for h in validacion.errores} & {"P-E09", "P-E10"}
    instrucciones = estado_instrucciones(estado)
    assert instrucciones is not None and not instrucciones.modificadas


def test_copia_el_contexto_como_insumo(tmp_path: Path) -> None:
    contexto = tmp_path / "contexto del estudio.md"
    contexto.write_bytes("# Contexto sintético\r\nEl zarambo no existe.\r\n".encode())
    destino = tmp_path / "mapeo-zarambo"

    resultado = _crear(destino, contexto)

    copia = destino / "protocolo" / "insumos" / "contexto del estudio.md"
    assert copia.read_bytes() == contexto.read_bytes()
    assert resultado.evento.datos["insumos"] == [
        {"ruta": "protocolo/insumos/contexto del estudio.md", "hash": hash_archivo(copia)}
    ]


def test_la_creacion_es_determinista(tmp_path: Path) -> None:
    primero = tmp_path / "a" / "mapeo-zarambo"
    segundo = tmp_path / "b" / "mapeo-zarambo"
    primero.parent.mkdir()
    segundo.parent.mkdir()

    _crear(primero)
    _crear(segundo)

    for relativa in ARCHIVOS_ESPERADOS:
        assert (primero / relativa).read_bytes() == (segundo / relativa).read_bytes(), relativa


# --- Rechazos -------------------------------------------------------------------------


def _rechazo(
    destino: Path, titulo: str = TITULO, modelo: str = MODELO, **opciones: Any
) -> list[str]:
    antes = sorted(p.name for p in destino.parent.iterdir()) if destino.parent.exists() else None
    with pytest.raises(ErrorCreacion) as informacion:
        crear_estudio(destino, titulo, modelo, **opciones)
    despues = sorted(p.name for p in destino.parent.iterdir()) if destino.parent.exists() else None
    assert antes == despues
    return informacion.value.errores


def test_rechaza_un_directorio_que_no_esta_vacio(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    destino.mkdir()
    (destino / "notas.txt").write_text("previo", encoding="utf-8")

    [error] = _rechazo(destino)

    assert "ya existe y no es un directorio vacío" in error
    assert (destino / "notas.txt").read_text(encoding="utf-8") == "previo"


def test_rechaza_un_archivo_con_ese_nombre(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    destino.write_text("", encoding="utf-8")

    [error] = _rechazo(destino)

    assert "ya existe y no es un directorio vacío" in error


def test_acepta_un_directorio_vacio(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    destino.mkdir()

    resultado = _crear(destino)

    assert resultado.archivos == ARCHIVOS_ESPERADOS


def test_rechaza_si_no_existe_el_directorio_padre(tmp_path: Path) -> None:
    [error] = _rechazo(tmp_path / "no-existe" / "mapeo-zarambo")

    assert error.startswith("no existe el directorio ")


@pytest.mark.parametrize("nombre", ["mapeo café", "-mapeo", "mapeo_", "estudio con espacios"])
def test_rechaza_un_nombre_de_carpeta_no_valido(tmp_path: Path, nombre: str) -> None:
    [error] = _rechazo(tmp_path / nombre)

    assert "será el nombre del estudio y del proyecto uv" in error


def test_el_nombre_se_pasa_a_minusculas(tmp_path: Path) -> None:
    resultado = _crear(tmp_path / "Mapeo-Zarambo")

    assert resultado.estudio.nombre == "mapeo-zarambo"


@pytest.mark.parametrize("titulo", ["", "   ", "Dos\nlíneas"])
def test_rechaza_un_titulo_no_valido(tmp_path: Path, titulo: str) -> None:
    [error] = _rechazo(tmp_path / "mapeo-zarambo", titulo=titulo)

    assert error == "el título no puede estar vacío ni tener saltos de línea"


@pytest.mark.parametrize("modelo", ["opus", "sonnet", "claude-opus-latest", "claude opus 5", ""])
def test_rechaza_un_modelo_que_no_es_un_identificador_exacto(tmp_path: Path, modelo: str) -> None:
    [error] = _rechazo(tmp_path / "mapeo-zarambo", modelo=modelo)

    assert "no es un identificador exacto" in error


def test_rechaza_un_contexto_inexistente(tmp_path: Path) -> None:
    [error] = _rechazo(tmp_path / "mapeo-zarambo", contexto=tmp_path / "no-existe.md")

    assert error.startswith("--contexto: no existe el archivo ")


def test_reporta_todos_los_problemas_a_la_vez(tmp_path: Path) -> None:
    errores = _rechazo(tmp_path / "mapeo café", titulo="", modelo="opus")

    assert len(errores) == 3


def test_un_fallo_a_mitad_no_deja_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fallar(_rutas: RutasProtocolo) -> None:
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(creacion, "escribir_anclaje", fallar)

    with pytest.raises(OSError, match="disco lleno"):
        _crear(tmp_path / "mapeo-zarambo")

    assert list(tmp_path.iterdir()) == []


def test_un_marcador_desconocido_es_un_error_del_paquete() -> None:
    with pytest.raises(KeyError, match="marcador desconocido"):
        renderizar("Hola {{desconocido}}", {"titulo": "x"})


def test_todas_las_plantillas_se_leen_del_paquete() -> None:
    for origen in PLANTILLAS:
        assert texto_de_plantilla(origen).strip(), origen


# --- De punta a punta: del estudio nuevo al protocolo aprobado --------------------------


def test_flujo_completo_sobre_un_estudio_nuevo(tmp_path: Path) -> None:
    destino = tmp_path / "mapeo-zarambo"
    _crear(destino)
    protocolo = _protocolo(destino)
    borradores = destino / ".borradores"
    borradores.mkdir()

    # /protocolo escribe cada sección con `protocolo escribir`.
    sintetico = YAML().load(RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8"))
    for seccion in SECCIONES:
        valor = sintetico[seccion]
        if seccion == "metadatos":
            valor["titulo"] = TITULO
        fragmento = borradores / f"{seccion}.yaml"
        with fragmento.open("w", encoding="utf-8", newline="\n") as archivo:
            YAML().dump({seccion: valor}, archivo)
        escribir_seccion(protocolo, seccion, fragmento)
    assert validar_archivo(protocolo).hallazgos == []

    # Dos decisiones propuestas por el LLM y confirmadas por el investigador.
    reloj = reloj_incremental()
    for id_decision in ("D1", "D2"):
        decision = borradores / f"decision-{id_decision}.json"
        opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
        decision.write_text(
            json.dumps(
                {
                    "id_decision": id_decision,
                    "tema": "Tema",
                    "pregunta": "¿Pregunta?",
                    "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
                    "elegida": "A",
                    "justificacion": "Elegida por el investigador.",
                    "propuesto_por": {"tipo": "llm", "modelo": MODELO},
                    "decidido_por": {"tipo": "humano", "id": "investigador-1"},
                }
            ),
            encoding="utf-8",
        )
        registrar_decision(protocolo, decision, reloj)
    confirmar_decisiones(protocolo, "investigador-1", TerminalSimulada(["confirmar 2"]), reloj)

    # El investigador aprueba en su terminal; luego se generan las ecuaciones.
    aprobar(protocolo, "investigador-1", TerminalSimulada(["aprobar 1.0.0"]), reloj=reloj)
    ecuaciones = generar(protocolo, escribir=True)

    assert ecuaciones.escrito
    validacion = validar_archivo(protocolo)
    assert validacion.valido
    assert validacion.notas() == []
    historial = construir_historial(protocolo)
    lineas = "\n".join(texto_historial(historial))
    assert f"estudio: {TITULO} (mapeo-zarambo)" in lineas
    assert "1.0.0" in lineas
    assert "D1  confirmada" in lineas and "D2  confirmada" in lineas
    registro = RegistroEncadenado(protocolo.parent / "eventos.jsonl")
    assert [e.tipo for e in registro.leer()] == [
        "estudio_creado",
        "decision_propuesta",
        "decision_propuesta",
        "decision_confirmada",
        "decision_confirmada",
        "protocolo_aprobado",
    ]
    assert registro.verificar(historial.registro.anclaje_actual).valido

    # Si se modifican las instrucciones del agente, validar lo avisa.
    (destino / "CLAUDE.md").write_text("# Otro contenido\n", encoding="utf-8")
    [nota] = validar_archivo(protocolo).notas()
    assert "instrucciones del agente modificadas" in nota


# --- CLI ------------------------------------------------------------------------------


def test_cli_nuevo_estudio_en_texto(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    destino = tmp_path / "mapeo-zarambo"

    codigo = ejecutar_nuevo_estudio(destino, TITULO, MODELO)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert f"estudio creado: {destino.resolve()}" in salida
    assert f"modelo fijado: {MODELO}" in salida
    assert "evento: evt-000001 (estudio_creado)" in salida
    assert "  protocolo/eventos.jsonl\n" in salida
    assert "  2. uv sync" in salida
    assert "gh repo create mapeo-zarambo --private --source . --push" in salida
    assert "escriba /protocolo" in salida


def test_cli_nuevo_estudio_en_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_nuevo_estudio(tmp_path / "mapeo-zarambo", TITULO, MODELO, como_json=True)

    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert salida.isascii()
    assert codigo == 0
    assert datos["comando"] == "nuevo-estudio"
    assert datos["resultado"]["estudio"]["titulo"] == TITULO
    assert datos["resultado"]["archivos"] == ARCHIVOS_ESPERADOS
    assert datos["resultado"]["anclaje"].startswith("evt-000001@sha256:")


def test_cli_nuevo_estudio_rechazado(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_nuevo_estudio(tmp_path / "mapeo-zarambo", TITULO, "opus")

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "nuevo-estudio: no se pudo crear el estudio" in salida
    assert "no es un identificador exacto" in salida


def test_main_nuevo_estudio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contexto = tmp_path / "contexto.md"
    contexto.write_text("Contexto sintético.\n", encoding="utf-8")
    destino = tmp_path / "mapeo-zarambo"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentresearch",
            "nuevo-estudio",
            str(destino),
            "--titulo",
            TITULO,
            "--modelo",
            MODELO,
            "--contexto",
            str(contexto),
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert json.loads(capsys.readouterr().out)["exito"] is True
    assert (destino / "protocolo" / "insumos" / "contexto.md").is_file()
