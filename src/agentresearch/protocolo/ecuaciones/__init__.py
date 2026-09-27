"""Ecuaciones de búsqueda por fuente, generadas desde los bloques del protocolo (ADR-0009)."""

from dataclasses import dataclass, field
from typing import Any

from agentresearch.protocolo.ecuaciones.comun import Aviso, Documentacion, Ecuacion, Traductor
from agentresearch.protocolo.ecuaciones.generica import TraductorGenerico
from agentresearch.protocolo.ecuaciones.openalex import TraductorOpenalex
from agentresearch.protocolo.ecuaciones.pubmed import TraductorPubmed
from agentresearch.protocolo.ecuaciones.scopus import TraductorScopus
from agentresearch.protocolo.ecuaciones.wos import TraductorWos
from agentresearch.protocolo.modelo import Protocolo

TRADUCTORES: dict[str, type[Traductor]] = {
    "openalex": TraductorOpenalex,
    "pubmed": TraductorPubmed,
    "scopus": TraductorScopus,
    "wos": TraductorWos,
}
"""ID de fuente reconocido en `fuentes` → traductor (ADR-0009, punto 4)."""


@dataclass(frozen=True, slots=True)
class ConjuntoEcuaciones:
    """Las ecuaciones de todas las fuentes declaradas, más la genérica."""

    ecuaciones: list[Ecuacion]
    sin_traductor: list[str] = field(default_factory=list)
    """Fuentes declaradas en el protocolo que no tienen traductor."""

    @property
    def bloqueadas(self) -> list[str]:
        return [ecuacion.fuente for ecuacion in self.ecuaciones if ecuacion.bloqueada]

    def como_dict(self) -> dict[str, Any]:
        return {
            "ecuaciones": [ecuacion.como_dict() for ecuacion in self.ecuaciones],
            "fuentes_sin_traductor": self.sin_traductor,
            "fuentes_bloqueadas": self.bloqueadas,
        }


def generar_ecuaciones(protocolo: Protocolo) -> ConjuntoEcuaciones:
    """Traduce los bloques del protocolo para cada fuente declarada y la genérica.

    Supone un protocolo sin P-E11: todos sus términos cumplen la gramática.
    """
    ecuaciones = []
    sin_traductor = []
    vistos = set()
    for fuente in protocolo.fuentes:
        clave = fuente.id.strip().lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        traductor = TRADUCTORES.get(clave)
        if traductor is None:
            sin_traductor.append(fuente.id)
        else:
            ecuaciones.append(traductor().traducir(protocolo.busqueda))
    ecuaciones.append(TraductorGenerico().traducir(protocolo.busqueda))
    return ConjuntoEcuaciones(ecuaciones, sin_traductor)


__all__ = [
    "TRADUCTORES",
    "Aviso",
    "ConjuntoEcuaciones",
    "Documentacion",
    "Ecuacion",
    "generar_ecuaciones",
]
