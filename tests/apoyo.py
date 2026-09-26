"""Utilidades compartidas por las pruebas del ciclo de vida del protocolo."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agentresearch.protocolo import RutasProtocolo
from agentresearch.protocolo.aprobacion import ResultadoOperacion, aprobar
from agentresearch.protocolo.ciclo_de_vida import escribir_anclaje
from agentresearch.trazabilidad import RegistroEncadenado

INICIO = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


def reloj_incremental(inicio: datetime = INICIO) -> Callable[[], datetime]:
    """Reloj que avanza un segundo en cada llamada."""
    contador = {"n": 0}

    def _reloj() -> datetime:
        momento = inicio + timedelta(seconds=contador["n"])
        contador["n"] += 1
        return momento

    return _reloj


@dataclass
class TerminalSimulada:
    """Terminal con respuestas preparadas; guarda lo que se mostró y lo que se preguntó."""

    respuestas: list[str | None] = field(default_factory=list)
    interactiva: bool = True
    mostrado: list[str] = field(default_factory=list)
    preguntas: list[str] = field(default_factory=list)
    al_preguntar: Callable[[], None] | None = None

    def es_interactiva(self) -> bool:
        return self.interactiva

    def mostrar(self, texto: str) -> None:
        self.mostrado.append(texto)

    def preguntar(self, pregunta: str) -> str | None:
        self.preguntas.append(pregunta)
        if self.al_preguntar is not None:
            self.al_preguntar()
        return self.respuestas.pop(0) if self.respuestas else None

    @property
    def texto(self) -> str:
        return "\n".join(self.mostrado)


def aprobar_protocolo(ruta: Path, respuestas: list[str | None] | None = None) -> ResultadoOperacion:
    """Aprueba el protocolo confirmando con la frase correcta."""
    terminal = TerminalSimulada(respuestas if respuestas is not None else ["aprobar 1.0.0"])
    return aprobar(ruta, "investigador-1", terminal, reloj=reloj_incremental())


def agregar_evento(ruta: Path, tipo: str, datos: dict[str, Any]) -> None:
    """Agrega un evento al registro del protocolo y actualiza el anclaje."""
    rutas = RutasProtocolo.desde(ruta)
    RegistroEncadenado(rutas.eventos).agregar(tipo, datos)
    escribir_anclaje(rutas)


def reemplazar_en(ruta: Path, viejo: str, nuevo: str) -> None:
    """Reemplaza un fragmento del texto de un archivo, que debe existir."""
    texto = ruta.read_text(encoding="utf-8")
    assert viejo in texto, viejo
    ruta.write_text(texto.replace(viejo, nuevo), encoding="utf-8", newline="\n")


def decision_propuesta(
    id_decision: str, reemplaza: str | None = None, decidido_por: str = "investigador-1"
) -> dict[str, Any]:
    """Datos de un evento `decision_propuesta` válido."""
    opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
    return {
        "decision": {
            "id_decision": id_decision,
            "tema": "t",
            "pregunta": "p",
            "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
            "elegida": "A",
            "justificacion": "j",
            "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
            "decidido_por": {"tipo": "humano", "id": decidido_por},
            "reemplaza": reemplaza,
        },
        "version_protocolo": "0.1.0",
        "estado_protocolo": "borrador",
        "hash_protocolo": "sha256:" + "a" * 64,
    }
