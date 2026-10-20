"""Fecha y hora de la búsqueda, con su desfase (ADR-0010, punto 13).

La terminal pide la fecha (`AAAA-MM-DD`) y la hora (`HH:MM`) por separado y
propone el desfase del computador para esa fecha. Sin dependencias: según la
documentación de Python 3.12, `astimezone()` sobre una fecha sin zona la toma
como hora local del sistema, con el desfase que da el sistema operativo.
"""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta, timezone

DesfaseDelSistema = Callable[[datetime], timedelta]
"""Recibe una fecha sin zona (hora local) o con zona, y devuelve el desfase local de esa fecha."""

_PATRON_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_PATRON_HORA = re.compile(r"[0-9]{2}:[0-9]{2}")
_PATRON_DESFASE = re.compile(r"([+-])([0-9]{2}):([0-9]{2})")


class EntradaInvalida(ValueError):
    """Lo que escribió el investigador no es una fecha, una hora o un desfase válidos."""


def desfase_del_sistema(momento: datetime) -> timedelta:
    """Desfase del computador en `momento` (una fecha sin zona se toma como hora local)."""
    desfase = momento.astimezone().utcoffset()
    assert desfase is not None  # astimezone() siempre devuelve una fecha con zona
    return desfase


def interpretar_fecha(texto: str) -> date:
    """Interpreta `AAAA-MM-DD`."""
    texto = texto.strip()
    if _PATRON_FECHA.fullmatch(texto) is None:
        raise EntradaInvalida("la fecha debe tener la forma AAAA-MM-DD")
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise EntradaInvalida("la fecha no existe en el calendario") from None


def interpretar_hora(texto: str) -> time:
    """Interpreta `HH:MM` (de 00:00 a 23:59)."""
    texto = texto.strip()
    if _PATRON_HORA.fullmatch(texto) is None:
        raise EntradaInvalida("la hora debe tener la forma HH:MM")
    try:
        return time.fromisoformat(texto)
    except ValueError:
        raise EntradaInvalida("la hora no existe: use de 00:00 a 23:59") from None


def interpretar_desfase(texto: str) -> timedelta:
    """Interpreta `±HH:MM` (entre -23:59 y +23:59)."""
    coincidencia = _PATRON_DESFASE.fullmatch(texto.strip())
    if coincidencia is None:
        raise EntradaInvalida("el desfase debe tener la forma ±HH:MM, por ejemplo -05:00")
    signo, horas, minutos = coincidencia.groups()
    if int(horas) > 23 or int(minutos) > 59:
        raise EntradaInvalida("el desfase debe estar entre -23:59 y +23:59")
    desfase = timedelta(hours=int(horas), minutes=int(minutos))
    return -desfase if signo == "-" else desfase


def texto_desfase(desfase: timedelta) -> str:
    """Escribe un desfase como `±HH:MM`."""
    minutos_totales = int(desfase.total_seconds() // 60)
    signo = "-" if minutos_totales < 0 else "+"
    horas, minutos = divmod(abs(minutos_totales), 60)
    return f"{signo}{horas:02d}:{minutos:02d}"


def con_desfase(fecha: date, hora: time, desfase: timedelta) -> datetime:
    """La fecha y la hora locales con su desfase (una fecha con zona)."""
    return datetime.combine(fecha, hora).replace(tzinfo=timezone(desfase))


def texto_iso(momento: datetime) -> str:
    """ISO 8601 hasta el minuto, con el desfase (`2026-10-14T09:30-05:00`)."""
    return momento.strftime("%Y-%m-%dT%H:%M") + texto_desfase(momento.utcoffset() or timedelta())


def texto_iso_utc(momento: datetime) -> str:
    """ISO 8601 hasta el minuto, en UTC (`2026-10-14T14:30Z`)."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")
