"""Utilidades de hash para el registro encadenado."""

import hashlib
from pathlib import Path

PREFIJO_SHA256 = "sha256:"


def hash_bytes(contenido: bytes) -> str:
    """Calcula el hash SHA-256 de un contenido binario."""
    return f"{PREFIJO_SHA256}{hashlib.sha256(contenido).hexdigest()}"


def hash_texto(texto: str) -> str:
    """Calcula el hash SHA-256 de un texto, codificado en UTF-8."""
    return hash_bytes(texto.encode("utf-8"))


def hash_archivo(ruta: Path) -> str:
    """Calcula el hash SHA-256 del contenido binario de un archivo."""
    return hash_bytes(Path(ruta).read_bytes())
