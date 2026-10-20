"""Pruebas de la fecha, la hora y el desfase de una búsqueda (ADR-0010, punto 13)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from agentresearch.importacion.fecha_hora import (
    EntradaInvalida,
    con_desfase,
    desfase_del_sistema,
    interpretar_desfase,
    interpretar_fecha,
    interpretar_hora,
    texto_desfase,
    texto_iso,
    texto_iso_utc,
)


def test_interpreta_una_fecha_valida() -> None:
    assert interpretar_fecha(" 2026-10-14 ") == date(2026, 10, 14)


@pytest.mark.parametrize("texto", ["14/10/2026", "2026-1-4", "2026-02-30", "", "ayer"])
def test_rechaza_una_fecha_invalida(texto: str) -> None:
    with pytest.raises(EntradaInvalida):
        interpretar_fecha(texto)


def test_interpreta_una_hora_valida() -> None:
    assert interpretar_hora("09:30") == time(9, 30)


@pytest.mark.parametrize("texto", ["9:30", "24:00", "09:60", "09:30:15", ""])
def test_rechaza_una_hora_invalida(texto: str) -> None:
    with pytest.raises(EntradaInvalida):
        interpretar_hora(texto)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("-05:00", timedelta(hours=-5)),
        ("+02:00", timedelta(hours=2)),
        ("+05:30", timedelta(hours=5, minutes=30)),
        ("-00:30", timedelta(minutes=-30)),
    ],
)
def test_interpreta_un_desfase(texto: str, esperado: timedelta) -> None:
    assert interpretar_desfase(texto) == esperado
    assert texto_desfase(esperado) == texto


@pytest.mark.parametrize("texto", ["05:00", "-5:00", "+24:00", "+05:60", "UTC", ""])
def test_rechaza_un_desfase_invalido(texto: str) -> None:
    with pytest.raises(EntradaInvalida):
        interpretar_desfase(texto)


def test_el_iso_local_y_el_utc() -> None:
    momento = con_desfase(date(2026, 10, 14), time(9, 30), timedelta(hours=-5))

    assert texto_iso(momento) == "2026-10-14T09:30-05:00"
    assert texto_iso_utc(momento) == "2026-10-14T14:30Z"
    assert momento.astimezone(UTC) == datetime(2026, 10, 14, 14, 30, tzinfo=UTC)


def test_el_desfase_del_sistema_es_un_intervalo() -> None:
    desfase = desfase_del_sistema(datetime(2026, 10, 14, 9, 30))

    assert isinstance(desfase, timedelta)
    assert abs(desfase) < timedelta(days=1)
