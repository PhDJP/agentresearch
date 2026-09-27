"""Metadatos del estudio en `estudio.yaml` (ADR-0007).

Guarda lo que identifica al estudio y lo que hace falta para reproducirlo: el
nombre, el título, la fecha de creación, la versión exacta del agente y de
dónde se instala, el modelo fijado y la licencia de los datos.
"""

import io
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from agentresearch.protocolo.archivo import a_python, crear_yaml

NOMBRE_ARCHIVO = "estudio.yaml"
VERSION_ESQUEMA_ESTUDIO: Literal[1] = 1
LICENCIA_DATOS: Literal["CC-BY-4.0"] = "CC-BY-4.0"
"""Licencia de los datos del estudio (ADR-0005), como identificador SPDX."""

CABECERA = (
    "# Metadatos del estudio (agentresearch, ADR-0007). Lo escribe `agentresearch nuevo-estudio`;\n"
    "# su hash queda en el primer evento de protocolo/eventos.jsonl.\n"
)


class ModeloEstudio(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Agente(ModeloEstudio):
    version: Annotated[str, Field(min_length=1)]
    """Versión exacta de agentresearch con que se creó el estudio."""
    fuente: Annotated[str, Field(min_length=1)]
    """Especificación de instalación fijada a esa versión, la misma de `pyproject.toml`."""


class Estudio(ModeloEstudio):
    version_esquema: Literal[1]
    nombre: Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")]
    titulo: Annotated[str, Field(min_length=1)]
    fecha_creacion: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    agente: Agente
    modelo: Annotated[str, Field(min_length=1)]
    licencia_datos: Literal["CC-BY-4.0"]


def texto_estudio(estudio: Estudio) -> str:
    """Serializa `estudio.yaml`: cabecera comentada, UTF-8 y LF; los textos con comillas dobles."""
    datos = estudio.model_dump(mode="python")
    datos["titulo"] = DoubleQuotedScalarString(datos["titulo"])
    datos["fecha_creacion"] = DoubleQuotedScalarString(datos["fecha_creacion"])
    datos["agente"]["version"] = DoubleQuotedScalarString(datos["agente"]["version"])
    salida = io.StringIO()
    crear_yaml().dump(datos, salida)
    return CABECERA + salida.getvalue()


def leer_estudio(ruta: Path | str) -> Estudio:
    """Lee y valida `estudio.yaml`. Lanza `ValueError` si no cumple el esquema."""
    datos = crear_yaml().load(Path(ruta).read_text(encoding="utf-8"))
    return Estudio.model_validate(a_python(datos))
