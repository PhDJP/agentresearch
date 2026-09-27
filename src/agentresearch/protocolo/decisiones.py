"""Decisiones del protocolo, en dos pasos (ADR-0008, puntos 16 y 17).

1. `registrar` valida la decisión y la deja como propuesta
   (`decision_propuesta`). No exige terminal: lo normal es que el LLM escriba
   el archivo con las opciones que presentó y la que eligió el investigador.
2. `confirmar` exige una terminal interactiva, muestra completas las
   decisiones pendientes del investigador y, si este las confirma en lote,
   registra un `decision_confirmada` por cada una.

El paquete no puede saber quién ejecutó `registrar`; por eso la decisión solo
cuenta como tomada cuando el investigador la confirma. `aprobar` y `enmendar`
se niegan mientras haya decisiones pendientes.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentresearch.protocolo.aprobacion import (
    ErrorCicloDeVida,
    Reloj,
    confirmar_frase,
    exigir_terminal,
    hash_leido,
    leer_y_validar,
    problemas_de_persona,
)
from agentresearch.protocolo.ciclo_de_vida import (
    DecisionRegistrada,
    EstadoRegistro,
    escribir_anclaje,
    falta_anclaje,
)
from agentresearch.protocolo.entradas import ErrorEntrada, leer_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_DECISION_CONFIRMADA,
    TIPO_DECISION_PROPUESTA,
    DatosDecisionConfirmada,
    DatosDecisionPropuesta,
    Decision,
    PersonaHumana,
)
from agentresearch.protocolo.modelo import Protocolo
from agentresearch.protocolo.terminal import Terminal
from agentresearch.protocolo.validacion import LecturaProtocolo, ResultadoValidacion
from agentresearch.trazabilidad import Anclaje, EventoRegistro, RegistroEncadenado

MINIMO_OPCIONES = 2
MAXIMO_OPCIONES = 4
"""Entre 2 y 4 opciones fundamentadas (CLAUDE.md, regla 9)."""

ALIAS_DE_MODELO = frozenset(
    {"opus", "sonnet", "haiku", "fable", "default", "opusplan", "best", "claude"}
)
"""Nombres que no identifican una versión exacta del modelo."""


@dataclass(frozen=True, slots=True)
class ResultadoRegistro:
    """Una decisión registrada como propuesta."""

    id_decision: str
    evento: EventoRegistro
    anclaje: Anclaje
    anclaje_recreado: bool = False
    """`anclaje.json` faltaba y se volvió a crear (ADR-0008, punto 21)."""

    def como_dict(self) -> dict[str, Any]:
        return {
            "id_decision": self.id_decision,
            "estado": "pendiente",
            "evento": self.evento.id,
            "anclaje": str(self.anclaje),
            "anclaje_recreado": self.anclaje_recreado,
            "datos": self.evento.datos,
        }


@dataclass(frozen=True, slots=True)
class ResultadoConfirmacion:
    """Decisiones confirmadas en lote por un investigador."""

    confirmado_por: str
    eventos: list[EventoRegistro]
    anclaje: Anclaje | None
    pendientes_de_otros: list[str]
    anclaje_recreado: bool = False
    """`anclaje.json` faltaba y se volvió a crear (ADR-0008, punto 21)."""

    @property
    def confirmadas(self) -> list[str]:
        return [str(evento.datos["id_decision"]) for evento in self.eventos]

    def como_dict(self) -> dict[str, Any]:
        return {
            "confirmado_por": self.confirmado_por,
            "confirmadas": self.confirmadas,
            "eventos": [evento.id for evento in self.eventos],
            "anclaje": str(self.anclaje) if self.anclaje else None,
            "anclaje_recreado": self.anclaje_recreado,
            "pendientes_de_otros": self.pendientes_de_otros,
        }


# --- Registrar ------------------------------------------------------------------------


def registrar_decision(
    ruta_protocolo: Path | str, archivo: Path | str, reloj: Reloj | None = None
) -> ResultadoRegistro:
    """Valida una decisión y la registra como propuesta pendiente de confirmar.

    Lanza `ErrorCicloDeVida` con todos los problemas si no se puede registrar.
    """
    rutas = RutasProtocolo.desde(ruta_protocolo)
    lectura, registro, validacion = leer_y_validar(rutas)
    protocolo = _protocolo_legible(lectura, validacion)
    try:
        decision = validar_modelo(Decision, leer_json(archivo), str(archivo))
    except ErrorEntrada as error:
        raise ErrorCicloDeVida(error.errores) from None
    errores = problemas_de_decision(decision, protocolo, registro)
    if errores:
        raise ErrorCicloDeVida(errores)

    datos = DatosDecisionPropuesta(
        decision=decision,
        version_protocolo=protocolo.metadatos.version_protocolo,
        estado_protocolo=protocolo.estado,
        hash_protocolo=hash_leido(lectura),
    )
    recreado = falta_anclaje(rutas)
    evento = _registro(rutas, reloj).agregar(TIPO_DECISION_PROPUESTA, datos.model_dump(mode="json"))
    return ResultadoRegistro(decision.id_decision, evento, escribir_anclaje(rutas), recreado)


def problemas_de_decision(
    decision: Decision, protocolo: Protocolo, registro: EstadoRegistro
) -> list[str]:
    """Reglas de contenido de una decisión (ADR-0008, punto 16), todas a la vez."""
    errores: list[str] = []
    if not re.fullmatch(r"\S+", decision.id_decision):
        errores.append("id_decision debe ser un identificador sin espacios (p. ej. O1)")
    for campo in ("tema", "pregunta", "justificacion"):
        if not getattr(decision, campo).strip():
            errores.append(f"{campo} está vacío")

    opciones = decision.opciones
    if not MINIMO_OPCIONES <= len(opciones) <= MAXIMO_OPCIONES:
        errores.append(
            f"hay {len(opciones)} opciones; se presentan entre {MINIMO_OPCIONES} y "
            f"{MAXIMO_OPCIONES} (CLAUDE.md, regla 9)"
        )
    ids_opciones: list[str] = []
    for posicion, opcion in enumerate(opciones):
        donde = f"opciones[{posicion}]"
        if not re.fullmatch(r"\S+", opcion.id):
            errores.append(f"{donde}.id debe ser un identificador sin espacios (p. ej. A)")
        elif opcion.id in ids_opciones:
            errores.append(f"{donde}.id {opcion.id!r} está repetido")
        ids_opciones.append(opcion.id)
        if not opcion.descripcion.strip():
            errores.append(f"{donde}.descripcion está vacía")
        for campo, requisito in (
            ("pros", "al menos un pro y ninguno vacío"),
            ("contras", "al menos un contra y ninguno vacío"),
            ("referencias", "al menos una referencia y ninguna vacía"),
        ):
            valores: list[str] = getattr(opcion, campo)
            if not valores or any(not valor.strip() for valor in valores):
                errores.append(f"{donde}.{campo} necesita {requisito} (CLAUDE.md, regla 9)")
    if decision.elegida not in ids_opciones:
        errores.append(f"elegida {decision.elegida!r} no es el id de ninguna opción")

    if decision.decidido_por.tipo != "humano":
        errores.append(
            "decidido_por debe ser un humano: el LLM propone, pero decide el investigador "
            "(CLAUDE.md, regla 1)"
        )
    else:
        errores += problemas_de_persona(protocolo, decision.decidido_por.id, "decidido_por.id")
    errores += _problemas_de_proponente(decision)

    if decision.id_decision in registro.decisiones:
        errores.append(
            f"la decisión {decision.id_decision} ya está registrada; para cambiarla, registre "
            "otra con reemplaza"
        )
    if decision.reemplaza is not None:
        reemplazada = registro.decisiones.get(decision.reemplaza)
        if reemplazada is None:
            errores.append(f"reemplaza {decision.reemplaza!r}, que no está registrada")
        elif reemplazada.reemplazada_por is not None:
            errores.append(
                f"reemplaza {decision.reemplaza!r}, que ya fue reemplazada por "
                f"{reemplazada.reemplazada_por}"
            )
    return errores


def _problemas_de_proponente(decision: Decision) -> list[str]:
    proponente = decision.propuesto_por
    if proponente.tipo == "humano":
        errores = []
        if not proponente.id.strip():
            errores.append("propuesto_por.id está vacío: un humano se identifica con su id")
        if proponente.modelo:
            errores.append("propuesto_por.modelo solo se usa cuando propuesto_por.tipo es llm")
        return errores
    modelo = proponente.modelo
    if not modelo.strip():
        return [
            "propuesto_por.modelo está vacío: un LLM se identifica con el identificador exacto "
            "del modelo (p. ej. claude-opus-5-5)"
        ]
    if (
        re.search(r"\s", modelo)
        or not any(caracter.isdigit() for caracter in modelo)
        or modelo.casefold() in ALIAS_DE_MODELO
        or modelo.casefold().endswith("-latest")
    ):
        return [
            f"propuesto_por.modelo {modelo!r} no es un identificador exacto: sin espacios, con "
            "su versión y sin alias como «opus» o «-latest» (p. ej. claude-opus-5-5)"
        ]
    return []


# --- Confirmar ------------------------------------------------------------------------


def confirmar_decisiones(
    ruta_protocolo: Path | str,
    confirmado_por: str,
    terminal: Terminal,
    reloj: Reloj | None = None,
) -> ResultadoConfirmacion:
    """Muestra las decisiones pendientes de `confirmado_por` y las confirma en lote.

    Lanza `ErrorCicloDeVida` si no se puede confirmar y `OperacionCancelada` si
    el investigador no escribe la frase de confirmación.
    """
    rutas = RutasProtocolo.desde(ruta_protocolo)
    lectura, registro, validacion = leer_y_validar(rutas)
    protocolo = _protocolo_legible(lectura, validacion)
    errores = problemas_de_persona(protocolo, confirmado_por, "--confirmado-por")
    if errores:
        raise ErrorCicloDeVida(errores)

    propias = [d for d in registro.pendientes if d.datos.decision.decidido_por.id == confirmado_por]
    de_otros = [d.id_decision for d in registro.pendientes if d not in propias]
    if not propias:
        return ResultadoConfirmacion(confirmado_por, [], None, de_otros)
    exigir_terminal(terminal)

    terminal.mostrar(
        f"Decisiones pendientes de {confirmado_por}: {len(propias)}\n"
        + "\n".join(texto_de_decision(decision) for decision in propias)
    )
    if de_otros:
        terminal.mostrar(
            f"Pendientes de otros revisores (no se confirman aquí): {', '.join(de_otros)}"
        )
    confirmar_frase(terminal, f"confirmar {len(propias)}")

    recreado = falta_anclaje(rutas)
    registro_eventos = _registro(rutas, reloj)
    eventos = []
    for decision in propias:
        datos = DatosDecisionConfirmada(
            id_decision=decision.id_decision,
            evento_propuesta=decision.evento.id,
            hash_evento_propuesta=decision.evento.hash,
            confirmado_por=PersonaHumana(tipo="humano", id=confirmado_por),
        )
        eventos.append(
            registro_eventos.agregar(TIPO_DECISION_CONFIRMADA, datos.model_dump(mode="json"))
        )
    return ResultadoConfirmacion(
        confirmado_por, eventos, escribir_anclaje(rutas), de_otros, recreado
    )


def texto_de_decision(registrada: DecisionRegistrada) -> str:
    """Una decisión completa, legible, para revisarla antes de confirmarla."""
    decision = registrada.datos.decision
    lineas = [
        f"Decisión {decision.id_decision} ({registrada.evento.id}): {decision.tema}",
        f"  pregunta: {decision.pregunta}",
    ]
    for opcion in decision.opciones:
        marca = " (elegida)" if opcion.id == decision.elegida else ""
        lineas += [
            f"  opción {opcion.id}{marca}: {opcion.descripcion}",
            f"    pros: {'; '.join(opcion.pros)}",
            f"    contras: {'; '.join(opcion.contras)}",
            f"    referencias: {'; '.join(opcion.referencias)}",
        ]
    proponente = decision.propuesto_por
    propuesta_por = (
        f"LLM {proponente.modelo}" if proponente.tipo == "llm" else f"humano {proponente.id}"
    )
    lineas += [
        f"  elegida: {decision.elegida}",
        f"  justificación: {decision.justificacion}",
        f"  propuesta por: {propuesta_por}",
        f"  decidida por: {decision.decidido_por.id}",
    ]
    if decision.reemplaza is not None:
        lineas.append(f"  reemplaza a: {decision.reemplaza}")
    return "\n".join(lineas)


# --- Apoyo ------------------------------------------------------------------------------


def _protocolo_legible(lectura: LecturaProtocolo, validacion: ResultadoValidacion) -> Protocolo:
    """El protocolo cargado, si se puede leer (sin P-E00) y el registro está íntegro (sin P-E10).

    Los demás errores no impiden registrar decisiones: un borrador está
    incompleto mientras se construye.
    """
    errores = [str(h) for h in validacion.errores if h.id_regla in ("P-E00", "P-E10")]
    if errores or lectura.documento is None:
        raise ErrorCicloDeVida(errores)
    return lectura.documento.protocolo


def _registro(rutas: RutasProtocolo, reloj: Reloj | None) -> RegistroEncadenado:
    if reloj is None:
        return RegistroEncadenado(rutas.eventos)
    return RegistroEncadenado(rutas.eventos, reloj=reloj)
