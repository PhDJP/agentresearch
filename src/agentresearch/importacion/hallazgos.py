"""Reglas de lectura y hallazgos (hito 2b; especificación, «Reglas de lectura»).

Cada regla tiene un ID estable que aparece en los mensajes y en las pruebas. Un
mensaje cita regla, archivo y línea: **nunca un valor de campo**, porque Claude
Code ve esta salida y los resúmenes de las bases tienen licencia (ADR-0010,
punto 26).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severidad = Literal["error", "advertencia"]


class Regla(BaseModel):
    """Una regla del catálogo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    severidad: Severidad
    descripcion: str


def _regla(id_: str, severidad: Severidad, descripcion: str) -> tuple[str, Regla]:
    return id_, Regla(id=id_, severidad=severidad, descripcion=descripcion)


REGLAS: dict[str, Regla] = dict(
    [
        _regla("L-E01", "error", "El archivo no es UTF-8 (con o sin BOM)"),
        _regla(
            "L-E02",
            "error",
            "Estructura inválida para el formato (registro sin cierre, etiqueta fuera de un "
            "registro, columna obligatoria ausente, fila con más o menos columnas, celda que "
            "supera el límite de campo, BibTeX mal formado o mapeo inválido)",
        ),
        _regla(
            "L-E03",
            "error",
            "Identificador de la fuente repetido dentro del archivo o entre archivos",
        ),
        _regla("L-A01", "advertencia", "Registro sin identificador de la fuente ni DOI"),
        _regla("L-A02", "advertencia", "Registro sin título"),
        _regla("L-A03", "advertencia", "Líneas de cabecera antes del primer registro"),
        _regla("L-A04", "advertencia", "Un campo esperado no aparece en el archivo"),
        _regla(
            "L-A05",
            "advertencia",
            "El mismo DOI en registros que no tienen identificador de la fuente",
        ),
    ]
)
"""Catálogo de reglas de lectura, por ID."""


class Hallazgo(BaseModel):
    """Un problema o aviso encontrado al leer un archivo.

    `linea` es la línea física del archivo donde empieza lo que se informa, o
    `None` si el hallazgo es del archivo completo. En un CSV, `fila` es además el
    número de fila (1 es el encabezado).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    regla: str
    severidad: Severidad
    archivo: str = Field(min_length=1)
    linea: int | None = Field(default=None, ge=1)
    fila: int | None = Field(default=None, ge=1)
    mensaje: str = Field(min_length=1)


def crear_hallazgo(
    regla: str,
    archivo: str,
    mensaje: str,
    linea: int | None = None,
    fila: int | None = None,
) -> Hallazgo:
    """Crea un hallazgo con la severidad del catálogo."""
    if regla not in REGLAS:
        raise ValueError(f"regla desconocida: {regla}")
    return Hallazgo(
        regla=regla,
        severidad=REGLAS[regla].severidad,
        archivo=archivo,
        linea=linea,
        fila=fila,
        mensaje=mensaje,
    )
