"""Pruebas del registro encadenado de eventos."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentresearch.trazabilidad import registro as registro_encadenado
from agentresearch.trazabilidad.registro import (
    HASH_GENESIS,
    Anclaje,
    RegistroEncadenado,
    formatear_fecha_hora_utc,
)

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


def test_verificar_rechaza_un_archivo_inexistente(tmp_path: Path) -> None:
    registro = RegistroEncadenado(tmp_path / "no_existe.jsonl")

    resultado = registro.verificar()

    assert not resultado.valido
    assert resultado.numero_linea_error is None
    assert "no existe" in (resultado.mensaje or "")


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


def test_verificar_detecta_una_linea_json_que_no_es_un_objeto(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO)).agregar("uno", {})
    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("[1, 2]\n")

    resultado = RegistroEncadenado(ruta).verificar()

    assert not resultado.valido
    assert resultado.numero_linea_error == 2
    assert "objeto JSON" in (resultado.mensaje or "")


def test_verificar_ignora_las_lineas_vacias(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("\n")

    assert registro.verificar().valido


def test_verificar_detecta_un_hash_anterior_que_no_encadena(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    registro.agregar("dos", {})
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    segundo = json.loads(lineas[1])
    segundo["hash_anterior"] = "sha256:" + "0" * 64
    lineas[1] = json.dumps(segundo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()

    assert not resultado.valido
    assert resultado.numero_linea_error == 2
    assert "hash_anterior" in (resultado.mensaje or "")


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


def test_verificar_detecta_una_linea_reformateada_con_los_mismos_valores(
    tmp_path: Path,
) -> None:
    """Reordenar las claves no cambia el hash recalculado, pero si la forma canonica."""
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_fijo(INICIO))
    registro.agregar("uno", {"a": 1})

    evento = json.loads(ruta.read_text(encoding="utf-8").splitlines()[0])
    evento_con_otro_orden = dict(reversed(list(evento.items())))
    assert list(evento_con_otro_orden.keys()) != sorted(evento_con_otro_orden.keys())
    linea_reformateada = json.dumps(
        evento_con_otro_orden, ensure_ascii=False, separators=(",", ":")
    )
    ruta.write_text(linea_reformateada + "\n", encoding="utf-8", newline="\n")

    resultado = registro.verificar()

    assert not resultado.valido
    assert resultado.numero_linea_error == 1
    assert "canónic" in (resultado.mensaje or "")


def test_agregar_rechaza_si_la_cadena_existente_esta_rota(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})
    contenido = ruta.read_text(encoding="utf-8").replace('"uno"', '"otro"')
    ruta.write_text(contenido, encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="rota"):
        registro.agregar("dos", {})


def test_agregar_rechaza_si_el_archivo_no_termina_en_salto_de_linea(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    registro.agregar("uno", {})

    contenido_sin_salto_final = ruta.read_bytes().rstrip(b"\n")
    ruta.write_bytes(contenido_sin_salto_final)

    with pytest.raises(ValueError, match="salto de línea"):
        registro.agregar("dos", {})


# --- Anclaje (ADR-0006, punto 10; ADR-0008, puntos 19 a 21) --------------------


def _registro_con_eventos(ruta: Path, cantidad: int) -> RegistroEncadenado:
    registro = RegistroEncadenado(ruta, reloj=_reloj_incremental(INICIO))
    for numero in range(cantidad):
        registro.agregar(f"evento-{numero}", {"n": numero})
    return registro


def test_anclaje_de_un_registro_vacio_usa_el_hash_genesis(tmp_path: Path) -> None:
    anclaje = RegistroEncadenado(tmp_path / "no_existe.jsonl").anclaje()

    assert anclaje == Anclaje(0, HASH_GENESIS)
    assert str(anclaje) == "evt-000000@sha256:genesis"


def test_anclaje_tiene_el_numero_de_eventos_y_el_hash_del_ultimo(tmp_path: Path) -> None:
    registro = _registro_con_eventos(tmp_path / "eventos.jsonl", 3)

    anclaje = registro.anclaje()

    assert anclaje.numero_eventos == 3
    assert anclaje.hash_ultimo == registro.leer()[-1].hash
    assert str(anclaje).startswith("evt-000003@sha256:")


def test_anclaje_se_interpreta_desde_su_texto(tmp_path: Path) -> None:
    anclaje = _registro_con_eventos(tmp_path / "eventos.jsonl", 2).anclaje()

    assert Anclaje.desde_texto(str(anclaje)) == anclaje
    assert Anclaje.desde_texto(f"  {anclaje}\n") == anclaje


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "evt-3@sha256:" + "a" * 64,
        "evt-000003:sha256:" + "a" * 64,
        "evt-000003@sha256:" + "A" * 64,
        "evt-000003@sha256:abc",
        "evt-000003@sha256:genesis",
        "evt-000000@sha256:" + "a" * 64,
    ],
)
def test_anclaje_rechaza_textos_no_validos(texto: str) -> None:
    with pytest.raises(ValueError):
        Anclaje.desde_texto(texto)


def test_anclaje_rechaza_un_numero_negativo() -> None:
    with pytest.raises(ValueError, match="negativo"):
        Anclaje(-1, HASH_GENESIS)


def test_verificar_acepta_el_anclaje_actual(tmp_path: Path) -> None:
    registro = _registro_con_eventos(tmp_path / "eventos.jsonl", 3)

    assert registro.verificar(registro.anclaje()).valido


def test_verificar_acepta_un_anclaje_anterior_como_prefijo(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = _registro_con_eventos(ruta, 2)
    anclaje_anterior = registro.anclaje()
    registro.agregar("posterior", {})

    assert registro.verificar(anclaje_anterior).valido


def test_verificar_con_anclaje_detecta_la_eliminacion_de_eventos_finales(
    tmp_path: Path,
) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = _registro_con_eventos(ruta, 3)
    anclaje = registro.anclaje()
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join(lineas[:-1]) + "\n", encoding="utf-8", newline="\n")

    assert registro.verificar().valido  # sin anclaje, el truncamiento pasa inadvertido
    resultado = registro.verificar(anclaje)

    assert not resultado.valido
    assert resultado.numero_linea_error is None
    assert "2 eventos" in (resultado.mensaje or "")
    assert "se eliminaron eventos del final" in (resultado.mensaje or "")


def test_verificar_con_anclaje_detecta_un_registro_reconstruido(tmp_path: Path) -> None:
    """Un registro recalculado desde cero es íntegro, pero no cumple el anclaje original."""
    ruta = tmp_path / "eventos.jsonl"
    anclaje = _registro_con_eventos(ruta, 2).anclaje()
    ruta.unlink()
    registro = RegistroEncadenado(ruta, reloj=_reloj_fijo(INICIO))
    registro.agregar("otro", {})
    registro.agregar("otro", {})

    resultado = registro.verificar(anclaje)

    assert not resultado.valido
    assert resultado.numero_linea_error == 2
    assert "evt-000002" in (resultado.mensaje or "")


def test_verificar_con_anclaje_vacio_acepta_cualquier_registro_integro(tmp_path: Path) -> None:
    registro = _registro_con_eventos(tmp_path / "eventos.jsonl", 1)

    assert registro.verificar(Anclaje(0, HASH_GENESIS)).valido


def test_verificar_con_anclaje_informa_primero_la_cadena_rota(tmp_path: Path) -> None:
    ruta = tmp_path / "eventos.jsonl"
    registro = _registro_con_eventos(ruta, 2)
    anclaje = registro.anclaje()
    contenido = ruta.read_text(encoding="utf-8").replace('"evento-0"', '"otro"')
    ruta.write_text(contenido, encoding="utf-8", newline="\n")

    resultado = registro.verificar(anclaje)

    assert not resultado.valido
    assert resultado.numero_linea_error == 1


def test_agregar_sincroniza_el_evento_a_disco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sincronizados: list[int] = []
    fsync_original = os.fsync

    def _fsync(descriptor: int) -> None:
        sincronizados.append(descriptor)
        fsync_original(descriptor)

    monkeypatch.setattr(os, "fsync", _fsync)
    # La sincronización del directorio (solo en POSIX) se prueba en test_escritura.py.
    monkeypatch.setattr(registro_encadenado, "sincronizar_directorio", lambda _d: None)

    RegistroEncadenado(tmp_path / "eventos.jsonl").agregar("uno", {})

    assert len(sincronizados) == 1
