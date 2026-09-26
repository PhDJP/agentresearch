"""Protocolo del estudio: modelo, lectura y escritura en YAML, y validación."""

from agentresearch.protocolo.archivo import (
    DocumentoProtocolo,
    ErrorLecturaProtocolo,
    ProblemaLectura,
    actualizar_documento,
    cargar_protocolo,
    escribir_protocolo,
    leer_protocolo,
    texto_plantilla,
    texto_protocolo,
)
from agentresearch.protocolo.modelo import VERSION_ESQUEMA, Protocolo

__all__ = [
    "VERSION_ESQUEMA",
    "DocumentoProtocolo",
    "ErrorLecturaProtocolo",
    "ProblemaLectura",
    "Protocolo",
    "actualizar_documento",
    "cargar_protocolo",
    "escribir_protocolo",
    "leer_protocolo",
    "texto_plantilla",
    "texto_protocolo",
]
