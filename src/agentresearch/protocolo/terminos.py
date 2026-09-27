"""Gramática de los términos de búsqueda del protocolo (ADR-0009, puntos 1 a 3).

Cada término de un bloque de búsqueda es una palabra, una palabra truncada
(`secad*`) o una frase entre comillas dobles, cuyas palabras también pueden
ir truncadas (`"hemp seed*"`). Una palabra está hecha de letras (con o sin
tilde) y dígitos, con guiones o apóstrofos internos (`by-product`).

Lo que no cumple la gramática es el error P-E11: un término que no se puede
traducir igual en todas las fuentes. La gramática no depende de ninguna
fuente; los límites de cada una (largo mínimo de la raíz, frases con
truncamiento) los aplica su traductor.
"""

from dataclasses import dataclass

TRUNCAMIENTO = "*"
SEPARADORES_INTERNOS = frozenset("-'’")
"""Guion y apóstrofos, admitidos solo entre letras o dígitos."""

OPERADORES = frozenset({"and", "or", "not", "near", "same"})
"""Operadores de alguna fuente (Scopus, Web of Science, PubMed, OpenAlex), en minúsculas.

Web of Science no distingue mayúsculas en sus operadores, así que se rechazan
en cualquier forma.
"""

_COMODINES_NO_ADMITIDOS = frozenset("?$#")
_SINTAXIS_DE_FUENTE = frozenset("()[]{}=:/\\")


class TerminoNoValido(ValueError):
    """El término no cumple la gramática (P-E11); el mensaje explica por qué."""


@dataclass(frozen=True, slots=True)
class Palabra:
    """Una palabra de un término, sin el `*` final."""

    texto: str
    truncada: bool

    @property
    def raiz(self) -> str:
        """Parte que sigue al último guion o apóstrofo: la unidad que indexan las bases.

        Es la que cuenta para el largo mínimo antes del comodín (ADR-0009, punto 7).
        """
        raiz = self.texto
        for separador in SEPARADORES_INTERNOS:
            raiz = raiz.rsplit(separador, 1)[-1]
        return raiz

    @property
    def tiene_separador(self) -> bool:
        return any(caracter in SEPARADORES_INTERNOS for caracter in self.texto)

    def __str__(self) -> str:
        return self.texto + (TRUNCAMIENTO if self.truncada else "")


@dataclass(frozen=True, slots=True)
class Termino:
    """Un término de búsqueda ya analizado."""

    original: str
    palabras: tuple[Palabra, ...]
    entre_comillas: bool

    @property
    def truncado(self) -> bool:
        return any(palabra.truncada for palabra in self.palabras)

    @property
    def es_frase(self) -> bool:
        return len(self.palabras) > 1

    @property
    def tiene_tilde(self) -> bool:
        """Contiene letras fuera de ASCII (tildes, eñes, letras griegas)."""
        return any(not caracter.isascii() for caracter in self.texto)

    @property
    def tiene_guion(self) -> bool:
        return any(palabra.tiene_separador for palabra in self.palabras)

    @property
    def texto(self) -> str:
        """Las palabras separadas por un espacio, con sus `*`, sin comillas."""
        return " ".join(str(palabra) for palabra in self.palabras)

    def __str__(self) -> str:
        return f'"{self.texto}"' if self.entre_comillas else self.texto


def analizar_termino(texto: str) -> Termino:
    """Analiza un término de búsqueda. Lanza `TerminoNoValido` si no cumple la gramática."""
    limpio = texto.strip()
    if not limpio:
        raise TerminoNoValido("el término está vacío")
    comillas = limpio.count('"')
    if comillas == 0:
        partes = limpio.split()
        if len(partes) > 1:
            raise TerminoNoValido(
                "tiene varias palabras sin comillas; cada base las interpretaría distinto "
                "(AND implícito o frase). Escríbalo entre comillas si es una frase, o sepárelo "
                "en varios términos"
            )
        return Termino(texto, (_analizar_palabra(partes[0]),), entre_comillas=False)
    if comillas != 2 or not (limpio.startswith('"') and limpio.endswith('"')):
        raise TerminoNoValido(
            "las comillas deben rodear el término completo, una al inicio y otra al final"
        )
    partes = limpio[1:-1].split()
    if not partes:
        raise TerminoNoValido("las comillas están vacías")
    palabras = tuple(_analizar_palabra(parte) for parte in partes)
    return Termino(texto, palabras, entre_comillas=True)


def _analizar_palabra(texto: str) -> Palabra:
    if texto.lower() in OPERADORES:
        raise TerminoNoValido(
            f"«{texto}» es un operador de búsqueda en alguna fuente, y los operadores los pone el "
            "paquete (OR dentro del bloque, AND entre bloques). Si es parte de una frase, puede "
            "separarla en varios términos del bloque (cada uno entre comillas si tiene varias "
            f"palabras) o reformularla sin la palabra «{texto}»; elija lo que conserve el "
            "significado que busca"
        )
    especiales = sorted({c for c in texto if c in _SINTAXIS_DE_FUENTE})
    if especiales:
        raise TerminoNoValido(
            f"«{texto}» contiene {' '.join(especiales)}: paréntesis, etiquetas de campo u otra "
            "sintaxis propia de una fuente. El paquete la genera para cada fuente"
        )
    comodines = sorted({c for c in texto if c in _COMODINES_NO_ADMITIDOS})
    if comodines:
        raise TerminoNoValido(
            f"«{texto}» usa el comodín {' '.join(comodines)}, que no todas las fuentes admiten; "
            "solo se admite el truncamiento final con *"
        )
    truncada = texto.endswith(TRUNCAMIENTO)
    nucleo = texto.removesuffix(TRUNCAMIENTO) if truncada else texto
    if TRUNCAMIENTO in nucleo:
        raise TerminoNoValido(
            f"«{texto}» tiene * al inicio o en medio de la palabra; solo se admite al final"
        )
    if not nucleo:
        raise TerminoNoValido("el * debe seguir a una palabra")
    if nucleo[0] in SEPARADORES_INTERNOS or nucleo[-1] in SEPARADORES_INTERNOS:
        raise TerminoNoValido(
            f"«{texto}» tiene un guion o un apóstrofo al inicio o al final de la palabra "
            "(o justo antes del *); solo se admiten entre letras"
        )
    anterior = ""
    for caracter in nucleo:
        if caracter in SEPARADORES_INTERNOS:
            if anterior in SEPARADORES_INTERNOS:
                raise TerminoNoValido(f"«{texto}» tiene dos separadores seguidos")
        elif not caracter.isalnum():
            raise TerminoNoValido(
                f"«{texto}» contiene el carácter {caracter!r}; una palabra lleva letras, dígitos "
                "y guiones o apóstrofos internos"
            )
        anterior = caracter
    return Palabra(nucleo, truncada)


def problemas_de_variantes(
    terminos: list[str], variantes: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """Problemas de las variantes de un bloque: (clave, mensaje) por cada uno.

    Cada clave debe ser un término truncado del bloque, y cada variante, una
    palabra o una frase válidas y sin truncamiento (ADR-0009, punto 3).
    """
    truncados = set()
    for termino in terminos:
        try:
            if analizar_termino(termino).truncado:
                truncados.add(termino.strip())
        except TerminoNoValido:
            continue
    problemas: list[tuple[str, str]] = []
    for clave, lista in variantes.items():
        if clave.strip() not in truncados:
            problemas.append(
                (clave, f"la clave {clave!r} no es un término truncado de este bloque")
            )
            continue
        if not lista:
            problemas.append((clave, f"el término {clave!r} no tiene ninguna variante"))
        for variante in lista:
            try:
                analizada = analizar_termino(variante)
            except TerminoNoValido as error:
                problemas.append((clave, f"la variante {variante!r} de {clave!r}: {error}"))
                continue
            if analizada.truncado:
                problemas.append(
                    (clave, f"la variante {variante!r} de {clave!r} no puede llevar *")
                )
    return problemas
