"""Correspondencia de etiquetas y columnas a campos del esquema (especificación 2b).

Cada formato tiene una **tabla base** y un **perfil por ID de fuente** para lo
que difiere (`scopus`, `wos`, `acs`). Lo que no se mapea va a `otros` con la
etiqueta o la columna de origen, sin traducir. Son constantes tipadas, no YAML
(decisión del 2026-10-13); cada una declara su procedencia.

Procedencia general de los perfiles: exportaciones reales de prueba del
2026-10-13 (una por fuente, de 1 a 5 registros), contrastadas con
- Scopus: https://www.elsevier.support/scopus/answer/what-fields-are-used-when-exporting-documents-from-scopus
  (act. 2025-11-07);
- RIS: https://gris.readthedocs.io/en/stable/specification.html (reconstrucción
  secundaria de la especificación RIS);
- Web of Science: lista oficial de etiquetas de Clarivate, que no se pudo leer;
  lo que no apareció en la exportación de prueba queda «por verificar».
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from agentresearch.registros import TipoIdFuente

TipoEtiqueta = Literal["texto", "lista_por_linea", "lista_con_separador"]
"""Qué significa una línea de continuación (Web of Science):
`texto` se une con un espacio; `lista_por_linea`, una línea es un elemento;
`lista_con_separador`, las líneas se unen con un espacio y el valor se separa por «; »."""

SEPARADOR_LISTA = "; "


@dataclass(frozen=True)
class PerfilEtiquetas:
    """Tabla de etiquetas (RIS o Web of Science) a campos, base o de una fuente."""

    escalares: Mapping[str, tuple[str, ...]]
    """Campo -> etiquetas candidatas, en orden de prioridad (gana la primera presente)."""
    listas: Mapping[str, tuple[str, ...]]
    """Campo de lista -> etiquetas; una de tipo `lista_con_separador` se separa por «; »."""
    anio: tuple[str, ...] = ("PY",)
    paginas_inicio: str = "SP"
    paginas_fin: str = "EP"
    volatiles: frozenset[str] = field(default_factory=frozenset)
    """Etiquetas que se descartan porque cambian en cada descarga."""
    tipos: Mapping[str, TipoEtiqueta] = field(default_factory=dict)
    """Tipo de las etiquetas que no son `texto` (Web of Science)."""
    tipo_id_desde_doi: bool = False
    """El identificador de la fuente es el DOI (ACS, ADR-0010, punto 19)."""
    id_etiqueta: tuple[TipoIdFuente, str] | None = None
    """El identificador de la fuente es el valor de una etiqueta (`UT` de Web of Science)."""
    eid_en_n1: bool = False
    """El EID viene en una línea `EID:` de `N1` y se descartan sus líneas volátiles (H1, H2)."""


PerfilRis = PerfilEtiquetas

RIS_BASE = PerfilEtiquetas(
    escalares={
        "titulo": ("TI", "T1"),
        "fuente_publicacion": ("JO", "JF", "T2"),
        "volumen": ("VL",),
        "numero": ("IS",),
        "doi": ("DO",),
        "resumen": ("AB", "N2"),
        "idioma": ("LA",),
    },
    listas={"autores": ("AU", "A1")},
)
"""Tabla base de RIS. `KW` va a `otros`: RIS no distingue palabras clave de autor e indexadas
y en el RIS de Scopus las mezcla (verificado el 2026-10-13)."""

RIS_SCOPUS = PerfilEtiquetas(
    escalares={**RIS_BASE.escalares, "pmid": ("C2",), "tipo_documento": ("M3",)},
    listas=RIS_BASE.listas,
    eid_en_n1=True,
)
"""Perfil de Scopus: `C2` es el PMID y `M3` el tipo de documento (`TY` es `JOUR` también en una
revisión); el EID y los volátiles `Export Date:` y `Cited By:` están en líneas de `N1`."""

RIS_ACS = PerfilEtiquetas(
    escalares=RIS_BASE.escalares,
    listas=RIS_BASE.listas,
    volatiles=frozenset({"Y2"}),
    tipo_id_desde_doi=True,
)
"""Perfil de ACS: `Y2` es la fecha de descarga (`MM/DD/AAAA`) y el ID de la fuente es el DOI."""

PERFILES_RIS: Mapping[str, PerfilEtiquetas] = {"scopus": RIS_SCOPUS, "acs": RIS_ACS}


def perfil_ris(fuente: str) -> PerfilEtiquetas:
    """El perfil RIS de la fuente, o la tabla base si la fuente no tiene uno propio."""
    return PERFILES_RIS.get(fuente, RIS_BASE)


WOS_BASE = PerfilEtiquetas(
    escalares={
        "titulo": ("TI",),
        "fuente_publicacion": ("SO",),
        "volumen": ("VL",),
        "numero": ("IS",),
        "doi": ("DI",),
        "pmid": ("PM",),
        "tipo_documento": ("DT",),
        "idioma": ("LA",),
        "resumen": ("AB",),
    },
    listas={
        "autores": ("AU",),
        "palabras_clave_autor": ("DE",),
        "palabras_clave_indexadas": ("ID",),
    },
    paginas_inicio="BP",
    paginas_fin="EP",
    volatiles=frozenset({"DA"}),
    tipos={
        "AU": "lista_por_linea",
        "AF": "lista_por_linea",
        "OI": "lista_con_separador",
        "RI": "lista_con_separador",
        "DE": "lista_con_separador",
        "ID": "lista_con_separador",
    },
    id_etiqueta=("ut", "UT"),
)
"""Tabla de Web of Science (texto plano). Verificado con la exportación del 2026-10-13: `AU` y
`AF` (un autor por línea), `TI`, `SO`, `PY`, `VL`, `IS`, `BP`, `EP`, `AR`, `DI`, `UT`, `OI`, `RI`.
Por verificar, porque la exportación no traía resumen: `AB`, `DT`, `LA`, `DE`, `ID`, `PM`, y `DA`
como volátil (la fecha de generación; no apareció en ningún registro)."""

PERFILES_WOS: Mapping[str, PerfilEtiquetas] = {"wos": WOS_BASE}


def perfil_wos(fuente: str) -> PerfilEtiquetas:
    """El perfil de Web of Science: el formato `wos_txt` tiene una sola tabla."""
    del fuente
    return WOS_BASE
