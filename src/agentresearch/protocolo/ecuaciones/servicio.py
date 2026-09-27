"""El comando `protocolo ecuaciones`: generar y, si se pide, escribir `ecuaciones.md`.

ADR-0009, punto 11. Lee los bytes del protocolo una sola vez, y sobre ellos
valida, traduce y calcula el hash que va en la cabecera. No registra un
evento: `ecuaciones.md` se deriva del protocolo de forma determinista.
"""

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agentresearch.protocolo.ciclo_de_vida import leer_estado_registro
from agentresearch.protocolo.ecuaciones import ConjuntoEcuaciones, generar_ecuaciones
from agentresearch.protocolo.ecuaciones.documento import OrigenEcuaciones, texto_ecuaciones
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.validacion import Hallazgo, leer_para_validar, validar_lectura
from agentresearch.trazabilidad import escribir_atomico

_IMPIDEN_TRADUCIR = frozenset({"P-E00", "P-E10", "P-E11"})


class ErrorEcuaciones(Exception):
    """No se pueden generar las ecuaciones; `errores` explica por qué, sin haber escrito nada."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("; ".join(errores))


@dataclass(frozen=True, slots=True)
class ResultadoEcuaciones:
    """Las ecuaciones generadas y, si se escribieron, dónde."""

    conjunto: ConjuntoEcuaciones
    origen: OrigenEcuaciones
    texto: str
    ruta_ecuaciones: str
    escrito: bool
    avisos: list[str]
    """Avisos sobre el protocolo, como un P-E09 cuando no se escribe."""

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta_protocolo": self.origen.ruta_protocolo,
            "version_protocolo": self.origen.version_protocolo,
            "estado": self.origen.estado,
            "hash_protocolo": self.origen.hash_protocolo,
            "ruta_ecuaciones": self.ruta_ecuaciones,
            "escrito": self.escrito,
            "avisos": self.avisos,
            **self.conjunto.como_dict(),
        }


def _impide(hallazgo: Hallazgo, escribir: bool) -> bool:
    if hallazgo.id_regla in _IMPIDEN_TRADUCIR:
        return True
    if hallazgo.id_regla == "P-E09":
        return escribir
    # Un bloque sin términos (o ningún bloque) deja la ecuación sin sentido.
    return hallazgo.id_regla == "P-E04" and (hallazgo.ubicacion or "").startswith("busqueda")


def generar(ruta: Path | str, escribir: bool = False) -> ResultadoEcuaciones:
    """Genera las ecuaciones del protocolo y, con `escribir`, guarda `ecuaciones.md`.

    Lanza `ErrorEcuaciones` si el protocolo no se puede traducir: P-E00, P-E10,
    P-E11 o un bloque sin términos; con `escribir`, también P-E09, porque unas
    ecuaciones de un protocolo con cambios sin registrar no corresponden a
    ninguna versión.
    """
    rutas = RutasProtocolo.desde(ruta)
    lectura = leer_para_validar(rutas.protocolo)
    validacion = validar_lectura(lectura, leer_estado_registro(rutas))
    errores = [str(h) for h in validacion.errores if _impide(h, escribir)]
    documento = lectura.documento
    if errores or documento is None or lectura.hash is None:
        raise ErrorEcuaciones(errores)
    avisos = [str(h) for h in validacion.errores if h.id_regla == "P-E09"]

    protocolo = documento.protocolo
    conjunto = generar_ecuaciones(protocolo)
    origen = OrigenEcuaciones(
        ruta_protocolo=rutas.relativa(rutas.protocolo),
        version_protocolo=protocolo.metadatos.version_protocolo,
        estado=protocolo.estado,
        hash_protocolo=lectura.hash,
        version_agente=version("agentresearch"),
    )
    texto = texto_ecuaciones(conjunto, origen)
    if escribir:
        escribir_atomico(rutas.ecuaciones, texto.encode("utf-8"))
    return ResultadoEcuaciones(
        conjunto=conjunto,
        origen=origen,
        texto=texto,
        ruta_ecuaciones=rutas.relativa(rutas.ecuaciones),
        escrito=escribir,
        avisos=avisos,
    )
