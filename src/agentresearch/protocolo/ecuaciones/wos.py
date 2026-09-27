"""Ecuación para Web of Science, que se usa por exportación manual (ADR-0009, puntos 6, 7 y 10).

Sintaxis verificada el 2026-09-26 en la ayuda de Web of Science
(webofscience.zendesk.com: Search Rules, Search Fields y Search Operators,
esta última actualizada el 2025-10-17; y la lista de etiquetas de campo de
la búsqueda avanzada):

- `TS` busca en título, resumen, palabras clave de autor y Keywords Plus.
- Las comillas buscan la frase exacta y desactivan la lematización; por eso
  una palabra suelta va sin comillas, salvo que el investigador las haya
  puesto.
- `*` exige al menos 3 caracteres antes en Topic. No se documenta el uso de
  comodines dentro de una frase entre comillas: lo no documentado se trata
  como no admitido, y se usan las variantes del término.
- `TS=hydro-power` recupera `hydro-power` y `hydro power`.
- Sin límite de operadores en TS (el límite es solo de All Fields).
- `PY=(2008-2010)` limita el periodo; no hay etiquetas documentadas de
  idioma ni de tipo de documento para la búsqueda avanzada.
- El tratamiento de las tildes en Topic no se documenta (en los nombres de
  autor no se buscan).
"""

from agentresearch.protocolo.ecuaciones.comun import Documentacion, Traductor, raiz_corta
from agentresearch.protocolo.ecuaciones.limites import LimitesTraducidos, limites_wos
from agentresearch.protocolo.modelo import Busqueda
from agentresearch.protocolo.terminos import Termino

MINIMO_RAIZ = 3


class TraductorWos(Traductor):
    id = "wos"
    nombre = "Web of Science"
    campos = "título, resumen, palabras clave de autor y Keywords Plus (TS)"
    manual = True
    documentacion = (
        Documentacion(
            "Search Rules (Web of Science)",
            "https://webofscience.zendesk.com/hc/en-us/articles/25350084904721-Search-Rules",
            "2026-09-26",
        ),
        Documentacion(
            "Web of Science Core Collection Search Fields",
            "https://webofscience.zendesk.com/hc/en-us/articles/26916258216209-Web-of-Science-Core-Collection-Search-Fields",
            "2026-09-26",
        ),
        Documentacion(
            "Search Operators (Web of Science)",
            "https://webofscience.zendesk.com/hc/en-us/articles/20016122409105-Search-Operators",
            "2026-09-26",
        ),
        Documentacion(
            "Advanced Search Field Tags (Web of Science)",
            "https://images.webofknowledge.com/images/help/WOS/hs_advanced_fieldtags.html",
            "2026-09-26",
        ),
    )

    def escribir(self, termino: Termino) -> str | None:
        if termino.es_frase and termino.truncado:
            return None
        if raiz_corta(termino, MINIMO_RAIZ):
            return None
        return str(termino)

    def motivo(self, termino: Termino) -> str:
        if termino.es_frase and termino.truncado:
            return (
                "Web of Science no documenta el truncamiento dentro de una frase entre comillas, "
                "y lo no documentado se trata como no admitido"
            )
        return (
            f"Web of Science exige al menos {MINIMO_RAIZ} letras antes del *, y "
            f"{str(termino)!r} tiene una raíz más corta"
        )

    def envolver(self, nucleo: str, varios_bloques: bool) -> str:
        return f"TS=({nucleo})"

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        return limites_wos(busqueda)
