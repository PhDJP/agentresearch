"""Registro encadenado de eventos: JSONL de solo adición con hashes verificables."""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agentresearch.trazabilidad.hashes import hash_texto

HASH_GENESIS = "sha256:genesis"

_PATRON_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_PATRON_ANCLAJE = re.compile(r"evt-([0-9]{6,})@(\S+)")


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


@dataclass(frozen=True, slots=True)
class Anclaje:
    """Número de eventos esperado de un registro y hash de su último evento.

    Se guarda fuera del registro para detectar la eliminación de eventos
    finales, que la cadena por sí sola no detecta (ADR-0006, punto 10). Se
    escribe como `evt-NNNNNN@sha256:<hex>`; un registro vacío tiene el anclaje
    `evt-000000@sha256:genesis` (ADR-0008, punto 19).
    """

    numero_eventos: int
    hash_ultimo: str

    def __post_init__(self) -> None:
        if self.numero_eventos < 0:
            raise ValueError("el número de eventos del anclaje no puede ser negativo")
        if self.numero_eventos == 0 and self.hash_ultimo != HASH_GENESIS:
            raise ValueError(f"un anclaje de 0 eventos debe usar el hash {HASH_GENESIS}")
        if self.numero_eventos > 0 and not _PATRON_HASH.fullmatch(self.hash_ultimo):
            raise ValueError(f"hash no válido en el anclaje: {self.hash_ultimo!r}")

    def __str__(self) -> str:
        return f"evt-{self.numero_eventos:06d}@{self.hash_ultimo}"

    @classmethod
    def desde_texto(cls, texto: str) -> "Anclaje":
        """Interpreta un anclaje escrito como `evt-NNNNNN@sha256:<hex>`."""
        coincidencia = _PATRON_ANCLAJE.fullmatch(texto.strip())
        if coincidencia is None:
            raise ValueError(f"anclaje no válido (se espera evt-NNNNNN@sha256:<hex>): {texto!r}")
        return cls(int(coincidencia.group(1)), coincidencia.group(2))


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
            # El evento queda en disco antes de que el llamador siga (ADR-0008, punto 14).
            archivo.flush()
            os.fsync(archivo.fileno())

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

    def anclaje(self) -> Anclaje:
        """Devuelve el anclaje actual: número de eventos y hash del último.

        No verifica la cadena; quien lo guarde debería verificarla antes.
        """
        eventos = self.leer()
        return Anclaje(len(eventos), eventos[-1].hash if eventos else HASH_GENESIS)

    def verificar(self, anclaje: Anclaje | None = None) -> ResultadoVerificacion:
        """Recalcula cada hash y valida la secuencia de ids y la cadena de hashes.

        Un archivo inexistente se trata como un error, no como una cadena
        vacía válida: quien pide verificar un registro espera que exista.

        Con un `anclaje`, además exige que el registro lo cumpla como prefijo:
        al menos tantos eventos como declara el anclaje, y el evento de esa
        posición con el hash anclado. Así se detecta la eliminación de eventos
        finales, y un anclaje que quedó atrás sigue siendo válido.
        """
        if not self._ruta.exists():
            return ResultadoVerificacion(False, None, f"el archivo no existe: {self._ruta}")

        with self._ruta.open("r", encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()

        hash_esperado_anterior = HASH_GENESIS
        indice_evento = 0
        lineas_y_hashes: list[tuple[int, str]] = []
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
            if not isinstance(evento, dict):
                return ResultadoVerificacion(
                    False, numero_linea, "la línea no es un objeto JSON"
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
            lineas_y_hashes.append((numero_linea, hash_declarado))

        if anclaje is not None:
            return _verificar_anclaje(lineas_y_hashes, anclaje)
        return ResultadoVerificacion(valido=True)


def _verificar_anclaje(
    lineas_y_hashes: list[tuple[int, str]], anclaje: Anclaje
) -> ResultadoVerificacion:
    """Comprueba que un registro íntegro cumpla un anclaje como prefijo."""
    numero_eventos = len(lineas_y_hashes)
    if numero_eventos < anclaje.numero_eventos:
        return ResultadoVerificacion(
            False,
            None,
            f"el registro tiene {numero_eventos} eventos, pero el anclaje {anclaje} exige "
            f"al menos {anclaje.numero_eventos}: se eliminaron eventos del final",
        )
    if anclaje.numero_eventos > 0:
        numero_linea, hash_real = lineas_y_hashes[anclaje.numero_eventos - 1]
        if hash_real != anclaje.hash_ultimo:
            return ResultadoVerificacion(
                False,
                numero_linea,
                f"el evento evt-{anclaje.numero_eventos:06d} no tiene el hash del anclaje "
                f"{anclaje}",
            )
    return ResultadoVerificacion(valido=True)
