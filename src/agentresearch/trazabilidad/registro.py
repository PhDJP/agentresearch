"""Registro encadenado de eventos: JSONL de solo adición con hashes verificables."""

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
    """Serializa un objeto a JSON canónico: claves ordenadas, UTF-8, sin espacios sobrantes."""
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


def _quitar_fin_de_linea(linea_cruda: str) -> str:
    """Quita el salto de línea final y, si quedara, un retorno de carro final."""
    linea = linea_cruda[:-1] if linea_cruda.endswith("\n") else linea_cruda
    return linea[:-1] if linea.endswith("\r") else linea


class RegistroEncadenado:
    """Archivo JSONL de solo adición, con cada línea encadenada por hash a la anterior."""

    def __init__(
        self,
        ruta: Path | str,
        reloj: Callable[[], datetime] = _reloj_del_sistema,
    ) -> None:
        self._ruta = Path(ruta)
        self._reloj = reloj

    def agregar(self, tipo: str, datos: dict[str, Any]) -> EventoRegistro:
        """Añade un evento al final del registro y devuelve el evento escrito.

        Antes de escribir, verifica que la cadena existente sea íntegra y que
        el archivo termine en un salto de línea; si no, se niega a agregar
        para no construir sobre un registro ya comprometido.
        """
        momento = self._reloj()
        if momento.tzinfo is None:
            raise ValueError("el reloj debe devolver una fecha con zona horaria")

        eventos_previos: list[EventoRegistro] = []
        if self._ruta.exists():
            contenido = self._ruta.read_bytes()
            if contenido and not contenido.endswith(b"\n"):
                raise ValueError(
                    "el archivo no termina en un salto de línea "
                    f"(escritura anterior incompleta): {self._ruta}"
                )
            resultado = self.verificar()
            if not resultado.valido:
                raise ValueError(
                    "no se puede agregar: la cadena está rota "
                    f"en la línea {resultado.numero_linea_error} ({resultado.mensaje})"
                )
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
                linea = _quitar_fin_de_linea(linea_cruda)
                if linea:
                    eventos.append(EventoRegistro(**json.loads(linea)))
        return eventos

    def verificar(self) -> ResultadoVerificacion:
        """Recalcula cada hash y valida la secuencia de ids y la cadena de hashes.

        Un archivo inexistente se trata como un error, no como una cadena
        vacía válida: quien pide verificar un registro espera que exista.
        """
        if not self._ruta.exists():
            return ResultadoVerificacion(False, None, f"el archivo no existe: {self._ruta}")

        with self._ruta.open("r", encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()

        hash_esperado_anterior = HASH_GENESIS
        indice_evento = 0
        for numero_linea, linea_cruda in enumerate(lineas, start=1):
            linea = _quitar_fin_de_linea(linea_cruda)
            if not linea:
                continue
            indice_evento += 1

            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                return ResultadoVerificacion(
                    False, numero_linea, "JSON inválido o línea truncada"
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
            if json_canonico(evento) != linea:
                return ResultadoVerificacion(
                    False,
                    numero_linea,
                    "la línea no coincide con su serialización canónica",
                )

            hash_declarado = evento.get("hash")
            evento_sin_hash = {clave: valor for clave, valor in evento.items() if clave != "hash"}
            hash_calculado = hash_texto(json_canonico(evento_sin_hash))
            if hash_declarado != hash_calculado:
                return ResultadoVerificacion(
                    False, numero_linea, "el hash no coincide con el contenido de la línea"
                )

            hash_esperado_anterior = hash_declarado

        return ResultadoVerificacion(valido=True)
