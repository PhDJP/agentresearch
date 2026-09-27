"""Pruebas de integración por subproceso, usando el módulo instalado.

Son herméticas respecto a la codificación: el subproceso no hereda las
variables de codificación del sistema, escribe en UTF-8 por decisión
explícita y su salida se decodifica en UTF-8 estricto.
"""

import json
import os
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from agentresearch.trazabilidad import RegistroEncadenado

from .apoyo import agregar_evento, aprobar_protocolo, decision_propuesta, reemplazar_en

VARIABLES_DE_CODIFICACION = (
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONLEGACYWINDOWSSTDIO",
    "PYTHONLEGACYWINDOWSFSENCODING",
    "PYTHONCOERCECLOCALE",
    "LC_ALL",
    "LC_CTYPE",
    "LANG",
)


def _entorno() -> dict[str, str]:
    """Entorno del subproceso: sin la codificación del sistema y con UTF-8 fijado."""
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if clave.upper() not in VARIABLES_DE_CODIFICACION
    }
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    return entorno


def _ejecutar(*argumentos: str, stdin: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentresearch", *argumentos],
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        env=_entorno(),
        check=False,
        timeout=60,
        stdin=stdin,
    )


def test_el_entorno_del_subproceso_no_hereda_la_codificacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("LC_ALL", "C")

    entorno = _entorno()

    assert entorno["PYTHONIOENCODING"] == "utf-8"
    assert entorno["PYTHONUTF8"] == "1"
    assert "LC_ALL" not in entorno


def test_el_comando_agentresearch_esta_registrado_como_punto_de_entrada() -> None:
    puntos = entry_points(group="console_scripts")
    nombres = {punto.name for punto in puntos}

    assert "agentresearch" in nombres


def test_modulo_muestra_la_version_por_subproceso() -> None:
    resultado = _ejecutar("--version")

    assert resultado.returncode == 0
    assert resultado.stdout.startswith("agentresearch ")


def test_modulo_verifica_una_cadena_integra_por_subproceso(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {"clave": "valor"})

    resultado = _ejecutar("registro", "verificar", str(archivo))

    assert resultado.returncode == 0
    assert "íntegro" in resultado.stdout


def test_modulo_detecta_una_cadena_rota_por_subproceso(tmp_path: Path) -> None:
    archivo = tmp_path / "eventos.jsonl"
    RegistroEncadenado(archivo).agregar("uno", {})
    contenido = archivo.read_text(encoding="utf-8").replace('"uno"', '"otro"')
    archivo.write_text(contenido, encoding="utf-8", newline="\n")

    resultado = _ejecutar("registro", "verificar", str(archivo))

    assert resultado.returncode == 1
    assert "inválido" in resultado.stdout


def test_modulo_reporta_error_si_el_archivo_no_existe_por_subproceso(tmp_path: Path) -> None:
    archivo = tmp_path / "no_existe.jsonl"

    resultado = _ejecutar("registro", "verificar", str(archivo))

    assert resultado.returncode == 1
    assert "no existe" in resultado.stdout


def test_modulo_rechaza_argumentos_invalidos_por_subproceso() -> None:
    resultado = _ejecutar("registro", "verificar")

    assert resultado.returncode != 0


# --- Ciclo de vida del protocolo (ADR-0008) --------------------------------------------


def test_validar_muestra_el_registro_y_su_anclaje_por_subproceso(
    protocolo_de_estudio: Path,
) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    anclaje = RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").anclaje()

    resultado = _ejecutar("protocolo", "validar", str(protocolo_de_estudio))

    assert resultado.returncode == 0
    assert f"registro: protocolo/eventos.jsonl (1 eventos, anclaje {anclaje})" in resultado.stdout


def test_historial_por_subproceso(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    resultado = _ejecutar("protocolo", "historial", str(protocolo_de_estudio), "--json")

    datos = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert datos["exito"] is True
    assert datos["resultado"]["versiones"][0]["version"] == "1.0.0"


def test_enmendar_simulado_por_subproceso(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    resultado = _ejecutar("protocolo", "enmendar", str(protocolo_de_estudio), "--simular", "--json")

    datos = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert datos["resultado"]["opciones_de_version"] == {"menor": "1.1.0", "mayor": "2.0.0"}


def test_enmendar_por_subproceso_sin_consola_se_niega(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    editado = protocolo_de_estudio.read_bytes()

    resultado = _ejecutar(
        "protocolo",
        "enmendar",
        str(protocolo_de_estudio),
        "--nivel",
        "menor",
        "--enmendado-por",
        "investigador-1",
        "--justificacion",
        "j",
        "--efecto-esperado",
        "e",
        stdin=subprocess.DEVNULL,
    )

    assert resultado.returncode == 1
    assert "exige una terminal interactiva" in resultado.stdout
    assert protocolo_de_estudio.read_bytes() == editado


def test_decision_confirmar_por_subproceso_sin_consola_se_niega(protocolo_de_estudio: Path) -> None:
    agregar_evento(protocolo_de_estudio, "decision_propuesta", decision_propuesta("O1"))
    protocolo = ["--protocolo", str(protocolo_de_estudio)]

    resultado = _ejecutar(
        "protocolo",
        "decision",
        "confirmar",
        "--confirmado-por",
        "investigador-1",
        *protocolo,
        stdin=subprocess.DEVNULL,
    )

    assert resultado.returncode == 1
    assert "exige una terminal interactiva" in resultado.stdout
    assert len(RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").leer()) == 1


def test_registro_verificar_con_anclaje_por_subproceso(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)
    eventos = protocolo_de_estudio.parent / "eventos.jsonl"
    anclaje = RegistroEncadenado(eventos).anclaje()

    cumplido = _ejecutar("registro", "verificar", str(eventos), "--anclaje", str(anclaje))
    eventos.write_bytes(b"")
    truncado = _ejecutar("registro", "verificar", str(eventos), "--anclaje", str(anclaje))

    assert cumplido.returncode == 0
    assert truncado.returncode == 1
    assert "se eliminaron eventos del final" in truncado.stdout
