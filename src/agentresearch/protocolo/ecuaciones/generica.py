"""Ecuación genérica: booleana, sin etiquetas de campo (ADR-0009).

Sirve para una base sin traductor propio. Deja los términos tal como están
en el protocolo, con sus comillas y sus `*`, y avisa que cada base trata el
truncamiento y las frases a su manera.
"""

from agentresearch.protocolo.ecuaciones.comun import Traductor
from agentresearch.protocolo.terminos import Termino


class TraductorGenerico(Traductor):
    id = "generica"
    nombre = "la ecuación genérica"
    campos = (
        "los que la base busque por defecto; restrínjalos a título, resumen y palabras clave "
        "si la base lo permite"
    )

    def escribir(self, termino: Termino) -> str | None:
        return str(termino)

    def motivo(self, termino: Termino) -> str:  # pragma: no cover - la genérica lo admite todo
        raise AssertionError("la ecuación genérica admite todos los términos")

    def avisos_de_termino(self, termino: Termino) -> list[str]:
        avisos = []
        if termino.truncado:
            avisos.append(
                "cada base trata el * a su manera (largo mínimo de la raíz, frases con "
                "truncamiento): compruébelo en la documentación de la base"
            )
        if termino.tiene_tilde:
            avisos.append(
                "compruebe cómo trata la base las letras con tilde; si hace falta, agregue la "
                "forma sin tilde como término aparte"
            )
        return avisos
