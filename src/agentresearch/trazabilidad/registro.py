"""Registro encadenado de eventos: JSONL de solo adicion con hashes verificables."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agentresearch.trazabilidad.hashes import hash_texto

HASH_GENESIS = "sha256:genesis"


def json_canonico(objeto: dict[str, Any]) -> str:
    """Serializa un objeto a JSON canonico: claves ordenadas, UTF-8, sin espacios sobrantes."""
    return json.dumps(
        objeto,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def formatear_fecha_hora_utc(momento: datetime) -> str:
    """Formatea una fecha con zona horaria como ISO 8601 en UTC, con milisegundos y 'Z'."""
    if momento.tzinfo is None:
        raise ValueError("la fecha y hora deben tener zona horaria")
    momento_utc = momento.astimezone(UTC)
    milisegundos = momento_utc.microsecond // 1000
    return momento_utc.strftime("%Y-%m-%dT%H:%M:%S") + f".{milisegundos:03d}Z"


@dataclass(frozen=True, slots=True)
class EventoRegistro:
    """Un evento del registro encadenado, ya validado y con su hash."""

    id: str
    tipo: str
    fecha_hora_utc: str
    version_agente: str
    datos: dict[str, Any]
    hash_anterior: str
    hash: str


@dataclass(frozen=True, slots=True)
class ResultadoVerificacion:
    """Resultado de verificar la integridad de un registro encadenado."""

    valido: bool
    numero_linea_error: int | None = None
    mensaje: str | None = None


def _reloj_del_sistema() -> datetime:
    return datetime.now(UTC)


class RegistroEncadenado:
    """Archivo JSONL de solo adicion, con cada linea encadenada por hash a la anterior."""

    def __init__(
        self,
        ruta: Path | str,
        reloj: Callable[[], datetime] = _reloj_del_sistema,
    ) -> None:
        self._ruta = Path(ruta)
        self._reloj = reloj

    def agregar(self, tipo: str, datos: dict[str, Any]) -> EventoRegistro:
        """Añade un evento al final del registro y devuelve el evento escrito."""
        momento = self._reloj()
        if momento.tzinfo is None:
            raise ValueError("el reloj debe devolver una fecha con zona horaria")

        eventos_previos = self.leer()
        siguiente_id = f"evt-{len(eventos_previos) + 1:06d}"
        hash_anterior = eventos_previos[-1].hash if eventos_previos else HASH_GENESIS

        evento_sin_hash: dict[str, Any] = {
            "id": siguiente_id,
            "tipo": tipo,
            "fecha_hora_utc": formatear_fecha_hora_utc(momento),
            "version_agente": version("agentresearch"),
            "datos": datos,
            "hash_anterior": hash_anterior,
        }
        hash_evento = hash_texto(json_canonico(evento_sin_hash))
        evento_completo = {**evento_sin_hash, "hash": hash_evento}

        with self._ruta.open("a", encoding="utf-8", newline="\n") as archivo:
            archivo.write(json_canonico(evento_completo) + "\n")

        return EventoRegistro(**evento_completo)

    def leer(self) -> list[EventoRegistro]:
        """Devuelve los eventos del registro, en orden, ya tipados."""
        if not self._ruta.exists():
            return []

        eventos = []
        with self._ruta.open("r", encoding="utf-8", newline="") as archivo:
            for linea_cruda in archivo:
                linea = linea_cruda.rstrip("\n")
                if linea:
                    eventos.append(EventoRegistro(**json.loads(linea)))
        return eventos

    def verificar(self) -> ResultadoVerificacion:
        """Recalcula cada hash y valida la secuencia de ids y la cadena de hashes."""
        if not self._ruta.exists():
            return ResultadoVerificacion(valido=True)

        with self._ruta.open("r", encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()

        hash_esperado_anterior = HASH_GENESIS
        indice_evento = 0
        for numero_linea, linea_cruda in enumerate(lineas, start=1):
            linea = linea_cruda.rstrip("\n")
            if not linea:
                continue
            indice_evento += 1

            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                return ResultadoVerificacion(
                    False, numero_linea, "JSON invalido o linea truncada"
                )

            id_esperado = f"evt-{indice_evento:06d}"
            if evento.get("id") != id_esperado:
                return ResultadoVerificacion(
                    False, numero_linea, f"se esperaba el id {id_esperado}"
                )
            if evento.get("hash_anterior") != hash_esperado_anterior:
                return ResultadoVerificacion(
                    False,
                    numero_linea,
                    "hash_anterior no coincide con el hash del evento anterior",
                )

            hash_declarado = evento.get("hash")
            evento_sin_hash = {clave: valor for clave, valor in evento.items() if clave != "hash"}
            hash_calculado = hash_texto(json_canonico(evento_sin_hash))
            if hash_declarado != hash_calculado:
                return ResultadoVerificacion(
                    False, numero_linea, "el hash no coincide con el contenido de la linea"
                )

            hash_esperado_anterior = hash_declarado

        return ResultadoVerificacion(valido=True)
