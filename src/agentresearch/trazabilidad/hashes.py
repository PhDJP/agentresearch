"""Utilidades de hash para el registro encadenado."""

import hashlib
from pathlib import Path

PREFIJO_SHA256 = "sha256:"


def hash_texto(texto: str) -> str:
    """Calcula el hash SHA-256 de un texto, codificado en UTF-8."""
    digerido = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    return f"{PREFIJO_SHA256}{digerido}"


def hash_archivo(ruta: Path) -> str:
    """Calcula el hash SHA-256 del contenido binario de un archivo."""
    digerido = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    return f"{PREFIJO_SHA256}{digerido}"
