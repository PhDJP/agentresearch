"""Normalización determinista de texto y de DOI (ADR-0010, punto 22).

Son las únicas transformaciones que se aplican a un registro: nada se inventa ni
se corrige a mano (regla 6 de CLAUDE.md). Se aplican a todo campo de texto, y
la evidencia literal del hito 5 se calcula sobre el texto ya normalizado.

Cambiar cualquiera de estas reglas exige incrementar `VERSION_NORMALIZACION`.
"""

import re
import unicodedata
from urllib.parse import unquote

VERSION_NORMALIZACION = 1
"""Versión de las reglas de normalización; se registra con cada importación."""

_MINUSCULAS_ASCII = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)

_PATRON_DOI = re.compile(r"(?<![0-9A-Za-z])10\.[0-9]{4,9}(?:\.[0-9]+)*/\S+")
_PATRON_DOI_COMPLETO = re.compile(r"10\.[0-9]{4,9}(?:\.[0-9]+)*/.+")
_PATRON_SERVIDOR = re.compile(
    r"(?:www\.)?[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}/",
    re.IGNORECASE,
)

_PUNTUACION_FINAL = ".,;:"
_CIERRES = {")": "(", "]": "[", ">": "<", "”": "“", "’": "‘", "»": "«"}
_COMILLAS_RECTAS = "\"'"


def normalizar_texto(texto: str) -> str:
    """Aplica Unicode NFC y colapsa cada secuencia de espacios Unicode en un espacio.

    Los espacios Unicode incluyen el espacio duro (U+00A0) y los saltos de
    línea; se recortan los extremos. Los saltos de párrafo se pierden.
    """
    return " ".join(unicodedata.normalize("NFC", texto).split())


def normalizar_texto_opcional(texto: str | None) -> str | None:
    """Como `normalizar_texto`, y un texto que queda vacío pasa a `None`."""
    if texto is None:
        return None
    normalizado = normalizar_texto(texto)
    return normalizado or None


def normalizar_doi(texto: str | None) -> str | None:
    """Extrae el DOI de un texto y lo devuelve en su forma normalizada, o `None`.

    Reglas (DOI Handbook, §2.4; especificación del hito 2, sección 2a):

    - se busca `10.<registrante>/<sufijo>` dentro de cualquier URL o prefijo
      (`https://doi.org/`, `doi:`, el proxy de la biblioteca); el registrante
      admite subdivisiones (`10.1000.10/`);
    - de una URL se quitan la consulta (`?…`) y el fragmento (`#…`), y se
      decodifican los `%XX`;
    - se descarta la puntuación final `.`, `,`, `;` o `:`;
    - cuando el DOI sale de texto libre (hay un prefijo, una URL o texto
      alrededor), se descarta además un cierre final (`)`, `]`, `>` o
      comillas) solo si no tiene su apertura dentro del DOI: hay DOI reales
      con paréntesis internos (tipo SICI). Se compara el número de cierres y
      de aperturas del propio DOI; las comillas rectas cuentan por paridad;
    - solo las letras ASCII A–Z pasan a minúsculas.
    """
    if texto is None:
        return None
    texto = normalizar_texto(texto)
    es_url = "://" in texto or _PATRON_SERVIDOR.match(texto) is not None
    if es_url:
        texto = unquote(texto)
    coincidencia = _PATRON_DOI.search(texto)
    if coincidencia is None:
        return None
    candidato = coincidencia.group(0)
    if es_url:
        candidato = re.split(r"[?#]", candidato, maxsplit=1)[0]
    solo_doi = (
        not es_url and coincidencia.start() == 0 and coincidencia.end() == len(texto)
    )
    candidato = _recortar_final(candidato, texto_libre=not solo_doi)
    if _PATRON_DOI_COMPLETO.fullmatch(candidato) is None:
        return None
    return candidato.translate(_MINUSCULAS_ASCII)


def _recortar_final(candidato: str, *, texto_libre: bool) -> str:
    """Descarta puntuación final y, en texto libre, cierres sin su apertura."""
    while True:
        anterior = candidato
        candidato = candidato.rstrip(_PUNTUACION_FINAL)
        if texto_libre and candidato and _sobra_cierre(candidato):
            candidato = candidato[:-1]
        if candidato == anterior:
            return candidato


def _sobra_cierre(candidato: str) -> bool:
    """Indica si el último carácter es un cierre sin su apertura dentro del texto."""
    ultimo = candidato[-1]
    if ultimo in _CIERRES:
        return candidato.count(ultimo) > candidato.count(_CIERRES[ultimo])
    if ultimo in _COMILLAS_RECTAS:
        return candidato.count(ultimo) % 2 == 1
    return False
