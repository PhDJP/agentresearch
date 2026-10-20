"""Pruebas de `importar historial` y de la regla P-E10 ampliada (todo sintético)."""

import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import ejecutar_importar_historial
from agentresearch.importacion.historial import construir_historial_importaciones
from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.ciclo_de_vida import escribir_anclaje
from agentresearch.trazabilidad import RegistroEncadenado

from .apoyo_busquedas import Estudio, crear_estudio


@pytest.fixture
def estudio(tmp_path: Path) -> Estudio:
    return crear_estudio(tmp_path)


def _registrar_dos(estudio: Estudio) -> None:
    estudio.registrar(
        estudio.busqueda([estudio.archivo_ris("a.ris", 1, 2), estudio.archivo_ris("b.ris", 3)])
    )
    estudio.registrar(
        estudio.busqueda([estudio.archivo_ris("c.ris", 4)]),
        respuestas=["2026-10-14", "10:00", "", "registrar imp-0002"],
    )


def _datos_del_primer_evento(estudio: Estudio) -> dict[str, Any]:
    rutas = RutasProtocolo.desde(estudio.protocolo)
    [evento] = [
        e for e in RegistroEncadenado(rutas.eventos).leer() if e.tipo == "busqueda_registrada"
    ][:1]
    datos: dict[str, Any] = json.loads(json.dumps(evento.datos))
    return datos


def test_sin_busquedas(estudio: Estudio, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ejecutar_importar_historial(estudio.raiz)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "no hay búsquedas registradas" in salida
    assert "íntegras" in salida


def test_totales_por_fuente_y_total_general(estudio: Estudio) -> None:
    _registrar_dos(estudio)

    historial = construir_historial_importaciones(estudio.raiz)

    assert historial.integro
    assert historial.totales_por_fuente == {"scopus": 4}
    assert historial.total == 4
    texto = "\n".join(historial.lineas())
    assert "imp-0001" in texto and "imp-0002" in texto
    assert "total de registros identificados en bases de datos: 4" in texto
    assert "scopus" in texto


def test_historial_en_json(estudio: Estudio, capsys: pytest.CaptureFixture[str]) -> None:
    _registrar_dos(estudio)

    codigo = ejecutar_importar_historial(estudio.raiz, como_json=True)

    datos = json.loads(capsys.readouterr().out)
    assert codigo == 0
    assert datos["comando"] == "importar historial"
    assert datos["exito"] is True
    resultado = datos["resultado"]
    assert resultado["totales_por_fuente"] == {"scopus": 4}
    assert resultado["total_registros"] == 4
    assert [b["id_importacion"] for b in resultado["busquedas"]] == ["imp-0001", "imp-0002"]
    assert resultado["busquedas"][0]["archivos"][0]["nombre_original"] == "a.ris"


def test_un_original_ausente_o_distinto_es_una_nota_y_no_un_error(
    estudio: Estudio, capsys: pytest.CaptureFixture[str]
) -> None:
    _registrar_dos(estudio)
    originales = estudio.raiz / "exportaciones_originales"
    (originales / "imp-0001" / "a.ris").unlink()
    (originales / "imp-0001" / "b.ris").write_text("otro contenido", encoding="utf-8")

    historial = construir_historial_importaciones(estudio.raiz)
    codigo = ejecutar_importar_historial(estudio.raiz)

    assert historial.integro
    assert codigo == 0
    assert any("falta en este equipo" in nota and "a.ris" in nota for nota in historial.notas)
    assert any("no coincide con el hash" in nota and "b.ris" in nota for nota in historial.notas)
    assert "nota:" in capsys.readouterr().out


# --- P-E10 ampliada -----------------------------------------------------------------


def test_p_e10_importacion_json_alterado(
    estudio: Estudio, capsys: pytest.CaptureFixture[str]
) -> None:
    _registrar_dos(estudio)
    ruta = estudio.raiz / "importaciones" / "imp-0001" / "importacion.json"
    ruta.write_text(ruta.read_text(encoding="utf-8") + " ", encoding="utf-8", newline="\n")

    codigo = ejecutar_importar_historial(estudio.raiz)

    assert codigo == 1
    assert "importaciones/imp-0001/importacion.json no coincide con el hash" in (
        capsys.readouterr().out
    )
    reglas = {h.id_regla for h in validar_archivo(estudio.protocolo).errores}
    assert "P-E10" in reglas


def test_p_e10_registros_csv_eliminado(estudio: Estudio) -> None:
    _registrar_dos(estudio)
    (estudio.raiz / "importaciones" / "imp-0002" / "registros.csv").unlink()

    estado = leer_estado_registro(RutasProtocolo.desde(estudio.protocolo))

    assert not estado.integro
    assert any("falta importaciones/imp-0002/registros.csv" in p for p in estado.problemas)


def test_p_e10_registros_jsonl_alterado(estudio: Estudio) -> None:
    _registrar_dos(estudio)
    ruta = estudio.raiz / "importaciones" / "imp-0001" / "registros.jsonl"
    ruta.write_bytes(ruta.read_bytes().replace(b"Abejas", b"Avispas"))

    estado = leer_estado_registro(RutasProtocolo.desde(estudio.protocolo))

    assert any("registros.jsonl no coincide" in p for p in estado.problemas)


def test_p_e10_numeros_de_importacion_no_consecutivos(estudio: Estudio) -> None:
    _registrar_dos(estudio)
    datos = _datos_del_primer_evento(estudio)
    datos["id_importacion"] = "imp-0004"
    datos["carpeta"] = "importaciones/imp-0004"
    for archivo in datos["archivos"]:
        archivo["copia"] = archivo["copia"].replace("imp-0001", "imp-0004")
    rutas = RutasProtocolo.desde(estudio.protocolo)
    RegistroEncadenado(rutas.eventos).agregar("busqueda_registrada", datos)
    escribir_anclaje(rutas)

    estado = leer_estado_registro(rutas)

    assert any("consecutivas" in p and "imp-0003" in p for p in estado.problemas)


def test_p_e10_evento_con_esquema_invalido(estudio: Estudio) -> None:
    _registrar_dos(estudio)
    datos = _datos_del_primer_evento(estudio)
    del datos["ecuacion_ejecutada"]
    rutas = RutasProtocolo.desde(estudio.protocolo)
    RegistroEncadenado(rutas.eventos).agregar("busqueda_registrada", datos)
    escribir_anclaje(rutas)

    estado = leer_estado_registro(rutas)

    assert any("no cumple su esquema" in p and "ecuacion_ejecutada" in p for p in estado.problemas)


@pytest.mark.parametrize(
    ("campo", "valor", "fragmento"),
    [
        ("carpeta", "importaciones/otra", "carpeta"),
        ("registros_leidos", 99, "registros_leidos"),
        ("fecha_hora_busqueda", "ayer", "fecha_hora_busqueda"),
        ("relacion_ecuacion", "desviacion", "justificación"),
    ],
)
def test_el_esquema_rechaza_datos_incoherentes(
    estudio: Estudio, campo: str, valor: object, fragmento: str
) -> None:
    _registrar_dos(estudio)
    datos = _datos_del_primer_evento(estudio)
    datos[campo] = valor
    rutas = RutasProtocolo.desde(estudio.protocolo)
    RegistroEncadenado(rutas.eventos).agregar("busqueda_registrada", datos)
    escribir_anclaje(rutas)

    estado = leer_estado_registro(rutas)

    assert any(fragmento in problema for problema in estado.problemas)
