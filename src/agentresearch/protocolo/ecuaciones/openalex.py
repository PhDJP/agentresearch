"""Ecuación para OpenAlex (ADR-0009, puntos 6, 7 y 9).

Sintaxis verificada el 2026-09-26 en la ayuda de OpenAlex
(https://help.openalex.org/api/searching/ y
https://help.openalex.org/guides/searching, actualizadas el 2026-09-19), y
el 2026-09-27 con consultas reales a la API (los conteos están en el
ADR-0009, punto 9):

- El filtro `title_and_abstract.search` (lematizado) y su variante
  `title_and_abstract.search.exact` existen y admiten `AND`, `OR` y
  paréntesis; los operadores van en mayúsculas (`or` en minúsculas no es un
  operador). Las comillas buscan la frase.
- La búsqueda lematizada rechaza los comodines (HTTP 400). La exacta los
  admite, también dentro de frases, con al menos 3 caracteres antes (con
  menos, HTTP 400), pero no lematiza. Solo se usa una de las dos.
- La búsqueda lematizada quita las palabras vacías, también dentro de una
  frase entre comillas: `"by-product"` se busca como `product`. La exacta
  las conserva.
- Un término con guion sin comillas se busca como AND de sus partes
  (`post-extraction` da lo mismo que `post AND extraction`); entre comillas,
  como frase.
- Las letras con tilde son distintas de las sin tilde (`liofilización` y
  `liofilizacion` recuperan conjuntos distintos).
- Una solicitud admite varios filtros de búsqueda separados por coma, que
  se combinan con AND, y pueden mezclar el lematizado y el exacto. Por eso
  cada bloque es un filtro con su propio modo.
- La URL completa admite unos 4 KB; más allá, la API responde 400.
"""

from urllib.parse import urlencode

from agentresearch.protocolo.ecuaciones.comun import (
    Aviso,
    Documentacion,
    Ecuacion,
    TerminoDeBloque,
    Traductor,
    raiz_corta,
    terminos_de,
)
from agentresearch.protocolo.ecuaciones.limites import LimitesTraducidos
from agentresearch.protocolo.modelo import Bloque, Busqueda
from agentresearch.protocolo.terminos import SEPARADORES_INTERNOS, Termino

MINIMO_RAIZ = 3
URL_BASE = "https://api.openalex.org/works?"
LIMITE_URL = 4096
""""About 4 KB" según la ayuda de OpenAlex: el límite de la URL completa."""
UMBRAL_URL = 3900
"""Longitud a partir de la cual se avisa (ADR-0009, punto 9).

La ecuación se mide como una URL con solo el filtro. El conector agregará
`api_key` y otros parámetros (`per-page`, `cursor`, `select`), así que el aviso
deja un margen bajo el límite de unos 4 KB.
"""

CAMPO = "title_and_abstract.search"
"""Filtro de búsqueda en título y resumen; `.exact` al final para la búsqueda sin lematizar."""

PALABRAS_VACIAS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into",
        "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then",
        "there", "these", "they", "this", "to", "was", "will", "with",
    }
)  # fmt: skip
"""Palabras vacías que la búsqueda lematizada quita (ADR-0009, punto 9).

Es la lista de inglés por defecto de Lucene. Se verificaron con consultas
by, for, with, in, of, the y and (y no se quitan via, per, co, non, post ni
pre); el resto se infiere. Tratar de más una palabra como vacía solo cuesta
la lematización (se usa la búsqueda exacta); tratar de menos ampliaría la
búsqueda sin aviso.
"""


def palabras_vacias_en(termino: Termino) -> list[str]:
    """Palabras vacías dentro de una frase o de un término con guion.

    Un término de una sola palabra sin guion no cuenta: si es una palabra
    vacía, la frase no pierde nada que no se haya pedido explícitamente.
    """
    partes = []
    for palabra in termino.palabras:
        texto = palabra.texto.lower()
        for separador in SEPARADORES_INTERNOS:
            texto = texto.replace(separador, " ")
        partes += texto.split()
    if len(partes) < 2:
        return []
    return [parte for parte in partes if parte in PALABRAS_VACIAS]


class TraductorOpenalex(Traductor):
    id = "openalex"
    nombre = "OpenAlex"
    campos = "título y resumen (title_and_abstract.search)"
    maximo = UMBRAL_URL
    union_de_bloques = ","
    documentacion = (
        Documentacion(
            "Search – Querying (OpenAlex Help Center)",
            "https://help.openalex.org/api/searching/",
            "2026-09-26",
        ),
        Documentacion(
            "Searching guide (OpenAlex)", "https://help.openalex.org/guides/searching", "2026-09-26"
        ),
        Documentacion(
            "Consultas de verificación a la API de OpenAlex (ADR-0009, punto 9)",
            "https://api.openalex.org/works",
            "2026-09-27",
        ),
    )

    def __init__(self) -> None:
        self.exacta = False

    def escribir(self, termino: Termino) -> str | None:
        if termino.truncado and (not self.exacta or raiz_corta(termino, MINIMO_RAIZ)):
            return None
        if termino.tiene_guion and not termino.entre_comillas:
            # Sin comillas, OpenAlex busca las partes con AND; entre comillas, como frase.
            return f'"{termino.texto}"'
        return str(termino)

    def motivo(self, termino: Termino) -> str:
        if not self.exacta:
            return (
                "la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos "
                "truncados del bloque tienen variantes"
            )
        return (
            f"OpenAlex exige al menos {MINIMO_RAIZ} letras antes del *, y {str(termino)!r} "
            "tiene una raíz más corta"
        )

    def avisos_de_termino(self, termino: Termino) -> list[str]:
        avisos = []
        if termino.tiene_tilde:
            avisos.append(
                "OpenAlex distingue las letras con tilde de las sin tilde (verificado el "
                "2026-09-27); si quiere recuperar también la forma sin tilde, agréguela como "
                "término aparte (ADR-0009, punto 8)"
            )
        return avisos

    def notas_de_termino(self, termino: Termino) -> list[str]:
        if termino.tiene_guion and not termino.entre_comillas:
            return [
                "se escribe entre comillas: sin ellas, OpenAlex busca las partes del término con "
                "guion unidas por AND, no como frase"
            ]
        return []

    def envolver(self, nucleo: str, varios_bloques: bool) -> str:
        return nucleo  # cada bloque ya es un filtro completo, unidos por coma

    def _texto_maximo(self) -> str:
        return (
            f"el umbral de aviso de OpenAlex ({UMBRAL_URL}), que deja margen para api_key y los "
            f"demás parámetros bajo el límite de unos 4 KB de la URL ({LIMITE_URL})"
        )

    def medir(self, texto: str) -> int:
        return len(URL_BASE + urlencode({"filter": texto}))

    def _descripcion_longitud(self) -> str:
        return "caracteres de URL codificada"

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        return LimitesTraducidos.como_texto(busqueda, pendientes_del_conector=True)

    def traducir(self, busqueda: Busqueda) -> Ecuacion:
        avisos: list[Aviso] = []
        bloques = [self._filtro_de_bloque(bloque, avisos) for bloque in busqueda.bloques]
        return self._ecuacion(busqueda, bloques, avisos)

    def _filtro_de_bloque(self, bloque: Bloque, avisos: list[Aviso]) -> str | None:
        """El bloque como filtro, con su propio modo (ADR-0009, punto 9)."""
        items = list(terminos_de(bloque))
        sin_variantes = [i.clave for i in items if i.termino.truncado and i.variantes is None]
        con_vacias = _terminos_con_palabras_vacias(items)
        self.exacta = bool(sin_variantes or con_vacias)
        sin_lematizar = (
            f"el bloque {bloque.id} usa la búsqueda sin lematizar (search.exact): en este "
            "bloque, OpenAlex no buscará plurales ni otras formas de los términos sin *. "
        )
        if sin_variantes:
            avisos.append(
                Aviso(
                    "advertencia",
                    sin_lematizar + "Motivo: tiene términos truncados sin variantes "
                    f"({', '.join(sin_variantes)}). Para conservar la lematización en el bloque, "
                    "escriba sus variantes",
                    bloque.id,
                )
            )
        if con_vacias:
            avisos.append(
                Aviso(
                    "advertencia",
                    sin_lematizar
                    + "Motivo: la búsqueda lematizada quita las palabras vacías también dentro de "
                    'frases y términos con guion ("by-product" se buscaría como "product"); '
                    f"términos afectados: {', '.join(con_vacias)}. Si quiere recuperar también "
                    "la forma sin la palabra vacía (p. ej. byproduct), agréguela como término "
                    "aparte, sin reemplazar el original, que las demás fuentes buscan como frase; "
                    "si no, acepte la búsqueda exacta en este bloque",
                    bloque.id,
                )
            )
        cuerpo = self._bloque(bloque, avisos)
        if cuerpo is None:
            return None
        return f"{CAMPO}{'.exact' if self.exacta else ''}:{cuerpo}"


def _terminos_con_palabras_vacias(items: list[TerminoDeBloque]) -> list[str]:
    """Términos de un bloque que la búsqueda lematizada escribiría con palabras vacías.

    Se miran los términos que irían en esa búsqueda: los no truncados, y las
    variantes de los truncados que las tienen.
    """
    afectados = []
    for item in items:
        if not item.termino.truncado:
            candidatos = [item.termino]
        else:
            candidatos = list(item.variantes or ())
        for termino in candidatos:
            if palabras_vacias_en(termino):
                afectados.append(str(termino))
    return afectados
