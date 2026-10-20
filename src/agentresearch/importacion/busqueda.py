"""Lectura de uno o varios archivos de una misma búsqueda (especificación 2b, «`importar leer`»).

Lee cada archivo con `leer`, busca los identificadores repetidos **entre**
archivos (L-E03 y L-A05) y suma los registros. Lo que no se pudo abrir se
informa aparte y no detiene la lectura de los demás. No escribe nada.

`ResultadoBusqueda` conserva los registros completos; lo que sale por la
terminal y por `--json` es `resumen()`, sin registros ni valores de campo
(ADR-0010, punto 26).
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentresearch.importacion.entrada import ErrorDeArchivo
from agentresearch.importacion.hallazgos import Hallazgo
from agentresearch.importacion.identidad import Repeticion, repeticiones_entre_archivos
from agentresearch.importacion.mapeo import Mapeo
from agentresearch.importacion.resultado import (
    CAMPOS_COBERTURA,
    ResultadoLectura,
)
from agentresearch.importacion.servicio import leer
from agentresearch.registros import FormatoRegistro


class ArchivoNoLeido(BaseModel):
    """Un archivo que no se pudo abrir (no existe, es una carpeta o no hay permiso)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    archivo: str = Field(min_length=1)
    motivo: str = Field(min_length=1)


class ResultadoBusqueda(BaseModel):
    """Lo que devuelve `leer_busqueda` para los archivos de una búsqueda."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    formato: FormatoRegistro
    fuente: str = Field(min_length=1)
    archivos: tuple[ResultadoLectura, ...] = ()
    no_leidos: tuple[ArchivoNoLeido, ...] = ()
    repeticiones: tuple[Repeticion, ...] = ()
    hallazgos_entre_archivos: tuple[Hallazgo, ...] = ()

    @property
    def numero_registros(self) -> int:
        return sum(a.numero_registros for a in self.archivos)

    @property
    def cobertura(self) -> dict[str, int]:
        total = dict.fromkeys(CAMPOS_COBERTURA, 0)
        for archivo in self.archivos:
            for campo, cuenta in archivo.cobertura.items():
                total[campo] += cuenta
        return total

    @property
    def hay_errores(self) -> bool:
        """Verdadero si algún archivo tiene un error de lectura o no se pudo abrir."""
        return (
            bool(self.no_leidos)
            or any(a.errores for a in self.archivos)
            or any(h.severidad == "error" for h in self.hallazgos_entre_archivos)
        )

    def resumen(self) -> dict[str, Any]:
        """Vista sin registros ni valores de campo, para la terminal y `--json`."""
        return {
            "archivos": [a.resumen() for a in self.archivos],
            "no_leidos": [n.model_dump() for n in self.no_leidos],
            "total": {
                "registros": self.numero_registros,
                "repetidos_entre_archivos": [r.model_dump() for r in self.repeticiones],
                "hallazgos_entre_archivos": [h.model_dump() for h in self.hallazgos_entre_archivos],
                "cobertura": self.cobertura,
            },
        }


def leer_busqueda(
    rutas: Sequence[Path],
    formato: FormatoRegistro,
    fuente: str,
    mapeo: Mapeo | None = None,
) -> ResultadoBusqueda:
    """Lee los archivos de una búsqueda y busca los repetidos entre ellos.

    Lanza `ValueError` en los mismos casos que `leer` (fuente vacía, formato sin
    lector, `csv` sin mapeo o mapeo con otro formato). Un archivo que no se puede
    abrir va en `no_leidos` y no impide leer los demás.
    """
    lecturas: list[ResultadoLectura] = []
    no_leidos: list[ArchivoNoLeido] = []
    for ruta in rutas:
        try:
            lecturas.append(leer(ruta, formato, fuente, mapeo))
        except ErrorDeArchivo as error:
            no_leidos.append(ArchivoNoLeido(archivo=ruta.name, motivo=error.motivo))
    repeticiones, hallazgos = repeticiones_entre_archivos(
        [(lectura.archivo, lectura.registros) for lectura in lecturas]
    )
    return ResultadoBusqueda(
        formato=formato,
        fuente=fuente,
        archivos=tuple(lecturas),
        no_leidos=tuple(no_leidos),
        repeticiones=repeticiones,
        hallazgos_entre_archivos=hallazgos,
    )


__all__ = ["ArchivoNoLeido", "ResultadoBusqueda", "leer_busqueda"]
