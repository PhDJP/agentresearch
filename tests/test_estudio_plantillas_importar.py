"""Plantillas del estudio para la importación (2d): permisos, `.gitignore`, publicación y skill.

Todo con estudios sintéticos y sin red.
"""

import fnmatch
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentresearch.estudio.creacion import crear_estudio
from agentresearch.registros.politica import cargar_politica, decodificar_configuracion
from agentresearch.registros.versionado import campos_versionables

MOMENTO = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

LEER = "uv run agentresearch importar leer exportacion.ris --formato ris --fuente scopus"
HISTORIAL = "uv run agentresearch importar historial"
REGISTRAR = "uv run agentresearch importar registrar --busqueda .borradores/busqueda.json"
HERRAMIENTAS = ("Bash", "PowerShell")


@pytest.fixture
def estudio(tmp_path: Path) -> Path:
    destino = tmp_path / "mapeo-zarambo"
    crear_estudio(destino, "Secado del zarambo", "claude-opus-5-5", reloj=lambda: MOMENTO)
    return destino


def _texto(estudio: Path, relativa: str) -> str:
    return estudio.joinpath(*relativa.split("/")).read_text(encoding="utf-8")


def _reglas(estudio: Path, lista: str) -> list[str]:
    configuracion = json.loads(_texto(estudio, ".claude/settings.json"))
    reglas: list[str] = configuracion["permissions"][lista]
    return reglas


def _coincide(regla: str, herramienta: str, comando: str) -> bool:
    """Coincidencia de una regla `Herramienta(patron)` con un comando, con `*` como comodín."""
    prefijo = f"{herramienta}("
    if not (regla.startswith(prefijo) and regla.endswith(")")):
        return False
    return fnmatch.fnmatchcase(comando, regla[len(prefijo) : -1])


def _alguna(reglas: list[str], herramienta: str, comando: str) -> bool:
    return any(_coincide(regla, herramienta, comando) for regla in reglas)


# --- Permisos ---------------------------------------------------------------------


@pytest.mark.parametrize("herramienta", HERRAMIENTAS)
@pytest.mark.parametrize("comando", [LEER, HISTORIAL + " --json"])
def test_leer_e_historial_estan_permitidos_y_no_negados(
    estudio: Path, herramienta: str, comando: str
) -> None:
    assert _alguna(_reglas(estudio, "allow"), herramienta, comando)
    assert not _alguna(_reglas(estudio, "deny"), herramienta, comando)


@pytest.mark.parametrize("herramienta", HERRAMIENTAS)
@pytest.mark.parametrize(
    "comando",
    [
        REGISTRAR + " --registrado-por inv-1",
        "uv run agentresearch importar registrar --busqueda b.json --registrado-por x --json",
        "cd C:\\estudio; uv run agentresearch importar registrar --busqueda b.json",
        "agentresearch importar registrar --busqueda b.json",
    ],
)
def test_registrar_esta_negado_y_no_permitido(
    estudio: Path, herramienta: str, comando: str
) -> None:
    assert _alguna(_reglas(estudio, "deny"), herramienta, comando)
    assert not _alguna(_reglas(estudio, "allow"), herramienta, comando)


def test_no_se_edita_ni_importaciones_ni_originales(estudio: Path) -> None:
    deny = _reglas(estudio, "deny")

    assert "Edit(/importaciones/**)" in deny
    assert "Edit(/exportaciones_originales/**)" in deny
    # Las reglas previas siguen vigentes.
    assert "Edit(/protocolo/**)" in deny
    assert "Bash(*agentresearch protocolo aprobar*)" in deny


# --- .gitignore y publicacion_datos.yaml ---------------------------------------------


def test_gitignore_ignora_las_exportaciones_originales(estudio: Path) -> None:
    texto = _texto(estudio, ".gitignore")

    assert "exportaciones_originales/" in texto.splitlines()
    assert "ADR-0010" in texto


def test_git_ignora_realmente_las_exportaciones_originales(estudio: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=estudio, check=True)
    original = estudio / "exportaciones_originales" / "imp-0001" / "scopus.ris"
    original.parent.mkdir(parents=True)
    original.write_text("TY  - JOUR\n", encoding="utf-8")

    ignorado = subprocess.run(
        ["git", "check-ignore", "-q", str(original)], cwd=estudio, check=False
    )
    no_ignorado = subprocess.run(
        ["git", "check-ignore", "-q", "importaciones/imp-0001/importacion.json"],
        cwd=estudio,
        check=False,
    )

    assert ignorado.returncode == 0
    assert no_ignorado.returncode == 1


def test_publicacion_datos_nace_valida_y_neutra(estudio: Path) -> None:
    contenido = (estudio / "publicacion_datos.yaml").read_bytes()
    politica = cargar_politica()

    configuracion = decodificar_configuracion(contenido, politica)

    assert set(configuracion.fuentes) == {"scopus", "wos", "acs", "lens"}
    for fuente, entrada in configuracion.fuentes.items():
        assert set(entrada.campos) == {"titulo", "autores", "doi", "fuente_publicacion"}
        assert all(not campo.base.es_completa for campo in entrada.campos.values())
        # Con la base incompleta, nada se versiona todavía.
        assert campos_versionables(fuente, politica, configuracion) == ()
    assert configuracion.evidencia_literal["resumen"].estado == "no_permitido"
    assert configuracion.respaldo_nube == {}


def test_publicacion_datos_no_nombra_instituciones(estudio: Path) -> None:
    texto = _texto(estudio, "publicacion_datos.yaml").lower()

    for nombre in ("universidad", "cauca", "unicauca", "biblioteca"):
        assert nombre not in texto


# --- CLAUDE.md y README.md ----------------------------------------------------------------


def test_claude_md_prohibe_versionar_originales_y_registros_completos(estudio: Path) -> None:
    texto = _texto(estudio, "CLAUDE.md")

    assert "`importar registrar`" in texto
    assert "`importaciones/`, `exportaciones_originales/`" in texto
    assert "no se versionan ni se copian a archivos versionados" in texto
    assert "/importar [fuente]" in texto
    # La importación ya no figura como fase no disponible.
    assert "Las búsquedas, la importación" not in texto


def test_readme_anuncia_las_carpetas_de_la_importacion(estudio: Path) -> None:
    texto = _texto(estudio, "README.md")

    assert "| `importaciones/` |" in texto
    assert "| `exportaciones_originales/` |" in texto
    assert "| `publicacion_datos.yaml` |" in texto
    assert "`/importar`" in texto


# --- Skill /importar ---------------------------------------------------------------------


def test_la_skill_solo_se_invoca_a_mano(estudio: Path) -> None:
    texto = _texto(estudio, ".claude/skills/importar/SKILL.md")

    cabecera = texto.split("---")[1]
    assert "name: importar" in cabecera
    assert "disable-model-invocation: true" in cabecera


def test_los_enlaces_de_la_skill_existen(estudio: Path) -> None:
    carpeta = estudio / ".claude" / "skills" / "importar"
    enlaces = re.findall(r"\]\(([^)#]+\.md)\)", (carpeta / "SKILL.md").read_text("utf-8"))

    assert set(enlaces) == {"formatos.md", "fuentes.md"}
    for enlace in enlaces:
        assert (carpeta / enlace).is_file()


def test_la_skill_sigue_el_procedimiento_de_la_especificacion(estudio: Path) -> None:
    texto = _texto(estudio, ".claude/skills/importar/SKILL.md")

    for fragmento in (
        "protocolo validar --json",
        "protocolo historial",
        "importar historial",
        "exportaciones_originales/",
        "estudio actualizar",
        "protocolo/ecuaciones.md",
        "el registro completo, con resumen",
        "según la documentación consultada, por verificar",
        "una cosa a la vez",
        "importar leer",
        "justificacion_diferencia",
        ".borradores/busqueda.json",
        "importar registrar --busqueda .borradores/busqueda.json --registrado-por <id>",
        "registrar imp-NNNN",
        "anclaje",
        "fuera de los servicios de nube compartidos",
        "respaldo_nube.<fuente>.estado: permitido",
        "nunca",
    ):
        assert fragmento in texto, fragmento
    # Claude no ejecuta el registro: lo ejecuta el investigador en su terminal.
    assert "Nunca ejecutes `importar registrar`" in texto


def test_la_skill_no_automatiza_acs_ni_muestra_registros(estudio: Path) -> None:
    texto = _texto(estudio, ".claude/skills/importar/SKILL.md")

    assert "búsquedas complementarias puntuales" in texto
    assert "Nunca" in texto and "automaticen la interfaz de ACS" in texto
    assert "no muestras registros ni valores de campos" in texto


def test_las_fuentes_muestran_los_maximos_como_por_verificar(estudio: Path) -> None:
    texto = _texto(estudio, ".claude/skills/importar/fuentes.md")

    assert "20 000" in texto and "1 000" in texto
    assert "por verificar" in texto
    assert "Fast 5000" in texto
    assert "no documentado" in texto


def test_el_formato_de_busqueda_de_la_skill_es_el_que_lee_el_paquete(estudio: Path) -> None:
    """El ejemplo de `formatos.md` es un `busqueda.json` válido para el paquete."""
    from agentresearch.importacion.busqueda_archivo import ArchivoDeBusqueda

    texto = _texto(estudio, ".claude/skills/importar/formatos.md")
    ejemplo = re.search(r"```json\n(.*?)\n```", texto, re.DOTALL)
    assert ejemplo is not None

    archivo = ArchivoDeBusqueda.model_validate(json.loads(ejemplo.group(1)))

    assert archivo.fuente == "scopus"
    assert archivo.formato == "ris"
    assert len(archivo.archivos) == 2
