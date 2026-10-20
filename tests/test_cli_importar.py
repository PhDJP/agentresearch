"""Pruebas de `agentresearch importar leer` (todo sintético; tema ficticio)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentresearch.cli import (
    construir_analizador,
    ejecutar_importar_historial,
    ejecutar_importar_leer,
    ejecutar_importar_registrar,
    main,
)

from .apoyo import TerminalSimulada
from .apoyo_busquedas import crear_estudio, reloj_de_registro
from .apoyo_importacion import csv_texto, escribir

TITULO = "Abejas de cristal secretas"


def _ris(*, eid: str | None, doi: str, titulo: str = TITULO) -> str:
    lineas = ["TY  - JOUR", "AU  - Cristal, A.", f"TI  - {titulo}", "PY  - 2024"]
    lineas += [f"DO  - {doi}", "AB  - Resumen ficticio.", "DB  - Scopus"]
    if eid is not None:
        lineas.append(f"N1  - EID: {eid}")
    lineas.append("ER  - ")
    return "\n".join(lineas) + "\n\n"


def _archivo(carpeta: Path, nombre: str, texto: str) -> Path:
    return escribir(carpeta / nombre, texto)


def _salida_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    datos: dict[str, object] = json.loads(capsys.readouterr().out)
    return datos


def test_lectura_correcta_devuelve_cero_y_no_muestra_valores(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))

    codigo = ejecutar_importar_leer([a], "ris", "scopus")

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "registros: 1" in salida
    assert "total de registros: 1" in salida
    assert "sin errores ni advertencias" in salida
    assert TITULO not in salida
    assert "10.5555/A.1" not in salida
    assert "2-s2.0-1" not in salida


def test_json_tiene_la_forma_comun_y_no_lleva_registros(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))

    codigo = ejecutar_importar_leer([a], "ris", "scopus", como_json=True)

    texto = capsys.readouterr().out
    datos = json.loads(texto)
    assert codigo == 0
    assert datos["comando"] == "importar leer"
    assert datos["exito"] is True
    assert datos["errores"] == []
    assert "version_agente" in datos
    resultado = datos["resultado"]
    assert set(resultado) == {"archivos", "no_leidos", "total"}
    assert resultado["archivos"][0]["registros"] == 1
    assert resultado["total"]["registros"] == 1
    assert set(resultado["total"]) >= {"registros", "repetidos_entre_archivos", "cobertura"}
    assert TITULO not in texto
    assert "10.5555/A.1" not in texto


def test_suma_los_registros_de_varias_tandas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))
    b = _archivo(tmp_path, "b.ris", _ris(eid="2-s2.0-2", doi="10.5555/A.2"))

    codigo = ejecutar_importar_leer([a, b], "ris", "scopus", como_json=True)

    datos = _salida_json(capsys)
    assert codigo == 0
    assert datos["resultado"]["total"]["registros"] == 2  # type: ignore[index]


def test_identificador_repetido_entre_archivos_es_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))
    b = _archivo(tmp_path, "b.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.2"))

    codigo = ejecutar_importar_leer([a, b], "ris", "scopus", como_json=True)

    datos = _salida_json(capsys)
    total = datos["resultado"]["total"]  # type: ignore[index]
    assert codigo == 1
    assert datos["exito"] is False
    assert len(total["repetidos_entre_archivos"]) == 1
    assert total["repetidos_entre_archivos"][0]["regla"] == "L-E03"
    assert "2-s2.0-1" not in json.dumps(datos)


def test_doi_repetido_sin_identificador_es_solo_advertencia(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid=None, doi="10.5555/A.1"))
    b = _archivo(tmp_path, "b.ris", _ris(eid=None, doi="10.5555/A.1"))

    codigo = ejecutar_importar_leer([a, b], "ris", "scopus")

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "L-A05" in salida
    assert "advertencia" in salida


def test_archivo_inexistente_es_uno_y_se_leen_los_demas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))

    codigo = ejecutar_importar_leer(
        [tmp_path / "no_existe.ris", a], "ris", "scopus", como_json=True
    )

    datos = _salida_json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert len(datos["errores"]) == 1  # type: ignore[arg-type]
    assert "no_existe.ris" in datos["errores"][0]  # type: ignore[index]
    assert datos["resultado"]["total"]["registros"] == 1  # type: ignore[index]


def test_archivo_no_utf8_es_error_de_lectura(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = tmp_path / "latin.ris"
    a.write_bytes("TY  - JOUR\nTI  - Abejas ñ\nER  - \n".encode("latin-1"))

    codigo = ejecutar_importar_leer([a], "ris", "scopus")

    assert codigo == 1
    assert "L-E01" in capsys.readouterr().out


def _csv_y_mapeo(carpeta: Path) -> tuple[Path, Path]:
    encabezado = ["Identificador", "Titulo", "DOI"]
    filas = [["000-1", "Abejas de cristal", "10.5555/A.1"]]
    csv_ = _archivo(carpeta, "lens.csv", csv_texto(encabezado, filas))
    mapeo = _archivo(
        carpeta,
        "mapeo.json",
        json.dumps({"Identificador": "id_fuente:lens_id", "Titulo": "titulo", "DOI": "doi"}),
    )
    return csv_, mapeo


def test_csv_con_mapeo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    csv_, mapeo = _csv_y_mapeo(tmp_path)

    codigo = ejecutar_importar_leer([csv_], "csv", "lens", mapeo, como_json=True)

    datos = _salida_json(capsys)
    assert codigo == 0
    assert datos["resultado"]["archivos"][0]["hash_mapeo"]  # type: ignore[index]


@pytest.mark.parametrize("contenido", [None, "esto no es json"])
def test_mapeo_ilegible_es_uno_y_no_lee_el_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], contenido: str | None
) -> None:
    csv_, mapeo = _csv_y_mapeo(tmp_path)
    if contenido is None:
        mapeo.unlink()
    else:
        mapeo.write_text(contenido, encoding="utf-8")

    codigo = ejecutar_importar_leer([csv_], "csv", "lens", mapeo, como_json=True)

    datos = _salida_json(capsys)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["resultado"] is None
    assert len(datos["errores"]) == 1  # type: ignore[arg-type]


def test_no_escribe_nada(tmp_path: Path) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))
    antes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    ejecutar_importar_leer([a], "ris", "scopus")

    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == antes


def test_el_analizador_asigna_los_argumentos(tmp_path: Path) -> None:
    a, b = tmp_path / "a.ris", tmp_path / "b.ris"

    argumentos = construir_analizador().parse_args(
        ["importar", "leer", str(a), str(b), "--formato", "ris", "--fuente", "scopus", "--json"]
    )

    assert argumentos.comando == "importar"
    assert argumentos.subcomando == "leer"
    assert argumentos.archivos == [a, b]
    assert argumentos.formato == "ris"
    assert argumentos.fuente == "scopus"
    assert argumentos.como_json is True
    assert argumentos.mapeo is None


@pytest.mark.parametrize(
    "argumentos",
    [
        ["importar", "leer", "--formato", "ris", "--fuente", "scopus"],
        ["importar", "leer", "a.ris", "--fuente", "scopus"],
        ["importar", "leer", "a.ris", "--formato", "ris"],
        ["importar", "leer", "a.ris", "--formato", "pdf", "--fuente", "scopus"],
        ["importar", "leer", "a.ris", "--formato", "ris", "--fuente", " "],
        ["importar", "leer", "a.csv", "--formato", "csv", "--fuente", "lens"],
        ["importar", "leer", "a.ris", "--formato", "ris", "--fuente", "s", "--mapeo", "m.json"],
        ["importar", "leer", "a.ris", "--formato", "ris", "--fuente", "s", "--desconocida"],
    ],
)
def test_invocaciones_rechazadas_salen_con_dos_sin_leer_nada(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argumentos: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["agentresearch", *argumentos])

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 2
    assert capsys.readouterr().out == ""


def test_main_sale_con_cero_y_con_uno(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = _archivo(tmp_path, "a.ris", _ris(eid="2-s2.0-1", doi="10.5555/A.1"))
    base = ["agentresearch", "importar", "leer"]

    monkeypatch.setattr(sys, "argv", [*base, str(a), "--formato", "ris", "--fuente", "scopus"])
    with pytest.raises(SystemExit) as bien:
        main()
    monkeypatch.setattr(
        sys, "argv", [*base, str(tmp_path / "x.ris"), "--formato", "ris", "--fuente", "scopus"]
    )
    with pytest.raises(SystemExit) as mal:
        main()

    assert bien.value.code == 0
    assert mal.value.code == 1


# --- importar registrar e importar historial ---------------------------------------


def test_el_analizador_asigna_los_argumentos_de_registrar_y_de_historial(tmp_path: Path) -> None:
    analizador = construir_analizador()

    registrar = analizador.parse_args(
        ["importar", "registrar", "--busqueda", "b.json", "--registrado-por", "inv-1", "--json"]
    )
    historial = analizador.parse_args(["importar", "historial", "--estudio", str(tmp_path)])

    assert (registrar.comando, registrar.subcomando) == ("importar", "registrar")
    assert registrar.busqueda == Path("b.json")
    assert registrar.registrado_por == "inv-1"
    assert registrar.estudio == Path(".")
    assert registrar.como_json is True
    assert (historial.comando, historial.subcomando) == ("importar", "historial")
    assert historial.estudio == tmp_path


@pytest.mark.parametrize(
    "argumentos",
    [
        ["importar", "registrar", "--registrado-por", "inv-1"],
        ["importar", "registrar", "--busqueda", "b.json"],
        ["importar", "registrar", "--busqueda", "b.json", "--registrado-por", "x", "--otra"],
    ],
)
def test_registrar_con_argumentos_incompletos_sale_con_dos(
    monkeypatch: pytest.MonkeyPatch, argumentos: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentresearch", *argumentos])

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 2


def test_registrar_imprime_el_anclaje_y_el_recordatorio_de_respaldo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if shutil.which("git") is None:
        pytest.skip("Git no está instalado")
    estudio = crear_estudio(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=estudio.raiz, check=True)
    escribir(estudio.raiz / ".gitignore", "exportaciones_originales/\n")
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])
    terminal = TerminalSimulada(["2026-10-14", "09:30", "-05:00", "registrar imp-0001"])

    codigo = ejecutar_importar_registrar(
        busqueda, "investigador-1", estudio.raiz, terminal=terminal, reloj=reloj_de_registro()
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "búsqueda registrada: imp-0001" in salida
    assert "anclaje: evt-" in salida
    assert "respaldo" in salida
    assert "a.ris" not in salida.replace("exportaciones_originales/", "")


def test_registrar_rechazado_devuelve_uno_y_lista_los_problemas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    estudio = crear_estudio(tmp_path)
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)], fuente="wos")

    codigo = ejecutar_importar_registrar(
        busqueda, "claude", estudio.raiz, como_json=True, terminal=TerminalSimulada([])
    )

    datos = json.loads(capsys.readouterr().out)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["comando"] == "importar registrar"
    assert any("I-E02" in e for e in datos["errores"])
    assert any("I-E11" in e for e in datos["errores"])


def test_registrar_cancelado_devuelve_uno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if shutil.which("git") is None:
        pytest.skip("Git no está instalado")
    estudio = crear_estudio(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=estudio.raiz, check=True)
    escribir(estudio.raiz / ".gitignore", "exportaciones_originales/\n")
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])
    terminal = TerminalSimulada(["2026-10-14", "09:30", "-05:00", "no"])

    codigo = ejecutar_importar_registrar(
        busqueda, "investigador-1", estudio.raiz, terminal=terminal, reloj=reloj_de_registro()
    )

    assert codigo == 1
    assert "cancelado" in capsys.readouterr().out
    assert not (estudio.raiz / "importaciones").exists()


def test_historial_de_un_estudio_sin_protocolo_aprobado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    estudio = crear_estudio(tmp_path, aprobar=False)

    codigo = ejecutar_importar_historial(estudio.raiz)

    assert codigo == 0
    assert "no hay búsquedas registradas" in capsys.readouterr().out
