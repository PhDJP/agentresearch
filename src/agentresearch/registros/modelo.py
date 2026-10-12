"""Modelo del registro normalizado de una fuente (ADR-0010, puntos 19 a 22).

Un registro es lo que devuelve una fuente para un documento. Hay dos tipos:

- `RegistroNormalizado`: lo que produce un lector, sin identificadores de
  importación. Es lo que usa `importar leer`, que no registra nada.
- `Registro`: un `RegistroNormalizado` con `id` e `id_importacion`, que asigna el
  registro de la búsqueda.

Ninguno de los dos es un artículo ni un estudio: el artículo y el estudio se
definen en `agentresearch.registros.estudios` (Kitchenham et al., 2011).
"""

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FormatoRegistro = Literal["ris", "bibtex", "scopus_csv", "wos_txt", "csv"]
"""Formatos de exportación que leen los lectores (hito 2b)."""

TipoIdFuente = Literal["eid", "ut", "doi", "pmid", "lens_id", "ninguno"]
"""Tipo del identificador que la fuente asigna al documento."""

LIMITE_POSICION = 99_999
"""Máxima posición de un registro dentro de una búsqueda (cinco dígitos en el ID)."""

_PATRON_ID_IMPORTACION = re.compile(r"imp-[0-9]{4}")
_PATRON_ID_REGISTRO = re.compile(r"(imp-[0-9]{4})-([0-9]{5})")


class LimiteDePosicionExcedido(ValueError):
    """Una búsqueda tiene más registros que los que admite el ID (`LIMITE_POSICION`)."""


class ModeloRegistros(BaseModel):
    """Base de los modelos del módulo: estricta, sin campos extra e inmutable."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RegistroNormalizado(ModeloRegistros):
    """Un registro leído de una exportación, con su procedencia, sin ID de importación.

    Los campos bibliográficos son los de la especificación del hito 2 (sección
    2a). `archivo` y `posicion` dicen dónde empieza el registro en el original:
    `posicion` es la línea física, en todos los formatos.
    """

    fuente: str = Field(min_length=1)
    formato: FormatoRegistro
    archivo: str = Field(min_length=1)
    posicion: int = Field(ge=1)
    tipo_id_fuente: TipoIdFuente = "ninguno"
    id_fuente: str | None = None
    titulo: str | None = None
    autores: tuple[str, ...] = ()
    anio: int | None = None
    fuente_publicacion: str | None = None
    volumen: str | None = None
    numero: str | None = None
    paginas: str | None = None
    doi: str | None = None
    pmid: str | None = None
    tipo_documento: str | None = None
    idioma: str | None = None
    resumen: str | None = None
    palabras_clave_autor: tuple[str, ...] = ()
    palabras_clave_indexadas: tuple[str, ...] = ()
    otros: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _identificador_coherente(self) -> "RegistroNormalizado":
        tiene_id = self.id_fuente is not None
        if self.tipo_id_fuente == "ninguno" and tiene_id:
            raise ValueError("`id_fuente` exige un `tipo_id_fuente` distinto de «ninguno»")
        if self.tipo_id_fuente != "ninguno" and not tiene_id:
            raise ValueError("un `tipo_id_fuente` distinto de «ninguno» exige `id_fuente`")
        return self


class Registro(RegistroNormalizado):
    """Un registro dentro de una búsqueda registrada.

    `id` es `imp-NNNN-NNNNN`: la importación y la posición del registro en la
    búsqueda (orden declarado de los archivos y, dentro de cada uno, orden de
    lectura), de 1 a `LIMITE_POSICION`.
    """

    id: str
    id_importacion: str

    @model_validator(mode="after")
    def _identificadores_coherentes(self) -> "Registro":
        if _PATRON_ID_IMPORTACION.fullmatch(self.id_importacion) is None:
            raise ValueError("`id_importacion` debe tener la forma `imp-NNNN`")
        coincidencia = _PATRON_ID_REGISTRO.fullmatch(self.id)
        if coincidencia is None:
            raise ValueError("`id` debe tener la forma `imp-NNNN-NNNNN`")
        if coincidencia.group(1) != self.id_importacion:
            raise ValueError("`id` debe empezar por el `id_importacion` del registro")
        if int(coincidencia.group(2)) < 1:
            raise ValueError("la posición del `id` empieza en 1")
        return self


def formatear_id_registro(id_importacion: str, posicion: int) -> str:
    """Arma `imp-NNNN-NNNNN`; lanza `LimiteDePosicionExcedido` si no cabe en cinco dígitos."""
    if posicion > LIMITE_POSICION:
        raise LimiteDePosicionExcedido(
            f"la búsqueda tiene más de {LIMITE_POSICION} registros: el ID admite cinco dígitos"
        )
    if posicion < 1:
        raise ValueError("la posición empieza en 1")
    return f"{id_importacion}-{posicion:05d}"


def construir_registros(
    id_importacion: str, normalizados: Iterable[RegistroNormalizado]
) -> list[Registro]:
    """Asigna a cada registro normalizado su `id`, en el orden recibido, desde 1."""
    registros: list[Registro] = []
    for posicion, normalizado in enumerate(normalizados, start=1):
        registros.append(
            Registro(
                **normalizado.model_dump(),
                id=formatear_id_registro(id_importacion, posicion),
                id_importacion=id_importacion,
            )
        )
    return registros
