"""Núcleo de lectura de CSV compartido por `scopus_csv` y `csv` (especificación 2b).

- Lee las filas con el módulo `csv` y anota la **línea física** donde empieza
  cada una (en un CSV con celdas de varias líneas no coincide con el número de
  fila).
- Fija un límite explícito de campo de 10 MB, y no el máximo posible, solo
  durante la lectura (`csv.field_size_limit` es global del proceso, así que se
  restaura el valor anterior).
- Una celda que supera el límite da L-E02 con el número de fila y **detiene la
  lectura del archivo en esa fila**: tras el error quedan filas basura, así que
  no se continúa. Las filas anteriores se conservan.
"""

import csv
import io
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

LIMITE_CAMPO = 10_485_760
"""Límite de campo: 10 MB (caracteres). Una celda de exactamente este tamaño se lee."""


@contextmanager
def limite_de_campo(limite: int = LIMITE_CAMPO) -> Iterator[None]:
    """Fija `csv.field_size_limit` y restaura el valor anterior al salir."""
    anterior = csv.field_size_limit(limite)
    try:
        yield
    finally:
        csv.field_size_limit(anterior)


@dataclass(frozen=True)
class FilaCsv:
    """Una fila de datos: su número (1 es el encabezado), su línea física y sus celdas."""

    fila: int
    linea: int
    celdas: list[str]


@dataclass
class TablaCsv:
    """El encabezado, las filas de datos leídas y dónde se detuvo la lectura, si se detuvo."""

    encabezado: list[str] | None = None
    filas: list[FilaCsv] = field(default_factory=list)
    detenido_en_fila: int | None = None
    detenido_en_linea: int | None = None


def leer_tabla(texto: str) -> TablaCsv:
    """Lee un CSV ya decodificado. El primer registro es el encabezado."""
    tabla = TablaCsv()
    with limite_de_campo():
        lector = csv.reader(io.StringIO(texto, newline=""))
        fila = 0
        while True:
            linea = lector.line_num + 1
            try:
                celdas = next(lector)
            except StopIteration:
                break
            except csv.Error:
                tabla.detenido_en_fila = fila + 1
                tabla.detenido_en_linea = linea
                break
            fila += 1
            if fila == 1:
                tabla.encabezado = [c.strip() for c in celdas]
            else:
                tabla.filas.append(FilaCsv(fila=fila, linea=linea, celdas=celdas))
    return tabla
