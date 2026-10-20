"""Campos volátiles y lecturas dentro de notas (especificación 2b, «Campos volátiles»).

Un volátil cambia en cada descarga y no describe el documento, así que nunca
entra a `otros` ni al `hash_completo` (ADR-0010, punto 20). Puede ser una
etiqueta, una línea con prefijo dentro de una etiqueta repetible o un elemento
dentro de un campo de texto. El conteo de citas es volátil por decisión del
2026-10-13.
"""

import re
from collections.abc import Sequence

from agentresearch.registros import normalizar_texto

PREFIJOS_N1_VOLATILES_SCOPUS = ("Export Date:", "Cited By:")
"""Líneas de `N1` del RIS de Scopus que se descartan: fecha de exportación y conteo de citas."""

COLUMNAS_VOLATILES_SCOPUS_CSV = ("Cited by",)
"""Columnas del CSV de Scopus que se descartan: el conteo de citas."""

PREFIJO_EID = "EID:"
"""Prefijo de la línea de `N1` del RIS de Scopus que trae el identificador (H1)."""

_SEPARADOR_NOTA = "; "
_CONTEO_DE_CITAS = re.compile(r"Cited by: [0-9]+")


def tiene_prefijo(valor: str, prefijos: Sequence[str]) -> bool:
    """Dice si el valor, con los espacios colapsados, empieza con alguno de los prefijos."""
    texto = normalizar_texto(valor)
    return any(texto.startswith(prefijo) for prefijo in prefijos)


def quitar_conteo_de_nota(valor: str) -> str | None:
    """Quita de `note` (BibTeX de Scopus) solo el elemento `Cited by: n`.

    Regla exacta (especificación 2b):

    1. el valor, con los espacios colapsados, se divide por `"; "`;
    2. se descartan los elementos que coinciden completos con
       `Cited by: [0-9]+` (sensible a mayúsculas);
    3. los demás se unen de nuevo con `"; "`, de modo que el separador vecino
       desaparece con el fragmento y un elemento que no coincide queda igual;
    4. si no queda nada devuelve `None`.
    """
    elementos = normalizar_texto(valor).split(_SEPARADOR_NOTA)
    restantes = [e for e in elementos if _CONTEO_DE_CITAS.fullmatch(e) is None]
    if not restantes or restantes == [""]:
        return None
    return _SEPARADOR_NOTA.join(restantes)


def procesar_n1_scopus(lineas: Sequence[str]) -> tuple[str | None, list[str]]:
    """Separa de las líneas de `N1` el EID y descarta los volátiles.

    Devuelve `(eid, resto)`. El EID es el valor de la **primera** línea que
    empieza con `EID:`; esa línea se consume y no pasa a `otros`. Con valor
    vacío, o sin esa línea, el EID es `None` y no se deriva de ningún otro campo
    (regla 6 de CLAUDE.md). Una segunda línea `EID:` sigue a `resto`. Las
    líneas volátiles se descartan y las demás se conservan en su orden.
    """
    eid: str | None = None
    eid_visto = False
    resto: list[str] = []
    for linea in lineas:
        texto = normalizar_texto(linea)
        if not eid_visto and texto.startswith(PREFIJO_EID):
            eid_visto = True
            valor = texto[len(PREFIJO_EID) :].strip()
            eid = valor or None
            continue
        if any(texto.startswith(p) for p in PREFIJOS_N1_VOLATILES_SCOPUS):
            continue
        resto.append(linea)
    return eid, resto
