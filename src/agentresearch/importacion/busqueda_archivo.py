"""Archivo de la búsqueda que Claude Code prepara en `.borradores/` (especificación 2c).

Lo escribe el LLM con lo que dice el investigador; por eso se lee de forma
estricta (UTF-8, JSON sin claves repetidas, esquema con `extra="forbid"`). Las
rutas de `archivos` son solo para leerlos: nunca se guardan. La fecha y la hora
no van aquí: las pide la terminal.
"""

from pathlib import Path

from pydantic import Field

from agentresearch.protocolo.entradas import leer_json, validar_modelo
from agentresearch.protocolo.eventos import ModeloEvento, TextoNoVacio
from agentresearch.protocolo.eventos_busqueda import FormatoImportacion


class ArchivoDeBusqueda(ModeloEvento):
    """Lo que el investigador declara de una búsqueda manual."""

    fuente: TextoNoVacio
    plataforma: TextoNoVacio
    institucion_acceso: TextoNoVacio
    cobertura: TextoNoVacio
    lematizacion: str | None = None
    filtros: list[TextoNoVacio] = Field(default_factory=list)
    ecuacion_ejecutada: TextoNoVacio
    justificacion_ecuacion: str = ""
    resultados_interfaz: int = Field(ge=0)
    justificacion_diferencia: str = ""
    formato: FormatoImportacion
    mapeo: str | None = None
    archivos: list[TextoNoVacio] = Field(min_length=1)


def leer_archivo_de_busqueda(ruta: Path | str) -> ArchivoDeBusqueda:
    """Lee y valida el archivo de la búsqueda; lanza `ErrorEntrada` con todos los errores."""
    return validar_modelo(ArchivoDeBusqueda, leer_json(ruta), str(ruta))


def problemas_de_mapeo(busqueda: ArchivoDeBusqueda) -> list[str]:
    """El mapeo es obligatorio con el formato `csv` y no se admite con otro."""
    if busqueda.formato == "csv" and busqueda.mapeo is None:
        return ["el formato csv exige un archivo de mapeo (`mapeo`)"]
    if busqueda.formato != "csv" and busqueda.mapeo is not None:
        return ["solo el formato csv admite un archivo de mapeo (`mapeo`)"]
    return []


__all__ = ["ArchivoDeBusqueda", "leer_archivo_de_busqueda", "problemas_de_mapeo"]
