"""Lectura estricta de archivos JSON de entrada y su validación contra un esquema.

Los archivos de entrada (una decisión, las justificaciones de las
advertencias, una enmienda y el anclaje) los puede escribir el LLM. Por eso se
leen de forma estricta: UTF-8, JSON válido, sin claves repetidas, y se validan
con un modelo pydantic con `extra="forbid"` y `strict=True`. Los errores se
reportan todos a la vez y en español.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from agentresearch.protocolo.archivo import describir_error_de_esquema


class ErrorEntrada(Exception):
    """Un archivo de entrada no se puede leer o no cumple su esquema."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("; ".join(errores))


def leer_json(ruta: Path | str) -> Any:
    """Lee un archivo JSON en UTF-8 y rechaza las claves repetidas."""
    ruta = Path(ruta)
    try:
        contenido = ruta.read_bytes()
    except FileNotFoundError:
        raise ErrorEntrada([f"el archivo no existe: {ruta}"]) from None
    except OSError as error:
        raise ErrorEntrada([f"no se pudo leer el archivo {ruta}: {error.strerror}"]) from None
    return cargar_json(contenido, str(ruta))


def cargar_json(contenido: bytes, nombre: str) -> Any:
    """Decodifica y analiza un JSON en UTF-8, rechazando las claves repetidas."""
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        raise ErrorEntrada([f"{nombre} no está codificado en UTF-8"]) from None
    try:
        return json.loads(texto, object_pairs_hook=_sin_claves_repetidas)
    except _ClaveRepetida as error:
        raise ErrorEntrada([f"{nombre} repite la clave {error.clave!r}"]) from None
    except json.JSONDecodeError as error:
        raise ErrorEntrada(
            [f"{nombre} no es JSON válido (línea {error.lineno}, columna {error.colno})"]
        ) from None


def validar_modelo[M: BaseModel](modelo: type[M], datos: Any, nombre: str) -> M:
    """Valida `datos` contra `modelo`; lanza `ErrorEntrada` con todos los errores."""
    try:
        return modelo.model_validate(datos)
    except ValidationError as error:
        raise ErrorEntrada(
            [f"{nombre}: {describir_error_de_esquema(detalle)}" for detalle in error.errors()]
        ) from None


class _ClaveRepetida(ValueError):
    def __init__(self, clave: str) -> None:
        self.clave = clave
        super().__init__(clave)


def _sin_claves_repetidas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for clave, valor in pares:
        if clave in resultado:
            raise _ClaveRepetida(clave)
        resultado[clave] = valor
    return resultado
