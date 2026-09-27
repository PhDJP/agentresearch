"""Ecuación para OpenAlex (ADR-0009, puntos 6, 7 y 9).

Sintaxis verificada el 2026-09-26 en la ayuda de OpenAlex
(https://help.openalex.org/api/searching/ y
https://help.openalex.org/guides/searching, actualizadas el 2026-09-19):

- Operadores `AND`, `OR` y `NOT` en mayúsculas; frases entre comillas.
- La búsqueda normal lematiza y quita palabras vacías, pero no admite
  comodines. `search.exact` admite `*` (con al menos 3 caracteres antes, no
  al inicio, también dentro de frases) pero no lematiza. Solo se usa una de
  las dos por solicitud.
- La URL completa admite unos 4 KB; más allá, la API responde 400.
- No se documenta el tratamiento de guiones ni de tildes.

Pendiente de la consulta real a la API (ADR-0009, punto 9): confirmar que
`title_and_abstract.search` existe y admite booleanos, frases y comodines
(y su variante `.search.exact`). Si no, el campo pasa a `search` (texto
completo).
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
from agentresearch.protocolo.modelo import Busqueda
from agentresearch.protocolo.terminos import Termino

MINIMO_RAIZ = 3
URL_BASE = "https://api.openalex.org/works?"
MAXIMO_URL = 4096
""""About 4 KB" según la ayuda de OpenAlex."""

CAMPO = "title_and_abstract.search"
"""Filtro de búsqueda en título y resumen; `.exact` al final para la búsqueda sin lematizar."""


class TraductorOpenalex(Traductor):
    id = "openalex"
    nombre = "OpenAlex"
    campos = "título y resumen (title_and_abstract.search)"
    maximo = MAXIMO_URL
    documentacion = (
        Documentacion(
            "Search – Querying (OpenAlex Help Center)",
            "https://help.openalex.org/api/searching/",
            "2026-09-26",
        ),
        Documentacion(
            "Searching guide (OpenAlex)", "https://help.openalex.org/guides/searching", "2026-09-26"
        ),
    )

    def __init__(self) -> None:
        self.exacta = False

    def escribir(self, termino: Termino) -> str | None:
        if termino.truncado and (not self.exacta or raiz_corta(termino, MINIMO_RAIZ)):
            return None
        return str(termino)

    def motivo(self, termino: Termino) -> str:
        if not self.exacta:
            return (
                "la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos "
                "truncados tienen variantes"
            )
        return (
            f"OpenAlex exige al menos {MINIMO_RAIZ} letras antes del *, y {str(termino)!r} "
            "tiene una raíz más corta"
        )

    def envolver(self, nucleo: str, varios_bloques: bool) -> str:
        filtro = CAMPO + (".exact" if self.exacta else "")
        return f"{filtro}:{super().envolver(nucleo, varios_bloques)}"

    def medir(self, texto: str) -> int:
        return len(URL_BASE + urlencode({"filter": texto}))

    def _descripcion_longitud(self) -> str:
        return "caracteres de URL codificada"

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        return LimitesTraducidos.como_texto(busqueda, pendientes_del_conector=True)

    def traducir(self, busqueda: Busqueda) -> Ecuacion:
        truncados = [
            item
            for bloque in busqueda.bloques
            for item in terminos_de(bloque)
            if item.termino.truncado
        ]
        self.exacta = bool(truncados) and not _todos_con_variantes(truncados)
        avisos: list[Aviso] = []
        if self.exacta:
            sin_variantes = ", ".join(i.clave for i in truncados if i.variantes is None)
            avisos.append(
                Aviso(
                    "advertencia",
                    "se usa la búsqueda sin lematizar (search.exact) porque hay términos "
                    f"truncados sin variantes ({sin_variantes}): OpenAlex no buscará plurales "
                    "ni otras formas de los términos sin * de toda la ecuación. Para conservar "
                    "la lematización, escriba las variantes de todos los términos truncados",
                )
            )
        bloques = [self._bloque(bloque, avisos) for bloque in busqueda.bloques]
        return self._ecuacion(busqueda, bloques, avisos)


def _todos_con_variantes(truncados: list[TerminoDeBloque]) -> bool:
    return all(item.variantes is not None for item in truncados)
