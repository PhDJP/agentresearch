"""Utilidades compartidas por las pruebas de los lectores (todo es sintético y ficticio)."""

import csv
import io
from pathlib import Path
from typing import Any

from agentresearch.registros import RegistroNormalizado


def registro(**campos: Any) -> RegistroNormalizado:
    """Un registro normalizado ficticio; los campos de lista deben pasarse como tuplas."""
    base: dict[str, Any] = {
        "fuente": "scopus",
        "formato": "scopus_csv",
        "archivo": "a.csv",
        "posicion": 2,
    }
    return RegistroNormalizado.model_validate({**base, **campos})


def escribir(ruta: Path, texto: str, *, bom: bool = False, fin_de_linea: str = "\n") -> Path:
    """Escribe un archivo de prueba en UTF-8 con el fin de línea y el BOM pedidos."""
    contenido = texto.replace("\n", fin_de_linea).encode("utf-8")
    ruta.write_bytes((b"\xef\xbb\xbf" if bom else b"") + contenido)
    return ruta


def csv_texto(encabezado: list[str], filas: list[list[str]]) -> str:
    """Un CSV con todos los campos entre comillas y LF, como el de Scopus."""
    salida = io.StringIO()
    escritor = csv.writer(salida, quoting=csv.QUOTE_ALL, lineterminator="\n")
    escritor.writerow(encabezado)
    escritor.writerows(filas)
    return salida.getvalue()
