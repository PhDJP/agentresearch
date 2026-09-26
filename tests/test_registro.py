"""Pruebas del registro encadenado de eventos."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentresearch.trazabilidad.registro import RegistroEncadenado, formatear_fecha_hora_utc

INICIO = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


def _reloj_fijo(momento: datetime) -> Callable[[], datetime]:
    def _reloj() -> datetime:
        return momento

    return _reloj


def _reloj_incremental(inicio: datetime) -> Callable[[], datetime]:
    contador = {"n": 0}

    def _reloj() -> datetime:
        momento = inicio + timedelta(seconds=contador["n"])
        contador["n"] += 1
        return momento

    return _reloj


def test_agregar_primer_evento_usa_hash_genesis(tmp_path: Path) -> None:
    registro = RegistroEncadenado(tmp_path / "eventos.jsonl", reloj=_reloj_fijo(INICIO))

    evento = registro.agregar("prueba", {"clave": "valor"})

    assert evento.id == "evt-000001"
    assert evento.hash_anterior == "sha256:genesis"


def test_agregar_encadena_por_el_hash_del_evento_anterior(tmp_path: Path) -> None:
    registro = RegistroEncadenado(tmp_path / "eventos.jsonl", reloj=_reloj_incremental(INICIO))

    primero = registro.agregar("uno", {})
    segundo = registro.agregar("dos", {})

    assert segundo.hash_anterior == primero.hash
    assert segundo.id == "evt-000002"


def test_verificar_acepta_una_cadena_valida(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {"a": 1})
    registro.agregar("dos", {"b": 2})
    registro.agregar("tres", {"c": 3})

    assert registro.verificar().valido


def test_verificar_acepta_un_archivo_inexistente(tmp_path: Path) -> None:
    registro = RegistroEncadenado(tmp_path / "no_existe.jsonl")

    assert registro.verificar().valido


def test_verificar_detecta_caracter_alterado(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {"a": 1})
    registro.agregar("dos", {"b": 2})

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    lineas[1] = lineas[1].replace('"dos"', '"dOs"')
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()
    assert not resultado.valido
    assert resultado.numero_linea_error == 2


def test_verificar_detecta_linea_eliminada(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    registro.agregar("dos", {})
    registro.agregar("tres", {})

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    del lineas[1]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()
    assert not resultado.valido
    assert resultado.numero_linea_error == 2


def test_verificar_detecta_lineas_reordenadas(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    registro.agregar("dos", {})
    registro.agregar("tres", {})

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    lineas[1], lineas[2] = lineas[2], lineas[1]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()
    assert not resultado.valido
    assert resultado.numero_linea_error == 2


def test_verificar_detecta_linea_insertada(tmp_path: Path) -> None:
    registro_intruso = RegistroEncadenado(tmp_path / "otro.jsonl", reloj=_reloj_fijo(INICIO))
    registro_intruso.agregar("intruso", {})
    linea_intrusa = (tmp_path / "otro.jsonl").read_text(encoding="utf-8").rstrip("\n")

    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    registro.agregar("dos", {})

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    lineas.insert(1, linea_intrusa)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()
    assert not resultado.valido
    assert resultado.numero_linea_error == 2


def test_verificar_detecta_json_invalido_o_linea_truncada(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})

    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write('{"id": "evt-000002", "tipo": "trunc')

    resultado = registro.verificar()
    assert not resultado.valido
    assert resultado.numero_linea_error == 2


def test_serializacion_es_identica_en_ejecuciones_repetidas(tmp_path: Path) -> None:
    registro_a = RegistroEncadenado(tmp_path / "a.jsonl", reloj=_reloj_fijo(INICIO))
    registro_b = RegistroEncadenado(tmp_path / "b.jsonl", reloj=_reloj_fijo(INICIO))

    registro_a.agregar("evento", {"clave": "valor", "lista": [1, 2, 3]})
    registro_b.agregar("evento", {"clave": "valor", "lista": [1, 2, 3]})

    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_archivo_no_contiene_retorno_de_carro(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    registro.agregar("dos", {})

    assert b"\r" not in ruta.read_bytes()


def test_fecha_hora_utc_tiene_zona_horaria_y_precision_fija_en_milisegundos(
    tmp_path: Path,
) -> None:
    registro = RegistroEncadenado(tmp_path / "eventos.jsonl", reloj=_reloj_fijo(INICIO))

    evento = registro.agregar("uno", {})

    assert evento.fecha_hora_utc == "2026-09-26T12:00:00.000Z"


def test_leer_devuelve_los_datos_originales_del_evento(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_fijo(INICIO))
    registro.agregar("uno", {"clave": "valor con acentos: ción"})

    eventos = registro.leer()

    assert len(eventos) == 1
    assert eventos[0].datos == {"clave": "valor con acentos: ción"}
    assert "\\u" not in ruta.read_text(encoding="utf-8")


def test_formatear_fecha_hora_utc_rechaza_datetime_sin_zona_horaria() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        formatear_fecha_hora_utc(datetime(2026, 9, 26, 12, 0, 0))


def test_agregar_rechaza_reloj_que_devuelve_fecha_sin_zona_horaria(tmp_path: Path) -> None:
    registro = RegistroEncadenado(
        tmp_path / "eventos.jsonl", reloj=lambda: datetime(2026, 9, 26, 12, 0, 0)
    )

    with pytest.raises(ValueError, match="zona horaria"):
        registro.agregar("uno", {})


def test_json_de_cada_linea_es_un_objeto_con_claves_ordenadas(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_fijo(INICIO))
    registro.agregar("uno", {"z": 1, "a": 2})

    linea = ruta.read_text(encoding="utf-8").splitlines()[0]
    claves = list(json.loads(linea).keys())

    assert claves == sorted(claves)
