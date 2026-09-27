"""Pruebas del comando `protocolo ecuaciones` y de la nota de ecuaciones desactualizadas.

ADR-0009, puntos 11 a 15.
"""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import (
    construir_analizador,
    ejecutar_protocolo_ecuaciones,
    ejecutar_protocolo_historial,
    ejecutar_protocolo_validar,
    main,
)
from agentresearch.protocolo import RutasProtocolo, validar_archivo
from agentresearch.protocolo.ecuaciones.documento import estado_ecuaciones, hash_de_ecuaciones
from agentresearch.protocolo.ecuaciones.servicio import ErrorEcuaciones, generar
from agentresearch.protocolo.historial import construir_historial
from agentresearch.trazabilidad import hash_archivo

from .apoyo import aprobar_protocolo, reemplazar_en

NOTA = "nota: ecuaciones desactualizadas: protocolo/ecuaciones.md no corresponde"


def _json(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    salida = capsys.readouterr().out
    assert salida.isascii()
    datos: dict[str, Any] = json.loads(salida)
    return datos


def _ecuaciones(ruta: Path) -> Path:
    return RutasProtocolo.desde(ruta).ecuaciones


def _bloquear_scopus(ruta: Path) -> None:
    """Agrega una frase con una raíz de 2 letras y sin variantes: Scopus no la admite."""
    reemplazar_en(ruta, '"dehydrat*"', '"dehydrat*", "\\"freeze dr*\\""')


# --- Generar sin escribir -------------------------------------------------------------


def test_sin_escribir_muestra_las_ecuaciones_y_no_crea_el_archivo(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert salida.startswith("# Ecuaciones de búsqueda\n")
    assert f"- Hash del protocolo: {hash_archivo(protocolo_de_estudio)}" in salida
    assert "TITLE-ABS-KEY((zarambo" in salida
    assert "(no se escribió protocolo/ecuaciones.md; use --escribir para guardarlo)" in salida
    assert not _ecuaciones(protocolo_de_estudio).exists()


def test_en_json(protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio, como_json=True)

    datos = _json(capsys)
    assert codigo == 0
    assert datos["comando"] == "protocolo ecuaciones"
    assert datos["exito"] is True
    assert datos["errores"] == []
    assert datos["version_agente"] == version("agentresearch")
    assert datos["escrito"] is False
    assert datos["fuentes_bloqueadas"] == []
    resultado = datos["resultado"]
    assert resultado["escrito"] is False
    assert resultado["fuentes_bloqueadas"] == []
    assert resultado["fuentes_sin_traductor"] == []
    assert resultado["hash_protocolo"] == hash_archivo(protocolo_de_estudio)
    assert resultado["ruta_ecuaciones"] == "protocolo/ecuaciones.md"
    assert [e["fuente"] for e in resultado["ecuaciones"]] == ["openalex", "scopus", "generica"]


# --- Escribir -----------------------------------------------------------------------


def test_escribir_guarda_ecuaciones_md(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio, escribir=True)

    salida = capsys.readouterr().out
    archivo = _ecuaciones(protocolo_de_estudio)
    assert codigo == 0
    assert "ecuaciones escritas en protocolo/ecuaciones.md" in salida
    assert "  - Scopus: generada (" in salida
    contenido = archivo.read_bytes()
    assert b"\r" not in contenido
    assert hash_de_ecuaciones(contenido.decode("utf-8")) == hash_archivo(protocolo_de_estudio)
    assert contenido.decode("utf-8") == generar(protocolo_de_estudio).texto


def test_escribir_dos_veces_da_los_mismos_bytes(protocolo_de_estudio: Path) -> None:
    generar(protocolo_de_estudio, escribir=True)
    primero = _ecuaciones(protocolo_de_estudio).read_bytes()
    generar(protocolo_de_estudio, escribir=True)

    assert _ecuaciones(protocolo_de_estudio).read_bytes() == primero


def test_con_una_fuente_bloqueada_escribe_igual_y_sale_con_uno(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bloquear_scopus(protocolo_de_estudio)

    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio, escribir=True)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "  - Scopus: bloqueada (" in salida
    assert "fuentes bloqueadas, sin ecuación: openalex, scopus" in salida
    assert "**Sin ecuación:**" in _ecuaciones(protocolo_de_estudio).read_text(encoding="utf-8")


def test_con_una_fuente_bloqueada_el_json_la_distingue_de_un_rechazo(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bloquear_scopus(protocolo_de_estudio)

    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio, escribir=True, como_json=True)

    datos = _json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["errores"] == []
    assert datos["escrito"] is True
    assert datos["fuentes_bloqueadas"] == ["openalex", "scopus"]


def test_una_fuente_bloqueada_sin_escribir_tambien_sale_con_uno(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _bloquear_scopus(protocolo_de_estudio)

    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio)

    assert codigo == 1
    assert "fuentes bloqueadas, sin ecuación: openalex, scopus" in capsys.readouterr().out
    assert not _ecuaciones(protocolo_de_estudio).exists()


# --- Rechazos (no se escribe nada) --------------------------------------------------


@pytest.mark.parametrize(
    ("viejo", "nuevo", "regla"),
    [
        ('"dehydrat*"', '"dehydrat*", "fruto seco"', "P-E11"),
        ('["secado", "drying", "dehydrat*", "liofilización"]', "[]", "P-E04"),
        ("version_esquema: 1", "version_esquema: 7", "P-E00"),
    ],
)
def test_se_niega_si_el_protocolo_no_se_puede_traducir(
    protocolo_de_estudio: Path,
    capsys: pytest.CaptureFixture[str],
    viejo: str,
    nuevo: str,
    regla: str,
) -> None:
    reemplazar_en(protocolo_de_estudio, viejo, nuevo)

    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio, escribir=True, como_json=True)

    datos = _json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["escrito"] is False
    assert datos["fuentes_bloqueadas"] == []
    assert any(regla in error for error in datos["errores"])
    assert not _ecuaciones(protocolo_de_estudio).exists()


def test_otros_errores_del_protocolo_no_impiden_traducir(protocolo_de_estudio: Path) -> None:
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 0")
    assert any(h.id_regla == "P-E08" for h in validar_archivo(protocolo_de_estudio).errores)

    resultado = generar(protocolo_de_estudio, escribir=True)

    assert resultado.escrito


def test_el_rechazo_en_texto(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reemplazar_en(protocolo_de_estudio, '"dehydrat*"', '"dehydrat*", "fruto seco"')

    codigo = ejecutar_protocolo_ecuaciones(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "protocolo ecuaciones: no se pudieron generar" in salida
    assert "error P-E11" in salida


# --- P-E09: cambio sin enmienda registrada -------------------------------------------


@pytest.fixture
def vigente_editado(protocolo_de_estudio: Path) -> Path:
    aprobar_protocolo(protocolo_de_estudio)
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")
    return protocolo_de_estudio


def test_con_p_e09_escribir_se_niega(vigente_editado: Path) -> None:
    with pytest.raises(ErrorEcuaciones) as error:
        generar(vigente_editado, escribir=True)

    [mensaje] = error.value.errores
    assert mensaje.startswith("error P-E09")
    assert not _ecuaciones(vigente_editado).exists()


def test_con_p_e09_sin_escribir_lo_avisa(
    vigente_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_ecuaciones(vigente_editado)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "aviso: error P-E09" in salida


def test_con_p_e09_sin_escribir_lo_avisa_en_json(
    vigente_editado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_protocolo_ecuaciones(vigente_editado, como_json=True)

    [aviso] = _json(capsys)["resultado"]["avisos"]
    assert aviso.startswith("error P-E09")


# --- Nota de ecuaciones desactualizadas (ADR-0009, punto 14) -------------------------


def test_sin_ecuaciones_md_no_hay_nota(protocolo_de_estudio: Path) -> None:
    resultado = validar_archivo(protocolo_de_estudio)

    assert resultado.ecuaciones is not None
    assert resultado.ecuaciones.existe is False
    assert resultado.como_dict()["ecuaciones_desactualizadas"] is False


def test_ecuaciones_al_dia_no_dan_nota(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generar(protocolo_de_estudio, escribir=True)

    ejecutar_protocolo_validar(protocolo_de_estudio)
    ejecutar_protocolo_historial(protocolo_de_estudio)

    assert "ecuaciones desactualizadas" not in capsys.readouterr().out


def test_tras_aprobar_las_ecuaciones_quedan_desactualizadas(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generar(protocolo_de_estudio, escribir=True)
    hash_borrador = hash_archivo(protocolo_de_estudio)
    aprobar_protocolo(protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_protocolo_validar(protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0  # no bloquea ni exige justificación
    assert NOTA in salida
    assert f"se generaron para el protocolo con hash {hash_borrador}" in salida
    assert "agentresearch protocolo ecuaciones --escribir" in salida
    assert validar_archivo(protocolo_de_estudio).advertencias == []


def test_validar_en_json_marca_las_ecuaciones_desactualizadas(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generar(protocolo_de_estudio, escribir=True)
    aprobar_protocolo(protocolo_de_estudio)
    capsys.readouterr()

    ejecutar_protocolo_validar(protocolo_de_estudio, como_json=True)

    datos = _json(capsys)
    assert datos["ecuaciones_desactualizadas"] is True
    assert datos["ecuaciones"]["existe"] is True


def test_historial_marca_las_ecuaciones_desactualizadas(
    protocolo_de_estudio: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generar(protocolo_de_estudio, escribir=True)
    aprobar_protocolo(protocolo_de_estudio)
    capsys.readouterr()

    ejecutar_protocolo_historial(protocolo_de_estudio)
    assert NOTA in capsys.readouterr().out
    ejecutar_protocolo_historial(protocolo_de_estudio, como_json=True)
    assert _json(capsys)["resultado"]["ecuaciones_desactualizadas"] is True


def test_regenerar_tras_aprobar_quita_la_nota(protocolo_de_estudio: Path) -> None:
    generar(protocolo_de_estudio, escribir=True)
    aprobar_protocolo(protocolo_de_estudio)

    generar(protocolo_de_estudio, escribir=True)

    assert construir_historial(protocolo_de_estudio).ecuaciones.desactualizadas is False


@pytest.mark.parametrize("contenido", [b"# Ecuaciones editadas a mano\n", b"\xff\xfe no es UTF-8"])
def test_ecuaciones_sin_hash_legible_se_marcan_desactualizadas(
    protocolo_de_estudio: Path, contenido: bytes
) -> None:
    _ecuaciones(protocolo_de_estudio).write_bytes(contenido)

    estado = estado_ecuaciones(
        RutasProtocolo.desde(protocolo_de_estudio), hash_archivo(protocolo_de_estudio)
    )

    assert estado.desactualizadas is True
    nota = estado.nota()
    assert nota is not None
    assert "su cabecera no tiene el hash del protocolo de origen" in nota


def test_con_el_protocolo_ilegible_no_hay_nota(protocolo_de_estudio: Path) -> None:
    generar(protocolo_de_estudio, escribir=True)

    estado = estado_ecuaciones(RutasProtocolo.desde(protocolo_de_estudio), None)

    assert estado.desactualizadas is False
    assert estado.nota() is None


# --- Analizador y subproceso ----------------------------------------------------------


def test_el_analizador_de_ecuaciones(tmp_path: Path) -> None:
    ruta = tmp_path / "p.yaml"
    argumentos = construir_analizador().parse_args(
        ["protocolo", "ecuaciones", str(ruta), "--escribir", "--json"]
    )

    assert argumentos.subcomando == "ecuaciones"
    assert argumentos.ruta == ruta
    assert argumentos.escribir is True
    assert argumentos.como_json is True


def test_ecuaciones_por_subproceso(protocolo_de_estudio: Path) -> None:
    resultado = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentresearch",
            "protocolo",
            "ecuaciones",
            str(protocolo_de_estudio),
            "--escribir",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    datos = json.loads(resultado.stdout)
    assert datos["escrito"] is True
    assert _ecuaciones(protocolo_de_estudio).is_file()


def test_main_ecuaciones(
    protocolo_de_estudio: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["agentresearch", "protocolo", "ecuaciones", str(protocolo_de_estudio)]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert capsys.readouterr().out.startswith("# Ecuaciones de búsqueda\n")
