"""Archivo de mapeo del CSV genérico (especificación 2b, «Archivo de mapeo»).

JSON de un solo nivel `{"columna": destino}`, donde `destino` es:

- un nombre de campo del esquema (`"titulo"`, `"doi"`, `"anio"`…), o
- un objeto `{"campo": "autores", "separador": "; "}`, obligatorio para los
  campos de lista y no admitido en los demás, o
- `"id_fuente:TIPO"`, con `TIPO` en `eid`, `ut`, `doi`, `pmid` o `lens_id`.

Un archivo que no se puede leer o no es JSON es un `ErrorDeMapeo` (el comando
lo informa y sale con 1). El contenido inválido no lanza: queda en `problemas`,
y `leer` lo informa como L-E02 con el nombre del archivo de mapeo.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentresearch.registros import TipoIdFuente
from agentresearch.trazabilidad import hash_bytes

CAMPOS_ESCALARES = (
    "titulo",
    "fuente_publicacion",
    "volumen",
    "numero",
    "paginas",
    "doi",
    "pmid",
    "tipo_documento",
    "idioma",
    "resumen",
    "anio",
)
CAMPOS_DE_LISTA = ("autores", "palabras_clave_autor", "palabras_clave_indexadas")
TIPOS_DE_IDENTIFICADOR: tuple[TipoIdFuente, ...] = ("eid", "ut", "doi", "pmid", "lens_id")

PREFIJO_ID = "id_fuente:"


class ErrorDeMapeo(Exception):
    """El archivo de mapeo no se pudo leer o no es JSON."""

    def __init__(self, ruta: Path, motivo: str) -> None:
        super().__init__(f"{ruta.name}: {motivo}")
        self.ruta = ruta
        self.motivo = motivo


@dataclass(frozen=True)
class DestinoMapeo:
    """A dónde va una columna."""

    campo: str
    """Campo del esquema, o `id_fuente` para el identificador de la fuente."""
    separador: str | None = None
    tipo_id: TipoIdFuente | None = None


@dataclass(frozen=True)
class Mapeo:
    """Un archivo de mapeo cargado y validado."""

    nombre: str
    hash: str
    destinos: dict[str, DestinoMapeo]
    problemas: tuple[str, ...] = field(default=())

    @classmethod
    def cargar(cls, ruta: Path) -> "Mapeo":
        """Lee y valida un archivo de mapeo."""
        try:
            datos = ruta.read_bytes()
        except OSError as error:
            raise ErrorDeMapeo(ruta, error.strerror or type(error).__name__) from error
        try:
            contenido = json.loads(datos.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ErrorDeMapeo(ruta, "no es JSON válido en UTF-8") from error
        return cls.desde_objeto(ruta.name, hash_bytes(datos), contenido)

    @classmethod
    def desde_objeto(cls, nombre: str, hash_: str, contenido: Any) -> "Mapeo":
        """Valida el objeto JSON ya leído y devuelve el mapeo con sus problemas."""
        problemas: list[str] = []
        destinos: dict[str, DestinoMapeo] = {}
        if not isinstance(contenido, dict):
            return cls(nombre, hash_, {}, ("el mapeo debe ser un objeto JSON {columna: destino}",))
        vistos: dict[str, str] = {}
        for columna, valor in contenido.items():
            destino, problema = _destino(str(columna), valor)
            if problema is not None or destino is None:
                problemas.append(problema or f"destino inválido para la columna «{columna}»")
                continue
            clave = "id_fuente" if destino.campo == "id_fuente" else destino.campo
            if clave in vistos:
                problemas.append(
                    f"las columnas «{vistos[clave]}» y «{columna}» tienen el mismo destino "
                    f"«{clave}»"
                )
                continue
            vistos[clave] = str(columna)
            destinos[str(columna)] = destino
        return cls(nombre, hash_, destinos, tuple(problemas))


def _destino(columna: str, valor: Any) -> tuple[DestinoMapeo | None, str | None]:
    if isinstance(valor, str):
        if valor.startswith(PREFIJO_ID):
            texto_tipo = valor[len(PREFIJO_ID) :]
            tipo = next((t for t in TIPOS_DE_IDENTIFICADOR if t == texto_tipo), None)
            if tipo is None:
                return None, (
                    f"columna «{columna}»: el tipo de identificador «{texto_tipo}» no es uno de "
                    f"{', '.join(TIPOS_DE_IDENTIFICADOR)}"
                )
            return DestinoMapeo("id_fuente", tipo_id=tipo), None
        return _campo(columna, valor, None)
    if isinstance(valor, dict):
        if set(valor) != {"campo", "separador"}:
            return None, (
                f"columna «{columna}»: el objeto debe tener exactamente «campo» y «separador»"
            )
        campo, separador = valor["campo"], valor["separador"]
        if not isinstance(campo, str) or not isinstance(separador, str) or not separador:
            return None, f"columna «{columna}»: «campo» y «separador» deben ser texto no vacío"
        return _campo(columna, campo, separador)
    return None, f"columna «{columna}»: el destino debe ser un texto o un objeto"


def _campo(
    columna: str, campo: str, separador: str | None
) -> tuple[DestinoMapeo | None, str | None]:
    if campo in CAMPOS_DE_LISTA:
        if separador is None:
            return None, (
                f"columna «{columna}»: el campo de lista «{campo}» exige un objeto con separador"
            )
        return DestinoMapeo(campo, separador=separador), None
    if campo in CAMPOS_ESCALARES:
        if separador is not None:
            return (
                None,
                f"columna «{columna}»: el campo «{campo}» no es de lista y no admite separador",
            )
        return DestinoMapeo(campo), None
    if campo == "id_fuente":
        return None, f"columna «{columna}»: use «id_fuente:TIPO» para el identificador de la fuente"
    return None, f"columna «{columna}»: «{campo}» no es un campo del esquema"
