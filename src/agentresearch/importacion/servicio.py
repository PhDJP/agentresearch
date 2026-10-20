"""Punto de entrada de la lectura: `leer` (especificación 2b, «Interfaz común»).

El formato lo declara el investigador; el lector no lo adivina.
"""

from collections.abc import Callable
from pathlib import Path

from agentresearch.importacion.ensamblado import Lectura
from agentresearch.importacion.entrada import Carga, cargar
from agentresearch.importacion.lector_bibtex import leer_bibtex
from agentresearch.importacion.lector_csv import leer_csv
from agentresearch.importacion.lector_ris import leer_ris
from agentresearch.importacion.lector_scopus_csv import leer_scopus_csv
from agentresearch.importacion.lector_wos import leer_wos
from agentresearch.importacion.mapeo import Mapeo
from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.registros import FormatoRegistro

_LECTORES: dict[str, Callable[[Carga, str, Mapeo | None], Lectura]] = {
    "ris": lambda carga, fuente, _mapeo: leer_ris(carga, fuente),
    "bibtex": lambda carga, fuente, _mapeo: leer_bibtex(carga, fuente),
    "scopus_csv": lambda carga, fuente, _mapeo: leer_scopus_csv(carga, fuente),
    "wos_txt": lambda carga, fuente, _mapeo: leer_wos(carga, fuente),
    "csv": lambda carga, fuente, mapeo: leer_csv(carga, fuente, _exigir(mapeo)),
}


def _exigir(mapeo: Mapeo | None) -> Mapeo:
    if mapeo is None:  # pragma: no cover - `leer` lo valida antes
        raise ValueError("el formato csv exige un archivo de mapeo")
    return mapeo


def formatos_disponibles() -> tuple[str, ...]:
    """Los formatos para los que ya hay lector."""
    return tuple(_LECTORES)


def leer(
    ruta: Path, formato: FormatoRegistro, fuente: str, mapeo: Mapeo | None = None
) -> ResultadoLectura:
    """Lee un archivo de exportación y devuelve sus registros normalizados y hallazgos.

    No escribe nada. Lanza `ErrorDeArchivo` si el archivo no se puede abrir y
    `ValueError` si el formato no tiene lector, la fuente está vacía, el formato
    `csv` no trae mapeo o un formato distinto de `csv` lo trae. Un archivo que no
    es UTF-8 devuelve un resultado sin registros con el hallazgo L-E01. Un mapeo
    con contenido inválido da L-E02 (con el nombre del archivo de mapeo) y
    ningún registro.
    """
    if not fuente.strip():
        raise ValueError("la fuente no puede estar vacía")
    lector = _LECTORES.get(formato)
    if lector is None:
        raise ValueError(f"formato sin lector: {formato}")
    if formato == "csv" and mapeo is None:
        raise ValueError("el formato csv exige un archivo de mapeo")
    if formato != "csv" and mapeo is not None:
        raise ValueError("solo el formato csv admite un archivo de mapeo")
    carga = cargar(ruta)
    hash_mapeo = mapeo.hash if mapeo is not None else None
    if carga.hallazgo is not None:
        return ResultadoLectura(
            archivo=carga.nombre,
            formato=formato,
            fuente=fuente,
            hash_archivo=carga.hash,
            hash_mapeo=hash_mapeo,
            hallazgos=(carga.hallazgo,),
        )
    lectura = lector(carga, fuente, mapeo)
    return ResultadoLectura(
        archivo=carga.nombre,
        formato=formato,
        fuente=fuente,
        hash_archivo=carga.hash,
        hash_mapeo=hash_mapeo,
        registros=lectura.registros,
        hallazgos=lectura.hallazgos,
        lineas_cabecera=lectura.lineas_cabecera,
        detenido_en_fila=lectura.detenido_en_fila,
    )
