"""Punto de entrada de la lectura: `leer` (especificación 2b, «Interfaz común»).

El formato lo declara el investigador; el lector no lo adivina.
"""

from collections.abc import Callable
from pathlib import Path

from agentresearch.importacion.ensamblado import Lectura
from agentresearch.importacion.entrada import Carga, cargar
from agentresearch.importacion.lector_ris import leer_ris
from agentresearch.importacion.lector_wos import leer_wos
from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.registros import FormatoRegistro

_LECTORES: dict[str, Callable[[Carga, str], Lectura]] = {
    "ris": leer_ris,
    "wos_txt": leer_wos,
}


def formatos_disponibles() -> tuple[str, ...]:
    """Los formatos para los que ya hay lector."""
    return tuple(_LECTORES)


def leer(ruta: Path, formato: FormatoRegistro, fuente: str) -> ResultadoLectura:
    """Lee un archivo de exportación y devuelve sus registros normalizados y hallazgos.

    No escribe nada. Lanza `ErrorDeArchivo` si el archivo no se puede abrir y
    `ValueError` si el formato no tiene lector o la fuente está vacía. Un archivo
    que no es UTF-8 devuelve un resultado sin registros con el hallazgo L-E01.
    """
    if not fuente.strip():
        raise ValueError("la fuente no puede estar vacía")
    lector = _LECTORES.get(formato)
    if lector is None:
        raise ValueError(f"formato sin lector: {formato}")
    carga = cargar(ruta)
    if carga.hallazgo is not None:
        return ResultadoLectura(
            archivo=carga.nombre,
            formato=formato,
            fuente=fuente,
            hash_archivo=carga.hash,
            hallazgos=(carga.hallazgo,),
        )
    lectura = lector(carga, fuente)
    return ResultadoLectura(
        archivo=carga.nombre,
        formato=formato,
        fuente=fuente,
        hash_archivo=carga.hash,
        registros=lectura.registros,
        hallazgos=lectura.hallazgos,
        lineas_cabecera=lectura.lineas_cabecera,
        detenido_en_fila=lectura.detenido_en_fila,
    )
