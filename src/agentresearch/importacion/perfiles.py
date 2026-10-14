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


@dataclass(frozen=True)
class PerfilRis:
    """Tabla de etiquetas RIS a campos, base o de una fuente."""

    escalares: Mapping[str, tuple[str, ...]]
    """Campo -> etiquetas candidatas, en orden de prioridad (gana la primera presente)."""
    listas: Mapping[str, tuple[str, ...]]
    """Campo de lista -> etiquetas; cada línea es un elemento."""
    anio: tuple[str, ...] = ("PY",)
    paginas_inicio: str = "SP"
    paginas_fin: str = "EP"
    volatiles: frozenset[str] = field(default_factory=frozenset)
    """Etiquetas que se descartan porque cambian en cada descarga."""
    tipo_id_desde_doi: bool = False
    """El identificador de la fuente es el DOI (ACS, ADR-0010, punto 19)."""
    eid_en_n1: bool = False
    """El EID viene en una línea `EID:` de `N1` y se descartan sus líneas volátiles (H1, H2)."""


RIS_BASE = PerfilRis(
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

RIS_SCOPUS = PerfilRis(
    escalares={**RIS_BASE.escalares, "pmid": ("C2",), "tipo_documento": ("M3",)},
    listas=RIS_BASE.listas,
    eid_en_n1=True,
)
"""Perfil de Scopus: `C2` es el PMID y `M3` el tipo de documento (`TY` es `JOUR` también en una
revisión); el EID y los volátiles `Export Date:` y `Cited By:` están en líneas de `N1`."""

RIS_ACS = PerfilRis(
    escalares=RIS_BASE.escalares,
    listas=RIS_BASE.listas,
    volatiles=frozenset({"Y2"}),
    tipo_id_desde_doi=True,
)
"""Perfil de ACS: `Y2` es la fecha de descarga (`MM/DD/AAAA`) y el ID de la fuente es el DOI."""

PERFILES_RIS: Mapping[str, PerfilRis] = {"scopus": RIS_SCOPUS, "acs": RIS_ACS}


def perfil_ris(fuente: str) -> PerfilRis:
    """El perfil RIS de la fuente, o la tabla base si la fuente no tiene uno propio."""
    return PERFILES_RIS.get(fuente, RIS_BASE)
