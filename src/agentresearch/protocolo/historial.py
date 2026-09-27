"""Historial del protocolo: versiones, enmiendas, decisiones y anclaje (ADR-0008, punto 18).

Alimenta los ítems 5 (protocolo y registro) y 20 (desviaciones del protocolo)
de PRISMA-ScR. Muestra el anclaje del registro (número de eventos y hash del
último) para poder guardarlo fuera del estudio y detectar después la
eliminación de eventos finales (ADR-0006, punto 10).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentresearch.protocolo.ciclo_de_vida import (
    DecisionRegistrada,
    EstadoRegistro,
    VersionRegistrada,
    leer_estado_registro,
    nota_falta_anclaje,
)
from agentresearch.protocolo.diferencias import Cambio
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import DatosAprobado, DatosEnmendado
from agentresearch.protocolo.validacion import (
    Hallazgo,
    hallazgos_de_directorio,
    leer_para_validar,
    resumen_registro,
)


@dataclass(frozen=True, slots=True)
class Historial:
    """El recorrido registrado del protocolo y el estado de su registro."""

    rutas: RutasProtocolo
    estado: str | None
    version_protocolo: str | None
    hash_archivo: str | None
    registro: EstadoRegistro
    hallazgos: list[Hallazgo]
    """Hallazgos de P-E09 y P-E10."""

    @property
    def integro(self) -> bool:
        """Indica si el historial es fiable (sin P-E10)."""
        return self.registro.integro

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta_protocolo": self.rutas.relativa(self.rutas.protocolo),
            "estado": self.estado,
            "version_protocolo": self.version_protocolo,
            "hash_archivo": self.hash_archivo,
            "registro": resumen_registro(self.registro),
            "estado_anclaje": estado_del_anclaje(self.registro),
            "versiones": [_version_como_dict(v) for v in self.registro.versiones],
            "decisiones": [_decision_como_dict(d) for d in self.registro.decisiones.values()],
            "hallazgos": [hallazgo.como_dict() for hallazgo in self.hallazgos],
        }


def construir_historial(ruta: Path | str) -> Historial:
    """Lee el protocolo y su registro, y reúne su historial."""
    rutas = RutasProtocolo.desde(ruta)
    lectura = leer_para_validar(rutas.protocolo)
    registro = leer_estado_registro(rutas)
    documento = lectura.documento
    estado = documento.protocolo.estado if documento is not None else None
    return Historial(
        rutas=rutas,
        estado=estado,
        version_protocolo=(
            documento.protocolo.metadatos.version_protocolo if documento is not None else None
        ),
        hash_archivo=lectura.hash,
        registro=registro,
        hallazgos=hallazgos_de_directorio(registro, lectura.hash, estado),
    )


def estado_del_anclaje(registro: EstadoRegistro) -> str:
    """Relación entre el anclaje guardado en `anclaje.json` y el registro actual."""
    if not registro.existe_registro:
        return "sin registro"
    if registro.anclaje_actual is None:
        return "registro dañado"
    guardado = registro.anclaje_guardado
    if guardado is None:
        return "no válido" if registro.existe_anclaje else "sin anclaje guardado"
    if guardado == registro.anclaje_actual:
        return "coincide"
    if not registro.anclaje_cumplido:
        return "no se cumple"
    return "atrasado (válido como prefijo)"


def texto_historial(historial: Historial) -> list[str]:
    """Líneas legibles del historial."""
    rutas = historial.rutas
    registro = historial.registro
    protocolo_rel = rutas.relativa(rutas.protocolo)
    if historial.estado is None:
        lineas = [f"protocolo: {protocolo_rel} (no se pudo leer; ejecute protocolo validar)"]
    else:
        lineas = [
            f"protocolo: {protocolo_rel} ({historial.estado}, versión "
            f"{historial.version_protocolo})"
        ]
    eventos_rel = rutas.relativa(rutas.eventos)
    if not registro.existe_registro:
        lineas.append(f"registro: no existe {eventos_rel} (sin eventos registrados)")
    else:
        integridad = "íntegro" if registro.integro else "con problemas (P-E10)"
        lineas.append(f"registro: {eventos_rel}, {integridad}, {len(registro.eventos)} eventos")
    if registro.anclaje_actual is not None:
        lineas.append(f"anclaje: {registro.anclaje_actual}")
        guardado = registro.anclaje_guardado
        detalle = estado_del_anclaje(registro)
        if guardado is not None and guardado != registro.anclaje_actual:
            detalle += f": {guardado}"
        lineas.append(f"anclaje guardado en {rutas.relativa(rutas.anclaje)}: {detalle}")
    if registro.falta_anclaje:
        lineas.append(f"nota: {nota_falta_anclaje(rutas)}")

    lineas.append("versiones:" if registro.versiones else "versiones: ninguna registrada")
    for version in registro.versiones:
        lineas += _texto_version(version)
    lineas.append("decisiones:" if registro.decisiones else "decisiones: ninguna registrada")
    for decision in registro.decisiones.values():
        lineas.append(_texto_decision(decision))
    if historial.hallazgos:
        lineas.append("hallazgos:")
        lineas += [f"  {hallazgo}" for hallazgo in historial.hallazgos]
    return lineas


def _texto_version(version: VersionRegistrada) -> list[str]:
    datos = version.datos
    evento = version.evento
    if isinstance(datos, DatosAprobado):
        lineas = [
            f"  {version.version}  {evento.fecha_hora_utc}  aprobación por "
            f"{datos.aprobado_por.id} ({evento.id})",
            f"    hash: {datos.hash_protocolo}",
            f"    advertencias justificadas: {len(datos.advertencias)}",
        ]
        lineas += [
            f"      - {a.id_regla} en {a.ubicacion}: {a.justificacion}" for a in datos.advertencias
        ]
        return lineas
    lineas = [
        f"  {version.version}  {evento.fecha_hora_utc}  enmienda {datos.nivel} por "
        f"{datos.enmendado_por.id} ({evento.id})",
        f"    hash: {datos.hash_protocolo}",
        f"    justificación: {datos.justificacion}",
        f"    efecto esperado: {datos.efecto_esperado}",
    ]
    if datos.solo_formato:
        lineas.append("    cambios: ninguno de contenido (solo formato o comentarios)")
    else:
        lineas.append(f"    cambios: {len(datos.cambios)}")
        lineas += [f"      - {_cambio(c.model_dump())}" for c in datos.cambios]
    nuevas = [a for a in datos.advertencias if a.nueva]
    if nuevas:
        lineas.append(f"    advertencias nuevas justificadas: {len(nuevas)}")
        lineas += [f"      - {a.id_regla} en {a.ubicacion}: {a.justificacion}" for a in nuevas]
    return lineas


def _cambio(datos: dict[str, Any]) -> Cambio:
    return Cambio(**datos)


def _texto_decision(registrada: DecisionRegistrada) -> str:
    decision = registrada.datos.decision
    proponente = decision.propuesto_por
    propuesta = f"LLM {proponente.modelo}" if proponente.tipo == "llm" else proponente.id
    detalle = f"decidió {decision.decidido_por.id}; propuso {propuesta}"
    if registrada.confirmacion is not None:
        detalle += f"; confirmada en {registrada.confirmacion.id}"
    if registrada.reemplazada_por is not None:
        detalle += f"; reemplazada por {registrada.reemplazada_por}"
    if decision.reemplaza is not None:
        detalle += f"; reemplaza a {decision.reemplaza}"
    return (
        f"  {decision.id_decision}  {registrada.estado}  {decision.tema}: opción "
        f"{decision.elegida} ({detalle})"
    )


def _version_como_dict(version: VersionRegistrada) -> dict[str, Any]:
    datos: DatosAprobado | DatosEnmendado = version.datos
    return {
        "version": version.version,
        "tipo": "aprobacion" if version.es_aprobacion else "enmienda",
        "evento": version.evento.id,
        "fecha_hora_utc": version.evento.fecha_hora_utc,
        "datos": datos.model_dump(mode="json"),
    }


def _decision_como_dict(registrada: DecisionRegistrada) -> dict[str, Any]:
    confirmacion = registrada.datos_confirmacion
    return {
        "id_decision": registrada.id_decision,
        "estado": registrada.estado,
        "evento_propuesta": registrada.evento.id,
        "fecha_hora_utc": registrada.evento.fecha_hora_utc,
        "evento_confirmacion": registrada.confirmacion.id if registrada.confirmacion else None,
        "confirmado_por": confirmacion.confirmado_por.id if confirmacion else None,
        "reemplazada_por": registrada.reemplazada_por,
        "datos": registrada.datos.model_dump(mode="json"),
    }
