"""Lectura de los bytes de un archivo de exportación (especificación 2b, «Codificación»).

UTF-8 con o sin BOM; cualquier otra codificación se rechaza con la línea del
primer byte inválido (L-E01). El fin de línea puede ser LF, CRLF o CR. La
«línea física» de un registro es el número de línea del archivo donde empieza,
contado con esos tres terminadores.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.trazabilidad import hash_bytes

_TERMINADOR_BYTES = re.compile(rb"\r\n|\n|\r")
_TERMINADOR = re.compile(r"\r\n|\n|\r")
_BOM_UTF16 = (b"\xff\xfe", b"\xfe\xff")


class ErrorDeArchivo(Exception):
    """El archivo no se pudo abrir (no existe, es una carpeta o no hay permiso)."""

    def __init__(self, ruta: Path, motivo: str) -> None:
        super().__init__(f"{ruta.name}: {motivo}")
        self.ruta = ruta
        self.motivo = motivo


@dataclass(frozen=True)
class Carga:
    """Resultado de cargar un archivo: su texto o el hallazgo L-E01."""

    nombre: str
    hash: str
    texto: str | None
    """El contenido decodificado, sin BOM; `None` si el archivo no es UTF-8."""
    lineas: tuple[str, ...]
    """Las líneas físicas sin terminador; `lineas[i]` es la línea `i + 1`."""
    hallazgo: Hallazgo | None


def dividir_lineas(texto: str) -> tuple[str, ...]:
    """Divide en líneas físicas (LF, CRLF o CR), sin la vacía que deja un salto final."""
    partes = _TERMINADOR.split(texto)
    if partes and partes[-1] == "":
        partes.pop()
    return tuple(partes)


def _linea_del_byte(datos: bytes, posicion: int) -> int:
    return len(_TERMINADOR_BYTES.findall(datos[:posicion])) + 1


def cargar(ruta: Path) -> Carga:
    """Lee un archivo y lo decodifica; informa L-E01 con la línea del primer byte inválido."""
    try:
        datos = ruta.read_bytes()
    except OSError as error:
        raise ErrorDeArchivo(ruta, error.strerror or type(error).__name__) from error
    nombre = ruta.name
    hash_ = hash_bytes(datos)

    def _rechazo(linea: int, motivo: str) -> Carga:
        hallazgo = crear_hallazgo("L-E01", nombre, f"el archivo no es UTF-8: {motivo}", linea=linea)
        return Carga(nombre, hash_, None, (), hallazgo)

    if datos.startswith(_BOM_UTF16):
        return _rechazo(1, "empieza con la marca de orden de bytes de UTF-16")
    nulo = datos.find(b"\x00")
    if nulo >= 0:
        return _rechazo(_linea_del_byte(datos, nulo), "contiene bytes nulos (¿UTF-16?)")
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return _rechazo(
            _linea_del_byte(datos, error.start), "byte inválido en esta línea (¿Latin-1?)"
        )
    return Carga(nombre, hash_, texto, dividir_lineas(texto), None)
