"""Registro encadenado de eventos, con hashes verificables."""

from agentresearch.trazabilidad.hashes import hash_archivo, hash_texto
from agentresearch.trazabilidad.registro import (
    EventoRegistro,
    RegistroEncadenado,
    ResultadoVerificacion,
)

__all__ = [
    "EventoRegistro",
    "RegistroEncadenado",
    "ResultadoVerificacion",
    "hash_archivo",
    "hash_texto",
]
