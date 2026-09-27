"""Ecuación para PubMed (ADR-0009, puntos 6 y 7).

Sintaxis verificada el 2026-09-26 en la guía de usuario de PubMed
(https://pubmed.ncbi.nlm.nih.gov/help/, actualizada el 2026-09-24):

- `[tiab]` busca en título y resumen; tras varias palabras, las busca como
  frase (`kidney allograft[tiab]`), y se combina con comillas.
- El truncamiento `*` exige al menos 4 caracteres antes del primer
  comodín, admite varios comodines en una frase (`"colo* cancer*"`) y se
  puede usar tras un guion (`breast-feed*`).
- Un guion busca la frase; si no está en el índice de frases, no devuelve
  resultados.
- Las comillas, las etiquetas y los comodines desactivan el mapeo
  automático de términos (ATM).
- No se documenta un límite de longitud ni el tratamiento de las tildes.
"""

from agentresearch.protocolo.ecuaciones.comun import Documentacion, Traductor, raiz_corta
from agentresearch.protocolo.ecuaciones.limites import LimitesTraducidos
from agentresearch.protocolo.modelo import Busqueda
from agentresearch.protocolo.terminos import Termino

MINIMO_RAIZ = 4


class TraductorPubmed(Traductor):
    id = "pubmed"
    nombre = "PubMed"
    campos = "título y resumen ([tiab])"
    documentacion = (
        Documentacion("PubMed User Guide", "https://pubmed.ncbi.nlm.nih.gov/help/", "2026-09-26"),
    )

    def escribir(self, termino: Termino) -> str | None:
        if raiz_corta(termino, MINIMO_RAIZ):
            return None
        return f"{termino}[tiab]"

    def motivo(self, termino: Termino) -> str:
        return (
            f"PubMed exige al menos {MINIMO_RAIZ} letras antes del *, y {str(termino)!r} tiene "
            "una raíz más corta"
        )

    def avisos_de_termino(self, termino: Termino) -> list[str]:
        avisos = super().avisos_de_termino(termino)
        if termino.tiene_guion:
            avisos.append(
                "PubMed busca un término con guion como frase y, si no está en su índice de "
                "frases, no devuelve resultados; compruébelo en la interfaz o agregue la forma "
                "sin guion como frase aparte"
            )
        return avisos

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        return LimitesTraducidos.como_texto(busqueda, pendientes_del_conector=True)
