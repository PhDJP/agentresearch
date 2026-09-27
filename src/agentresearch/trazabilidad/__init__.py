"""Registro encadenado de eventos, con hashes verificables."""

from agentresearch.trazabilidad.escritura import escribir_atomico
from agentresearch.trazabilidad.hashes import hash_archivo, hash_bytes, hash_texto
from agentresearch.trazabilidad.registro import (
    HASH_GENESIS,
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    ResultadoVerificacion,
    json_canonico,
)

__all__ = [
    "HASH_GENESIS",
    "Anclaje",
    "EventoRegistro",
    "RegistroEncadenado",
    "ResultadoVerificacion",
    "escribir_atomico",
    "hash_archivo",
    "hash_bytes",
    "hash_texto",
    "json_canonico",
]
