"""Estado del ciclo de vida del protocolo, leído del directorio del estudio.

Lee el registro de eventos (`protocolo/eventos.jsonl`), su anclaje y las
copias de versión, y evalúa las dos reglas que dependen de ellos y no solo
del modelo (ADR-0008, puntos 22 a 24):

- **P-E10:** el registro está íntegro, cumple su anclaje, sus eventos
  cumplen su esquema y forman una secuencia coherente, y las copias de
  versión existen y coinciden con su hash.
- **P-E09:** el protocolo no cambió desde el último hash registrado sin una
  enmienda, y no está vigente sin una aprobación registrada.
"""

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from agentresearch.protocolo.entradas import ErrorEntrada, cargar_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_APROBADO,
    TIPO_DECISION_CONFIRMADA,
    TIPO_DECISION_PROPUESTA,
    TIPO_ENMENDADO,
    ArchivoAnclaje,
    DatosAprobado,
    DatosDecisionConfirmada,
    DatosDecisionPropuesta,
    DatosEnmendado,
    Nivel,
)
from agentresearch.trazabilidad import (
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    escribir_atomico,
    hash_bytes,
)

VERSION_APROBADA = "1.0.0"
"""Versión que fija la aprobación (ADR-0008, punto 5)."""

EstadoDecision = Literal["pendiente", "confirmada", "reemplazada"]


def siguiente_version(version: str, nivel: Nivel) -> str:
    """Versión que sigue a `version` según el nivel de la enmienda (ADR-0008, punto 6)."""
    mayor, menor, parche = (int(parte) for parte in version.split("."))
    if nivel == "mayor":
        return f"{mayor + 1}.0.0"
    if nivel == "menor":
        return f"{mayor}.{menor + 1}.0"
    return f"{mayor}.{menor}.{parche + 1}"


@dataclass(frozen=True, slots=True)
class VersionRegistrada:
    """Una versión del protocolo registrada por una aprobación o una enmienda."""

    evento: EventoRegistro
    datos: DatosAprobado | DatosEnmendado

    @property
    def es_aprobacion(self) -> bool:
        return isinstance(self.datos, DatosAprobado)

    @property
    def version(self) -> str:
        return self.datos.version_protocolo

    @property
    def hash_protocolo(self) -> str:
        return self.datos.hash_protocolo


@dataclass(slots=True)
class DecisionRegistrada:
    """Una decisión propuesta, con su confirmación y su reemplazo, si los hay."""

    evento: EventoRegistro
    datos: DatosDecisionPropuesta
    confirmacion: EventoRegistro | None = None
    datos_confirmacion: DatosDecisionConfirmada | None = None
    reemplazada_por: str | None = None

    @property
    def id_decision(self) -> str:
        return self.datos.decision.id_decision

    @property
    def estado(self) -> EstadoDecision:
        if self.reemplazada_por is not None:
            return "reemplazada"
        if self.confirmacion is not None:
            return "confirmada"
        return "pendiente"


@dataclass(slots=True)
class EstadoRegistro:
    """Lo que el directorio del estudio dice sobre el ciclo de vida del protocolo."""

    rutas: RutasProtocolo
    existe_registro: bool = False
    existe_anclaje: bool = False
    existe_versiones: bool = False
    eventos: list[EventoRegistro] = field(default_factory=list)
    anclaje_actual: Anclaje | None = None
    """Anclaje del registro tal como está, si su cadena está íntegra."""
    anclaje_guardado: Anclaje | None = None
    """Anclaje leído de `anclaje.json`, si existe y es válido."""
    anclaje_cumplido: bool | None = None
    """Si el registro cumple el anclaje guardado (como prefijo); `None` si no hay anclaje válido."""
    versiones: list[VersionRegistrada] = field(default_factory=list)
    decisiones: dict[str, DecisionRegistrada] = field(default_factory=dict)
    problemas: list[str] = field(default_factory=list)
    """Mensajes de la regla P-E10; vacío si el registro es íntegro y coherente."""

    @property
    def integro(self) -> bool:
        return not self.problemas

    @property
    def ultima_version(self) -> VersionRegistrada | None:
        return self.versiones[-1] if self.versiones else None

    @property
    def pendientes(self) -> list[DecisionRegistrada]:
        return [d for d in self.decisiones.values() if d.estado == "pendiente"]


def leer_estado_registro(rutas: RutasProtocolo) -> EstadoRegistro:
    """Lee el registro, el anclaje y las copias de versión, y reúne los problemas de P-E10."""
    estado = EstadoRegistro(
        rutas=rutas,
        existe_registro=rutas.eventos.is_file(),
        existe_anclaje=rutas.anclaje.is_file(),
        existe_versiones=rutas.versiones.exists(),
    )
    registro_rel = rutas.relativa(rutas.eventos)

    if not estado.existe_registro:
        if estado.existe_anclaje or estado.existe_versiones:
            presentes = [
                rutas.relativa(ruta)
                for ruta, existe in (
                    (rutas.anclaje, estado.existe_anclaje),
                    (rutas.versiones, estado.existe_versiones),
                )
                if existe
            ]
            estado.problemas.append(
                f"falta {registro_rel}, pero existe {' y '.join(presentes)}: el registro pudo "
                "haberse eliminado. Si una primera aprobación se interrumpió antes de registrar "
                f"su evento, compruebe con Git que {registro_rel} nunca existió y elimine la "
                "copia huérfana"
            )
        return estado

    registro = RegistroEncadenado(rutas.eventos)
    verificacion = registro.verificar()
    if not verificacion.valido:
        linea = (
            f" en la línea {verificacion.numero_linea_error}"
            if verificacion.numero_linea_error is not None
            else ""
        )
        estado.problemas.append(
            f"la cadena de {registro_rel} está rota{linea}: {verificacion.mensaje}"
        )
        return estado

    estado.eventos = registro.leer()
    estado.anclaje_actual = registro.anclaje()
    if estado.existe_anclaje:
        _verificar_anclaje_guardado(estado, registro)
    _interpretar_eventos(estado)
    _verificar_copias(estado)
    return estado


def _verificar_anclaje_guardado(estado: EstadoRegistro, registro: RegistroEncadenado) -> None:
    rutas = estado.rutas
    anclaje_rel = rutas.relativa(rutas.anclaje)
    try:
        archivo = validar_modelo(
            ArchivoAnclaje, cargar_json(rutas.anclaje.read_bytes(), anclaje_rel), anclaje_rel
        )
        anclaje = Anclaje(archivo.numero_eventos, archivo.hash_ultimo)
    except ErrorEntrada as error:
        estado.problemas.extend(f"{anclaje_rel} no es válido: {e}" for e in error.errores)
        return
    except ValueError as error:
        estado.problemas.append(f"{anclaje_rel} no es válido: {error}")
        return
    if archivo.registro != rutas.relativa(rutas.eventos):
        estado.problemas.append(
            f"{anclaje_rel} ancla {archivo.registro!r}, no {rutas.relativa(rutas.eventos)!r}"
        )
        return
    estado.anclaje_guardado = anclaje
    resultado = registro.verificar(anclaje)
    estado.anclaje_cumplido = resultado.valido
    if not resultado.valido:
        estado.problemas.append(
            f"{rutas.relativa(rutas.eventos)} no cumple {anclaje_rel}: {resultado.mensaje}"
        )


def _validar_datos[M: BaseModel](
    estado: EstadoRegistro, evento: EventoRegistro, modelo: type[M]
) -> M | None:
    try:
        return validar_modelo(modelo, evento.datos, f"{evento.id} ({evento.tipo})")
    except ErrorEntrada as error:
        estado.problemas.extend(
            f"el evento no cumple su esquema: {mensaje}" for mensaje in error.errores
        )
        return None


def _interpretar_eventos(estado: EstadoRegistro) -> None:
    """Construye versiones y decisiones, y comprueba que la secuencia sea coherente."""
    propuestas_por_evento: dict[str, DecisionRegistrada] = {}
    for evento in estado.eventos:
        if evento.tipo == TIPO_APROBADO:
            aprobado = _validar_datos(estado, evento, DatosAprobado)
            if aprobado is not None:
                _registrar_aprobacion(estado, evento, aprobado)
        elif evento.tipo == TIPO_ENMENDADO:
            enmendado = _validar_datos(estado, evento, DatosEnmendado)
            if enmendado is not None:
                _registrar_enmienda(estado, evento, enmendado)
        elif evento.tipo == TIPO_DECISION_PROPUESTA:
            propuesta = _validar_datos(estado, evento, DatosDecisionPropuesta)
            if propuesta is not None:
                _registrar_propuesta(estado, evento, propuesta, propuestas_por_evento)
        elif evento.tipo == TIPO_DECISION_CONFIRMADA:
            confirmada = _validar_datos(estado, evento, DatosDecisionConfirmada)
            if confirmada is not None:
                _registrar_confirmacion(estado, evento, confirmada, propuestas_por_evento)
        # Otros tipos (p. ej. el evento inicial del estudio) no afectan el ciclo de vida.


def _registrar_aprobacion(
    estado: EstadoRegistro, evento: EventoRegistro, datos: DatosAprobado
) -> None:
    if estado.versiones:
        estado.problemas.append(
            f"{evento.id} registra una segunda aprobación; un protocolo se aprueba una sola vez"
        )
        return
    if datos.version_protocolo != VERSION_APROBADA:
        estado.problemas.append(
            f"{evento.id} aprueba la versión {datos.version_protocolo}; la aprobación fija "
            f"la versión {VERSION_APROBADA}"
        )
        return
    estado.versiones.append(VersionRegistrada(evento, datos))


def _registrar_enmienda(
    estado: EstadoRegistro, evento: EventoRegistro, datos: DatosEnmendado
) -> None:
    anterior = estado.ultima_version
    if anterior is None:
        estado.problemas.append(f"{evento.id} registra una enmienda sin aprobación previa")
        return
    esperada = siguiente_version(anterior.version, datos.nivel)
    if datos.version_anterior != anterior.version or datos.version_protocolo != esperada:
        estado.problemas.append(
            f"{evento.id} enmienda de {datos.version_anterior} a {datos.version_protocolo}, "
            f"pero la versión registrada es {anterior.version} y el nivel "
            f"{datos.nivel} lleva a {esperada}"
        )
        return
    if datos.hash_protocolo_anterior != anterior.hash_protocolo:
        estado.problemas.append(
            f"{evento.id}: hash_protocolo_anterior no coincide con el hash de la versión "
            f"{anterior.version} registrada en {anterior.evento.id}"
        )
        return
    estado.versiones.append(VersionRegistrada(evento, datos))


def _registrar_propuesta(
    estado: EstadoRegistro,
    evento: EventoRegistro,
    datos: DatosDecisionPropuesta,
    propuestas_por_evento: dict[str, DecisionRegistrada],
) -> None:
    decision = datos.decision
    if decision.id_decision in estado.decisiones:
        estado.problemas.append(
            f"{evento.id} vuelve a registrar la decisión {decision.id_decision}"
        )
        return
    if decision.reemplaza is not None:
        reemplazada = estado.decisiones.get(decision.reemplaza)
        if reemplazada is None or reemplazada.reemplazada_por is not None:
            estado.problemas.append(
                f"{evento.id}: la decisión {decision.id_decision} reemplaza a "
                f"{decision.reemplaza}, que no existe o ya fue reemplazada"
            )
            return
        reemplazada.reemplazada_por = decision.id_decision
    registrada = DecisionRegistrada(evento, datos)
    estado.decisiones[decision.id_decision] = registrada
    propuestas_por_evento[evento.id] = registrada


def _registrar_confirmacion(
    estado: EstadoRegistro,
    evento: EventoRegistro,
    datos: DatosDecisionConfirmada,
    propuestas_por_evento: dict[str, DecisionRegistrada],
) -> None:
    propuesta = propuestas_por_evento.get(datos.evento_propuesta)
    if (
        propuesta is None
        or propuesta.id_decision != datos.id_decision
        or propuesta.evento.hash != datos.hash_evento_propuesta
    ):
        estado.problemas.append(
            f"{evento.id} confirma la decisión {datos.id_decision}, pero no corresponde a "
            f"la propuesta registrada en {datos.evento_propuesta}"
        )
        return
    if propuesta.estado != "pendiente":
        estado.problemas.append(
            f"{evento.id} confirma la decisión {datos.id_decision}, que no estaba pendiente "
            f"({propuesta.estado})"
        )
        return
    propuesta.confirmacion = evento
    propuesta.datos_confirmacion = datos


def _verificar_copias(estado: EstadoRegistro) -> None:
    for version in estado.versiones:
        ruta_rel = version.datos.ruta_version
        esperada = estado.rutas.relativa(estado.rutas.copia_de_version(version.version))
        ruta = estado.rutas.resolver(ruta_rel)
        if ruta_rel != esperada:
            estado.problemas.append(
                f"{version.evento.id} guarda la copia de la versión {version.version} en "
                f"{ruta_rel}, no en {esperada}"
            )
        elif not ruta.is_file():
            estado.problemas.append(
                f"falta la copia {ruta_rel} de la versión {version.version} "
                f"registrada en {version.evento.id}"
            )
        elif hash_bytes(ruta.read_bytes()) != version.hash_protocolo:
            estado.problemas.append(
                f"la copia {ruta_rel} no coincide con el hash de la versión {version.version} "
                f"registrada en {version.evento.id}"
            )


# --- Regla P-E09 -----------------------------------------------------------------


def problemas_p_e09(
    estado: EstadoRegistro, hash_actual: str | None, estado_protocolo: str | None
) -> list[str]:
    """Mensajes de P-E09: cambio sin enmienda registrada (ADR-0008, punto 23).

    No se evalúa si hay problemas de P-E10, porque la referencia no es fiable.
    `hash_actual` es `None` si el archivo no se pudo leer, y `estado_protocolo`
    es `None` si el protocolo no se pudo cargar (P-E00).
    """
    if not estado.integro:
        return []
    rutas = estado.rutas
    protocolo_rel = rutas.relativa(rutas.protocolo)
    ultima = estado.ultima_version
    if ultima is None:
        if estado_protocolo != "vigente":
            return []
        motivo = (
            f"{rutas.relativa(rutas.eventos)} no contiene ninguna aprobación"
            if estado.existe_registro
            else f"no existe {rutas.relativa(rutas.eventos)}"
        )
        return [
            f"el protocolo está vigente, pero {motivo}; un protocolo solo pasa a vigente con "
            "`agentresearch protocolo aprobar`"
        ]
    if hash_actual is None or hash_actual == ultima.hash_protocolo:
        return []
    operacion = "aprobación" if ultima.es_aprobacion else "enmienda"
    if hash_actual == ultima.datos.hash_revisado:
        return [
            f"la {operacion} de la versión {ultima.version} registrada en {ultima.evento.id} "
            f"se interrumpió antes de actualizar {protocolo_rel}: para completarla, copie "
            f"{ultima.datos.ruta_version} sobre {protocolo_rel}"
        ]
    mensaje = (
        f"{protocolo_rel} cambió desde la versión {ultima.version} registrada en "
        f"{ultima.evento.id}; registre el cambio con `agentresearch protocolo enmendar`"
    )
    if estado_protocolo == "borrador":
        mensaje += (
            ". El archivo dice «borrador», pero el registro contiene una aprobación, y un "
            "protocolo aprobado no vuelve a borrador"
        )
    return [mensaje]


# --- Anclaje -----------------------------------------------------------------------


def texto_anclaje(rutas: RutasProtocolo, anclaje: Anclaje) -> bytes:
    """Contenido de `anclaje.json`: claves ordenadas, sangría de 2, UTF-8 y LF."""
    datos = {
        "hash_ultimo": anclaje.hash_ultimo,
        "numero_eventos": anclaje.numero_eventos,
        "registro": rutas.relativa(rutas.eventos),
    }
    return (json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def escribir_anclaje(rutas: RutasProtocolo) -> Anclaje:
    """Guarda en `anclaje.json` el anclaje actual del registro y lo devuelve."""
    anclaje = RegistroEncadenado(rutas.eventos).anclaje()
    escribir_atomico(rutas.anclaje, texto_anclaje(rutas, anclaje))
    return anclaje
