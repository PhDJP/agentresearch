"""Rutas de los archivos del protocolo dentro del repositorio de un estudio.

Junto a `protocolo/protocolo.yaml` viven el registro de eventos
(`eventos.jsonl`), su anclaje (`anclaje.json`) y las copias de cada versión
registrada (`versiones/X.Y.Z.yaml`), además de las ecuaciones de búsqueda
(`ecuaciones.md`, ADR-0009). Se localizan por convención, sin
configuración (ADR-0008, punto 1). El estudio es el directorio padre del
directorio del protocolo.

Toda ruta que se guarda en un evento o en el anclaje es relativa al estudio,
usa `/` como separador y no contiene `..` (ADR-0008, punto 2).
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

NOMBRE_EVENTOS = "eventos.jsonl"
NOMBRE_ANCLAJE = "anclaje.json"
NOMBRE_VERSIONES = "versiones"
NOMBRE_ECUACIONES = "ecuaciones.md"


def es_ruta_relativa_valida(texto: str) -> bool:
    """Indica si `texto` es una ruta relativa con `/`, sin `..`, sin unidad y sin partes vacías."""
    if not texto or "\\" in texto or ":" in texto or texto.startswith("/"):
        return False
    partes = texto.split("/")
    return all(parte not in ("", ".", "..") for parte in partes)


@dataclass(frozen=True, slots=True)
class RutasProtocolo:
    """Rutas absolutas de los archivos del protocolo de un estudio."""

    protocolo: Path

    @classmethod
    def desde(cls, ruta_protocolo: Path | str) -> "RutasProtocolo":
        return cls(Path(ruta_protocolo).resolve())

    @property
    def directorio(self) -> Path:
        return self.protocolo.parent

    @property
    def estudio(self) -> Path:
        return self.directorio.parent

    @property
    def eventos(self) -> Path:
        return self.directorio / NOMBRE_EVENTOS

    @property
    def anclaje(self) -> Path:
        return self.directorio / NOMBRE_ANCLAJE

    @property
    def versiones(self) -> Path:
        return self.directorio / NOMBRE_VERSIONES

    @property
    def ecuaciones(self) -> Path:
        """Ecuaciones de búsqueda generadas desde el protocolo (ADR-0009, punto 12)."""
        return self.directorio / NOMBRE_ECUACIONES

    def copia_de_version(self, version: str) -> Path:
        return self.versiones / f"{version}.yaml"

    def relativa(self, ruta: Path) -> str:
        """Ruta relativa al estudio, con `/`, para guardarla en un evento o mostrarla."""
        return PurePosixPath(*ruta.relative_to(self.estudio).parts).as_posix()

    def resolver(self, relativa: str) -> Path:
        """Ruta absoluta de una ruta relativa guardada. Lanza `ValueError` si no es válida."""
        if not es_ruta_relativa_valida(relativa):
            raise ValueError(f"ruta guardada no válida: {relativa!r}")
        return self.estudio.joinpath(*relativa.split("/"))
