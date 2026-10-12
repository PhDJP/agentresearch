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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentresearch.registros.normalizacion import (
    normalizar_doi,
    normalizar_texto,
    normalizar_texto_opcional,
)
from agentresearch.trazabilidad import hash_texto, json_canonico

FormatoRegistro = Literal["ris", "bibtex", "scopus_csv", "wos_txt", "csv"]
"""Formatos de exportación que leen los lectores (hito 2b)."""

TipoIdFuente = Literal["eid", "ut", "doi", "pmid", "lens_id", "ninguno"]
"""Tipo del identificador que la fuente asigna al documento."""

LIMITE_POSICION = 99_999
"""Máxima posición de un registro dentro de una búsqueda (cinco dígitos en el ID)."""

_CAMPOS_DE_TEXTO = (
    "id_fuente",
    "titulo",
    "fuente_publicacion",
    "volumen",
    "numero",
    "paginas",
    "pmid",
    "tipo_documento",
    "idioma",
    "resumen",
)
_CAMPOS_DE_LISTA = ("autores", "palabras_clave_autor", "palabras_clave_indexadas")

CAMPOS_DEL_HASH = (
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
    "resumen",
    "palabras_clave_autor",
    "palabras_clave_indexadas",
    "otros",
)
"""Campos bibliográficos que entran al `hash_completo`, desde `tipo_id_fuente` hasta `otros`.

No incluye `id`, `id_importacion`, `archivo` ni `posicion`, que cambian entre
descargas, ni `fuente` ni `formato`, que constan aparte en el registro y en el
evento (ADR-0010, punto 20).
"""

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

    Al construirse, el modelo aplica la normalización de
    `agentresearch.registros.normalizacion` a todo campo de texto, de modo que
    un registro válido siempre está normalizado y su hash es determinista.
    Un texto que queda vacío pasa a `None`, y en `autores`, las palabras clave
    y `otros` se descartan las entradas vacías.
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

    @field_validator(*_CAMPOS_DE_TEXTO, mode="after")
    @classmethod
    def _normalizar_campo_de_texto(cls, valor: str | None) -> str | None:
        return normalizar_texto_opcional(valor)

    @field_validator("doi", mode="after")
    @classmethod
    def _normalizar_doi(cls, valor: str | None) -> str | None:
        return normalizar_doi(valor)

    @field_validator(*_CAMPOS_DE_LISTA, mode="after")
    @classmethod
    def _normalizar_lista(cls, valor: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(texto for texto in map(normalizar_texto, valor) if texto)

    @field_validator("otros", mode="after")
    @classmethod
    def _normalizar_otros(cls, valor: dict[str, str]) -> dict[str, str]:
        normalizados: dict[str, str] = {}
        for etiqueta, contenido in valor.items():
            clave = normalizar_texto(etiqueta)
            texto = normalizar_texto(contenido)
            if clave and texto:
                normalizados[clave] = texto
        return normalizados

    @model_validator(mode="after")
    def _identificador_coherente(self) -> "RegistroNormalizado":
        tiene_id = self.id_fuente is not None
        if self.tipo_id_fuente == "ninguno" and tiene_id:
            raise ValueError("`id_fuente` exige un `tipo_id_fuente` distinto de «ninguno»")
        if self.tipo_id_fuente != "ninguno" and not tiene_id:
            raise ValueError("un `tipo_id_fuente` distinto de «ninguno» exige `id_fuente`")
        return self

    @property
    def hash_completo(self) -> str:
        """SHA-256 del registro completo normalizado (ADR-0010, punto 20).

        Se calcula sobre el JSON canónico (ADR-0006, punto 2) de
        `CAMPOS_DEL_HASH`. El mismo registro descargado dos veces tiene el mismo
        hash. Sirve para comprobar que regenerar el registro desde el original
        da exactamente el mismo registro.
        """
        contenido = {campo: getattr(self, campo) for campo in CAMPOS_DEL_HASH}
        return hash_texto(json_canonico(contenido))


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


def es_id_de_registro(valor: str) -> bool:
    """Indica si `valor` tiene la forma `imp-NNNN-NNNNN` de un `Registro.id`."""
    return _PATRON_ID_REGISTRO.fullmatch(valor) is not None


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
