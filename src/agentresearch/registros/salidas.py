"""Archivos versionados de una importación: `registros.jsonl` y `registros.csv`.

Son deterministas: los mismos registros dan los mismos bytes en Windows y en
Ubuntu (UTF-8 sin BOM, fin de línea LF, JSON canónico del ADR-0006, punto 2).

- `registros.jsonl`: un registro por línea, **solo con los campos versionables**
  (ver `agentresearch.registros.versionado`).
- `registros.csv`: vista derivada de `registros.jsonl`, con columnas fijas. Las
  celdas que empiezan por `=`, `+`, `-` o `@` **no se alteran**: la vista es una
  derivación fiel del JSONL, y Excel podría interpretarlas como fórmulas. Sin
  BOM, Excel de Windows puede mostrar mal las tildes al abrirlo con doble clic;
  para eso se usa «Datos > Desde texto/CSV» con UTF-8.
"""

import csv
import io
import json
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from agentresearch.registros.modelo import Registro
from agentresearch.registros.versionado import registro_versionable
from agentresearch.trazabilidad import escribir_atomico, hash_bytes, json_canonico

COLUMNAS_CSV = (
    "id",
    "id_importacion",
    "fuente",
    "formato",
    "archivo",
    "posicion",
    "tipo_id_fuente",
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
    "hash_completo",
)
"""Columnas de `registros.csv`, en el orden del esquema."""

SEPARADOR_DE_AUTORES = "; "


def serializar_registros_jsonl(registros: Sequence[Registro], campos: Collection[str]) -> bytes:
    """Serializa los registros: una línea de JSON canónico por registro, en UTF-8 con LF.

    Cada registro se reduce a sus campos versionables con `registro_versionable`,
    así que nada que no se versione llega al archivo.
    """
    lineas = [
        json_canonico(registro_versionable(registro, campos)) + "\n" for registro in registros
    ]
    return "".join(lineas).encode("utf-8")


def serializar_vista_csv(jsonl: bytes) -> bytes:
    """Deriva `registros.csv` de los bytes de `registros.jsonl`.

    Columnas fijas (`COLUMNAS_CSV`), `autores` unidos por `; `, UTF-8 sin BOM y
    LF. Un campo que el JSONL no trae (porque no se versionó) queda vacío. Lanza
    `ValueError` si una línea tiene una clave fuera de las columnas.
    """
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(COLUMNAS_CSV)
    for numero, linea in enumerate(jsonl.decode("utf-8").split("\n"), start=1):
        if not linea:
            continue
        registro: Mapping[str, Any] = json.loads(linea)
        desconocidas = sorted(set(registro) - set(COLUMNAS_CSV))
        if desconocidas:
            raise ValueError(
                f"línea {numero} del JSONL: claves sin columna en el CSV: {', '.join(desconocidas)}"
            )
        escritor.writerow(_celda(registro.get(columna)) for columna in COLUMNAS_CSV)
    return salida.getvalue().encode("utf-8")


def escribir_registros_jsonl(
    ruta: Path | str, registros: Sequence[Registro], campos: Collection[str]
) -> str:
    """Escribe `registros.jsonl` de forma atómica y devuelve el hash de sus bytes."""
    contenido = serializar_registros_jsonl(registros, campos)
    escribir_atomico(ruta, contenido)
    return hash_bytes(contenido)


def escribir_vista_csv(ruta: Path | str, jsonl: bytes) -> str:
    """Escribe `registros.csv` derivado de `jsonl` de forma atómica y devuelve su hash."""
    contenido = serializar_vista_csv(jsonl)
    escribir_atomico(ruta, contenido)
    return hash_bytes(contenido)


def _celda(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, list):
        return SEPARADOR_DE_AUTORES.join(str(elemento) for elemento in valor)
    return str(valor)
