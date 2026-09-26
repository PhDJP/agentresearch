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
from agentresearch.protocolo.reglas import REGLAS, Regla
from agentresearch.protocolo.validacion import (
    Hallazgo,
    ResultadoValidacion,
    validar_archivo,
    validar_documento,
    validar_protocolo,
)

__all__ = [
    "REGLAS",
    "VERSION_ESQUEMA",
    "DocumentoProtocolo",
    "ErrorLecturaProtocolo",
    "Hallazgo",
    "ProblemaLectura",
    "Protocolo",
    "Regla",
    "ResultadoValidacion",
    "actualizar_documento",
    "cargar_protocolo",
    "escribir_protocolo",
    "leer_protocolo",
    "texto_plantilla",
    "texto_protocolo",
    "validar_archivo",
    "validar_documento",
    "validar_protocolo",
]
