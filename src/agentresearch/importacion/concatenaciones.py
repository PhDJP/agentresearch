"""Resolvedor mínimo de valores de campo BibTeX con concatenaciones `#` (especificación 2b).

`bibtexparser` 2.0.1 resuelve `@string` pero deja una concatenación como texto
crudo (`"Primera " # "parte"`). Este módulo trabaja sobre los valores **crudos**
(con sus delimitadores): cada valor es una expresión de partes unidas por `#`,
donde una parte es

- un texto entre llaves `{…}` (con llaves anidadas balanceadas),
- un texto entre comillas `"…"` (una comilla dentro de llaves no lo cierra),
- un número, o
- el nombre de un `@string`.

Un nombre que no está definido queda como su propio texto: no se inventa nada.
Si la expresión no se puede analizar, se devuelve tal cual (sin delimitadores
exteriores solo si es un texto simple entre llaves o comillas).
"""

from collections.abc import Mapping

_PROFUNDIDAD_MAXIMA = 10
_CARACTERES_DE_NOMBRE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-+/")


class _ErrorDeExpresion(Exception):
    """La expresión no tiene la forma de un valor BibTeX."""


def _leer_llaves(texto: str, inicio: int) -> tuple[str, int]:
    nivel = 0
    for indice in range(inicio, len(texto)):
        caracter = texto[indice]
        if caracter == "\\":
            continue
        if caracter == "{" and texto[indice - 1 : indice] != "\\":
            nivel += 1
        elif caracter == "}" and texto[indice - 1 : indice] != "\\":
            nivel -= 1
            if nivel == 0:
                return texto[inicio + 1 : indice], indice + 1
    raise _ErrorDeExpresion


def _leer_comillas(texto: str, inicio: int) -> tuple[str, int]:
    nivel = 0
    for indice in range(inicio + 1, len(texto)):
        caracter = texto[indice]
        previo = texto[indice - 1 : indice]
        if caracter == "{" and previo != "\\":
            nivel += 1
        elif caracter == "}" and previo != "\\":
            nivel -= 1
        elif caracter == '"' and nivel == 0:
            return texto[inicio + 1 : indice], indice + 1
    raise _ErrorDeExpresion


def _partes(expresion: str) -> list[tuple[str, str]]:
    """Divide la expresión en partes `(tipo, contenido)`; el tipo es texto, numero o nombre."""
    partes: list[tuple[str, str]] = []
    indice = 0
    esperando_parte = True
    while indice < len(expresion):
        caracter = expresion[indice]
        if caracter.isspace():
            indice += 1
        elif caracter == "#":
            if esperando_parte:
                raise _ErrorDeExpresion
            esperando_parte = True
            indice += 1
        elif not esperando_parte:
            raise _ErrorDeExpresion
        elif caracter == "{":
            contenido, indice = _leer_llaves(expresion, indice)
            partes.append(("texto", contenido))
            esperando_parte = False
        elif caracter == '"':
            contenido, indice = _leer_comillas(expresion, indice)
            partes.append(("texto", contenido))
            esperando_parte = False
        elif caracter.isdigit():
            fin = indice
            while fin < len(expresion) and expresion[fin].isdigit():
                fin += 1
            partes.append(("numero", expresion[indice:fin]))
            indice = fin
            esperando_parte = False
        elif caracter in _CARACTERES_DE_NOMBRE:
            fin = indice
            while fin < len(expresion) and expresion[fin] in _CARACTERES_DE_NOMBRE:
                fin += 1
            partes.append(("nombre", expresion[indice:fin]))
            indice = fin
            esperando_parte = False
        else:
            raise _ErrorDeExpresion
    if esperando_parte:
        raise _ErrorDeExpresion
    return partes


def resolver_valor(expresion: str, cadenas: Mapping[str, str], _profundidad: int = 0) -> str:
    """Resuelve un valor crudo: quita delimitadores, concatena y sustituye `@string`.

    `cadenas` es el nombre (en minúsculas) de cada `@string` con su valor crudo.
    """
    try:
        partes = _partes(expresion)
    except _ErrorDeExpresion:
        return expresion.strip()
    resueltas: list[str] = []
    for tipo, contenido in partes:
        if tipo != "nombre":
            resueltas.append(contenido)
            continue
        definicion = cadenas.get(contenido.lower())
        if definicion is None or _profundidad >= _PROFUNDIDAD_MAXIMA:
            resueltas.append(contenido)
        else:
            resueltas.append(resolver_valor(definicion, cadenas, _profundidad + 1))
    return "".join(resueltas)
