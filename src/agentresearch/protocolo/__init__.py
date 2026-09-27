"""Protocolo del estudio: modelo, lectura y escritura en YAML, validación y ciclo de vida."""

from agentresearch.protocolo.archivo import (
    DocumentoProtocolo,
    ErrorLecturaProtocolo,
    ProblemaLectura,
    actualizar_documento,
    cargar_protocolo,
    decodificar_protocolo,
    escribir_protocolo,
    leer_bytes_protocolo,
    leer_protocolo,
    texto_plantilla,
    texto_protocolo,
)
from agentresearch.protocolo.ciclo_de_vida import (
    EstadoRegistro,
    leer_estado_registro,
    siguiente_version,
)
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.modelo import VERSION_ESQUEMA, Protocolo
from agentresearch.protocolo.reglas import REGLAS, Regla
from agentresearch.protocolo.validacion import (
    Hallazgo,
    LecturaProtocolo,
    ResultadoValidacion,
    leer_para_validar,
    validar_archivo,
    validar_documento,
    validar_lectura,
    validar_protocolo,
)

__all__ = [
    "REGLAS",
    "VERSION_ESQUEMA",
    "DocumentoProtocolo",
    "ErrorLecturaProtocolo",
    "EstadoRegistro",
    "Hallazgo",
    "LecturaProtocolo",
    "ProblemaLectura",
    "Protocolo",
    "Regla",
    "ResultadoValidacion",
    "RutasProtocolo",
    "actualizar_documento",
    "cargar_protocolo",
    "decodificar_protocolo",
    "escribir_protocolo",
    "leer_bytes_protocolo",
    "leer_estado_registro",
    "leer_para_validar",
    "leer_protocolo",
    "siguiente_version",
    "texto_plantilla",
    "texto_protocolo",
    "validar_archivo",
    "validar_documento",
    "validar_lectura",
    "validar_protocolo",
]
