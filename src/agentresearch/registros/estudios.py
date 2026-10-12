"""Artículo, estudio y su vínculo: modelos **provisionales** (ADR-0010, punto 21).

Tres cosas distintas (Kitchenham et al., 2011; regla 7 de CLAUDE.md):

- el **registro** es lo que devuelve una fuente para un documento
  (`agentresearch.registros.modelo`);
- el **artículo** es la publicación, a la que la deduplicación (hito 4) asocia
  uno o varios registros;
- el **estudio** es la investigación, con una relación de muchos a muchos con
  los artículos (hito 8): una investigación puede reportarse en varios
  artículos, y un artículo puede reportar varias investigaciones.

Los esquemas de este módulo son **provisionales**: tienen solo los campos
mínimos (ID y vínculos) y los hitos 4 y 8 los completan. Asociar un registro a
un artículo no lo modifica ni lo fusiona: el artículo solo lo referencia.
"""

import re

from pydantic import field_validator, model_validator

from agentresearch.registros.modelo import ModeloRegistros, es_id_de_registro

_PATRON_ID_ARTICULO = re.compile(r"art-[0-9]{5}")
_PATRON_ID_ESTUDIO = re.compile(r"est-[0-9]{5}")


class Articulo(ModeloRegistros):
    """Una publicación, con los registros de las fuentes que la reportan (provisional).

    `id` es `art-NNNNN`. `ids_registros` son los `id` de los `Registro` que la
    deduplicación (hito 4) asoció al artículo; no se repiten.
    """

    id: str
    ids_registros: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def _validar_id(cls, valor: str) -> str:
        if _PATRON_ID_ARTICULO.fullmatch(valor) is None:
            raise ValueError("el ID de un artículo debe tener la forma `art-NNNNN`")
        return valor

    @model_validator(mode="after")
    def _validar_registros(self) -> "Articulo":
        for id_registro in self.ids_registros:
            if not es_id_de_registro(id_registro):
                raise ValueError(f"`{id_registro}` no es el ID de un registro (`imp-NNNN-NNNNN`)")
        if len(set(self.ids_registros)) != len(self.ids_registros):
            raise ValueError("un artículo no puede repetir un registro")
        return self


class Estudio(ModeloRegistros):
    """Una investigación, reportada en uno o varios artículos (provisional).

    `id` es `est-NNNNN`. Sus artículos se expresan con `VinculoArticuloEstudio`.
    """

    id: str

    @field_validator("id")
    @classmethod
    def _validar_id(cls, valor: str) -> str:
        if _PATRON_ID_ESTUDIO.fullmatch(valor) is None:
            raise ValueError("el ID de un estudio debe tener la forma `est-NNNNN`")
        return valor


class VinculoArticuloEstudio(ModeloRegistros):
    """Un artículo reporta un estudio: la relación de muchos a muchos (provisional)."""

    id_articulo: str
    id_estudio: str

    @field_validator("id_articulo")
    @classmethod
    def _validar_articulo(cls, valor: str) -> str:
        if _PATRON_ID_ARTICULO.fullmatch(valor) is None:
            raise ValueError("`id_articulo` debe tener la forma `art-NNNNN`")
        return valor

    @field_validator("id_estudio")
    @classmethod
    def _validar_estudio(cls, valor: str) -> str:
        if _PATRON_ID_ESTUDIO.fullmatch(valor) is None:
            raise ValueError("`id_estudio` debe tener la forma `est-NNNNN`")
        return valor
