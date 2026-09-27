"""Ecuación para Scopus, que se usa por exportación manual (ADR-0009, puntos 6, 7 y 10).

Sintaxis verificada el 2026-09-26 en los consejos de búsqueda de Elsevier
(https://dev.elsevier.com/sc_search_tips.html) y en la ayuda de búsqueda
avanzada de Scopus (actualizada el 2026-08-24):

- `TITLE-ABS-KEY` busca en título, resumen y palabras clave; `KEY` reúne
  AUTHKEY, INDEXTERMS, TRADENAME y CHEMNAME.
- Las comillas buscan una frase aproximada: ignoran la puntuación (el
  guion), incluyen plurales y admiten comodines.
- `*` exige al menos 3 caracteres; se descarta si va justo tras un guion.
- `PUBYEAR > 1994` es "después de 1994" (estricto), `LANGUAGE(french)` usa el
  nombre en inglés, y `DOCTYPE(ar)` usa los códigos de tipo.
- Elsevier anuncia un cambio de precedencia de operadores en 2026: la
  ecuación pone paréntesis en cada bloque y en la unión de bloques.
- No se documenta un límite de longitud ni el tratamiento de las tildes.
"""

from agentresearch.protocolo.ecuaciones.comun import Documentacion, Traductor, raiz_corta
from agentresearch.protocolo.ecuaciones.limites import LimitesTraducidos, limites_scopus
from agentresearch.protocolo.modelo import Busqueda
from agentresearch.protocolo.terminos import Termino

MINIMO_RAIZ = 3


class TraductorScopus(Traductor):
    id = "scopus"
    nombre = "Scopus"
    campos = (
        "título, resumen y palabras clave (TITLE-ABS-KEY); las palabras clave incluyen las del "
        "autor, los términos indexados, los nombres comerciales y los nombres químicos"
    )
    manual = True
    documentacion = (
        Documentacion(
            "Scopus Search Tips (Elsevier Developer Portal)",
            "https://dev.elsevier.com/sc_search_tips.html",
            "2026-09-26",
        ),
        Documentacion(
            "How can I best use the Advanced search? (Scopus)",
            "https://www.elsevier.support/scopus/answer/how-can-i-best-use-the-advanced-search",
            "2026-09-26",
        ),
    )

    def escribir(self, termino: Termino) -> str | None:
        if raiz_corta(termino, MINIMO_RAIZ):
            return None
        return str(termino)

    def motivo(self, termino: Termino) -> str:
        return (
            f"Scopus exige al menos {MINIMO_RAIZ} letras antes del *, y {str(termino)!r} tiene "
            "una raíz más corta"
        )

    def envolver(self, nucleo: str, varios_bloques: bool) -> str:
        return f"TITLE-ABS-KEY({nucleo})"

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        return limites_scopus(busqueda)
