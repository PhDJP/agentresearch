"""Escritura atómica de archivos: temporal, sincronización a disco y reemplazo."""

import os
import tempfile
from pathlib import Path


def escribir_atomico(ruta: Path | str, contenido: bytes) -> None:
    """Escribe `contenido` en `ruta` sin dejar nunca un archivo a medio escribir.

    Escribe en un temporal del mismo directorio, lo sincroniza a disco con
    `flush` y `os.fsync`, y lo pone en su lugar con `os.replace`, que es
    atómico en Windows y en POSIX. En POSIX, además, sincroniza el
    directorio para que el cambio de nombre sobreviva a un corte de energía.
    Si algo falla, el archivo original queda intacto y el temporal se
    elimina. Crea el directorio si no existe.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, nombre_temporal = tempfile.mkstemp(
        dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp"
    )
    temporal = Path(nombre_temporal)
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise
    sincronizar_directorio(ruta.parent)


def sincronizar_directorio(directorio: Path | str) -> None:
    """Sincroniza a disco las entradas de `directorio` (nombres de archivo), solo en POSIX.

    Después de `os.replace` o de crear un archivo, el contenido ya está en
    disco, pero el nombre nuevo puede no estarlo hasta sincronizar el
    directorio. Windows no admite abrir un directorio para sincronizarlo,
    así que ahí no hace nada (ADR-0008, punto 14).
    """
    if os.name != "posix":
        return
    descriptor = os.open(directorio, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
