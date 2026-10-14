"""Resultados de la lectura de un archivo y de una búsqueda (especificación 2b, «Interfaz común»).

`ResultadoLectura` y `ResultadoBusqueda` contienen los registros completos
normalizados y no son lo que sale por la terminal ni por `--json`: esa salida
es la vista de `resumen()`, sin registros ni valores de campo, porque Claude Code
la ve y los resúmenes tienen licencia (ADR-0010, punto 26).
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentresearch.importacion.hallazgos import Hallazgo
from agentresearch.registros import FormatoRegistro, RegistroNormalizado

CAMPOS_COBERTURA = (
    "id_fuente",
    "titulo",
    "autores",
    "anio",
    "fuente_publicacion",
    "volumen",
    "numero",
    "paginas",
    "doi",
    "pmid",
    "tipo_documento",
    "idioma",
    "resumen",
    "palabras_clave_autor",
    "palabras_clave_indexadas",
)
"""Campos del registro cuya presencia se cuenta, en el orden de la salida."""


def calcular_cobertura(registros: Sequence[RegistroNormalizado]) -> dict[str, int]:
    """Cuenta en cuántos registros está cada campo.

    Se cuenta sobre el registro ya normalizado: un valor vacío (una celda vacía,
    `pages = {}`) es un campo ausente. Todos los campos aparecen, también con 0.
    """
    return {
        campo: sum(1 for registro in registros if getattr(registro, campo))
        for campo in CAMPOS_COBERTURA
    }


class LineaCabecera(BaseModel):
    """Una línea anterior al primer registro (L-A03)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    linea: int = Field(ge=1)
    texto: str


class ResultadoLectura(BaseModel):
    """Lo que devuelve `leer` para un archivo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    archivo: str = Field(min_length=1)
    formato: FormatoRegistro
    fuente: str = Field(min_length=1)
    hash_archivo: str
    hash_mapeo: str | None = None
    registros: tuple[RegistroNormalizado, ...] = ()
    hallazgos: tuple[Hallazgo, ...] = ()
    lineas_cabecera: tuple[LineaCabecera, ...] = ()
    detenido_en_fila: int | None = Field(default=None, ge=1)
    """Fila donde se detuvo la lectura (celda que supera el límite de campo), si ocurrió."""

    @property
    def numero_registros(self) -> int:
        return len(self.registros)

    @property
    def cobertura(self) -> dict[str, int]:
        return calcular_cobertura(self.registros)

    @property
    def errores(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.severidad == "error")

    @property
    def advertencias(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.severidad == "advertencia")

    def resumen(self) -> dict[str, Any]:
        """Vista sin registros ni valores de campo, para la terminal y `--json`."""
        return {
            "archivo": self.archivo,
            "formato": self.formato,
            "fuente": self.fuente,
            "hash": self.hash_archivo,
            "hash_mapeo": self.hash_mapeo,
            "registros": self.numero_registros,
            "detenido_en_fila": self.detenido_en_fila,
            "hallazgos": [h.model_dump() for h in self.hallazgos],
            "lineas_cabecera": [c.model_dump() for c in self.lineas_cabecera],
            "cobertura": self.cobertura,
        }
