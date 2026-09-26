"""Pruebas del subcomando `protocolo validar` de la CLI."""

import json
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from agentresearch.cli import (
    RUTA_PROTOCOLO_POR_DEFECTO,
    _resumen,
    construir_analizador,
    ejecutar_protocolo_validar,
    main,
)
from agentresearch.trazabilidad import hash_archivo

RUTA_PROTOCOLO_SINTETICO = Path(__file__).parent / "datos" / "protocolo_sintetico.yaml"


def _protocolo_modificado(tmp_path: Path, viejo: str, nuevo: str) -> Path:
    texto = RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8")
    assert viejo in texto
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text(texto.replace(viejo, nuevo), encoding="utf-8", newline="\n")
    return archivo


# --- Funciones -----------------------------------------------------------------


def test_protocolo_valido_devuelve_cero(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_validar(RUTA_PROTOCOLO_SINTETICO)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "(borrador, versión 0.1.0)" in salida
    assert salida.rstrip().endswith("resultado: sin errores ni advertencias")


def test_protocolo_con_errores_devuelve_uno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = _protocolo_modificado(tmp_path, "tamano_lote_llm: 25", "tamano_lote_llm: 0")

    codigo = ejecutar_protocolo_validar(archivo)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "error P-E08 en seleccion.tamano_lote_llm (línea " in salida
    assert "Referencia: Landis y Koch (1977)" in salida
    assert "resultado: 1 error, 0 advertencias" in salida


def test_protocolo_solo_con_advertencias_devuelve_cero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = _protocolo_modificado(tmp_path, "restrictivo: false", "restrictivo: true")

    codigo = ejecutar_protocolo_validar(archivo)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "advertencia P-A02" in salida
    assert "resultado: 0 errores, 1 advertencia" in salida


def test_archivo_inexistente_devuelve_uno_con_p_e00(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_validar(tmp_path / "no_existe.yaml")

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "error P-E00: el archivo no existe" in salida


def test_salida_json_de_un_protocolo_valido(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_protocolo_validar(RUTA_PROTOCOLO_SINTETICO, como_json=True)

    datos = json.loads(capsys.readouterr().out)
    assert codigo == 0
    assert datos["valido"] is True
    assert datos["version_agente"] == version("agentresearch")
    assert datos["hash_archivo"] == hash_archivo(RUTA_PROTOCOLO_SINTETICO)
    assert datos["version_esquema"] == 1
    assert datos["hallazgos"] == []


def test_salida_json_con_errores(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archivo = _protocolo_modificado(tmp_path, "      fase: titulo_resumen\n", "")

    codigo = ejecutar_protocolo_validar(archivo, como_json=True)

    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert codigo == 1
    assert datos["valido"] is False
    assert datos["errores"] == 1
    [hallazgo] = datos["hallazgos"]
    assert hallazgo["id_regla"] == "P-E05"
    assert hallazgo["referencia"] == "PRISMA-ScR, ítem 6"
    assert salida.isascii()


@pytest.mark.parametrize(
    ("errores", "advertencias", "texto"),
    [
        (0, 0, "sin errores ni advertencias"),
        (1, 0, "1 error, 0 advertencias"),
        (2, 1, "2 errores, 1 advertencia"),
        (0, 3, "0 errores, 3 advertencias"),
    ],
)
def test_resumen(errores: int, advertencias: int, texto: str) -> None:
    assert _resumen(errores, advertencias) == texto


# --- Analizador y main() --------------------------------------------------------


def test_analizador_de_protocolo_validar_con_ruta_por_defecto() -> None:
    argumentos = construir_analizador().parse_args(["protocolo", "validar"])

    assert argumentos.comando == "protocolo"
    assert argumentos.subcomando == "validar"
    assert argumentos.ruta == RUTA_PROTOCOLO_POR_DEFECTO
    assert argumentos.como_json is False


def test_analizador_de_protocolo_validar_con_ruta_y_json(tmp_path: Path) -> None:
    ruta = tmp_path / "otro.yaml"

    argumentos = construir_analizador().parse_args(["protocolo", "validar", str(ruta), "--json"])

    assert argumentos.ruta == ruta
    assert argumentos.como_json is True


def test_analizador_exige_subcomando_de_protocolo() -> None:
    with pytest.raises(SystemExit):
        construir_analizador().parse_args(["protocolo"])


def test_main_valida_la_ruta_por_defecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    destino = tmp_path / RUTA_PROTOCOLO_POR_DEFECTO
    destino.parent.mkdir()
    shutil.copyfile(RUTA_PROTOCOLO_SINTETICO, destino)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["agentresearch", "protocolo", "validar"])

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert "sin errores ni advertencias" in capsys.readouterr().out


def test_main_sale_con_uno_si_hay_errores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["agentresearch", "protocolo", "validar", str(tmp_path / "no.yaml"), "--json"]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 1
    assert json.loads(capsys.readouterr().out)["hallazgos"][0]["id_regla"] == "P-E00"


# --- Subproceso ----------------------------------------------------------------


def _ejecutar(*argumentos: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentresearch", "protocolo", "validar", *argumentos],
        capture_output=True,
        text=True,
        check=False,
    )


def test_subproceso_valida_un_protocolo_en_json() -> None:
    resultado = _ejecutar(str(RUTA_PROTOCOLO_SINTETICO), "--json")

    assert resultado.returncode == 0
    assert json.loads(resultado.stdout)["valido"] is True


def test_subproceso_sale_con_uno_si_hay_errores(tmp_path: Path) -> None:
    archivo = _protocolo_modificado(tmp_path, "avanzan: [A, B, C, D, E]", "avanzan: [B]")

    resultado = _ejecutar(str(archivo))

    assert resultado.returncode == 1
    assert "P-E06" in resultado.stdout


def test_subproceso_no_falla_con_caracteres_fuera_de_la_consola(tmp_path: Path) -> None:
    """Un término con β (fuera de cp1252) no debe romper la salida en Windows."""
    texto = RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8")
    texto = texto.replace('terminos: ["industria alimentaria"]', 'terminos: ["β-zarambina"]')
    texto = texto.replace('"dehydrat*",', '"dehydrat*", "β-zarambina",')
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_text(texto, encoding="utf-8", newline="\n")

    resultado = _ejecutar(str(archivo))
    resultado_json = _ejecutar(str(archivo), "--json")

    assert resultado.returncode == 0, resultado.stderr
    assert "P-A02" in resultado.stdout
    assert resultado.stderr == ""
    assert "β-zarambina" in json.loads(resultado_json.stdout)["hallazgos"][0]["mensaje"]


def test_subproceso_rechaza_una_opcion_desconocida() -> None:
    resultado = _ejecutar("--formato", "xml")

    assert resultado.returncode == 2
