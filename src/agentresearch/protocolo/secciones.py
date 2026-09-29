"""Escritura de una sección del protocolo desde un fragmento YAML (ADR-0007).

`/protocolo` construye el protocolo sección por sección, y las reglas de
permisos del estudio impiden que Claude Code edite `protocolo/` con sus
herramientas de archivos. Esta es la vía para escribir: se lee un fragmento
con una sola clave de primer nivel, se valida el protocolo completo contra el
esquema antes de escribir y se escribe de forma atómica, conservando los
comentarios y el estilo del resto del archivo.

Funciona igual con el protocolo en borrador que vigente. Con el protocolo
vigente es la forma de preparar una enmienda: después de escribir, P-E09
avisa del cambio sin registrar hasta que el investigador registra la
enmienda en su terminal.

No escribe `version_esquema`, `estado` ni `metadatos.version_protocolo`: el
paquete los asigna al aprobar y al enmendar.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentresearch.protocolo.aprobacion import ErrorCicloDeVida
from agentresearch.protocolo.archivo import (
    ErrorLecturaProtocolo,
    a_python,
    analizar_fragmento,
    decodificar_protocolo,
    describir_error_de_esquema,
    leer_bytes_protocolo,
    reemplazar_seccion,
    texto_protocolo,
)
from agentresearch.protocolo.ciclo_de_vida import leer_estado_registro
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.modelo import Protocolo
from agentresearch.protocolo.validacion import ResultadoValidacion, validar_archivo
from agentresearch.trazabilidad import escribir_atomico, hash_bytes

SECCIONES = (
    "metadatos",
    "justificacion",
    "objetivos",
    "pregunta_general",
    "preguntas",
    "marco",
    "fuentes",
    "estrategias",
    "busqueda",
    "criterios",
    "seleccion",
    "extraccion",
    "calidad",
    "analisis",
)
"""Secciones que se pueden escribir, en el orden en que las recorre `/protocolo`."""


@dataclass(frozen=True, slots=True)
class ResultadoEscritura:
    """Resultado de escribir una sección, con la validación del archivo resultante."""

    ruta_protocolo: str
    seccion: str
    cambio: bool
    """Si el archivo cambió; escribir una sección idéntica no lo toca."""
    hash_anterior: str
    hash_protocolo: str
    estado: str
    version_protocolo: str
    validacion: ResultadoValidacion

    @property
    def pendiente_de_enmienda(self) -> bool:
        """El protocolo está vigente y cambió: queda P-E09 hasta registrar la enmienda."""
        return self.estado == "vigente" and any(
            hallazgo.id_regla == "P-E09" for hallazgo in self.validacion.errores
        )

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta_protocolo": self.ruta_protocolo,
            "seccion": self.seccion,
            "cambio": self.cambio,
            "hash_anterior": self.hash_anterior,
            "hash_protocolo": self.hash_protocolo,
            "estado": self.estado,
            "version_protocolo": self.version_protocolo,
            "pendiente_de_enmienda": self.pendiente_de_enmienda,
            "validacion": self.validacion.como_dict(),
        }


def escribir_seccion(ruta: Path | str, seccion: str, archivo: Path | str) -> ResultadoEscritura:
    """Reemplaza la sección `seccion` del protocolo por la del fragmento `archivo`.

    Lanza `ErrorCicloDeVida`, sin escribir nada, si la sección no se puede
    escribir, si el fragmento o el protocolo no se pueden leer, si el
    resultado no cumple el esquema, si el registro de eventos no es íntegro
    (P-E10) o si hay una operación interrumpida que recuperar.
    """
    rutas = RutasProtocolo.desde(ruta)
    protocolo_rel = rutas.relativa(rutas.protocolo)
    if seccion not in SECCIONES:
        raise ErrorCicloDeVida(
            [
                f"la sección «{seccion}» no se escribe con este comando; se admiten: "
                f"{', '.join(SECCIONES)}. El estado y las versiones los asigna el paquete"
            ]
        )
    valor = _leer_fragmento(Path(archivo), seccion)

    registro = leer_estado_registro(rutas)
    if not registro.integro:
        raise ErrorCicloDeVida(
            [
                f"el registro de eventos no es íntegro (P-E10): {problema}"
                for problema in registro.problemas
            ]
        )
    try:
        contenido = leer_bytes_protocolo(rutas.protocolo)
        documento = decodificar_protocolo(contenido)
    except ErrorLecturaProtocolo as error:
        raise ErrorCicloDeVida(
            [f"no se pudo leer {protocolo_rel} (P-E00): {p.mensaje}" for p in error.problemas]
            + ["corrija el archivo a mano antes de escribir una sección"]
        ) from None
    hash_anterior = hash_bytes(contenido)
    ultima = registro.ultima_version
    if (
        ultima is not None
        and hash_anterior == ultima.datos.hash_revisado
        and hash_anterior != ultima.hash_protocolo
    ):
        raise ErrorCicloDeVida(
            [
                f"la operación de la versión {ultima.version} ({ultima.evento.id}) se "
                f"interrumpió antes de actualizar {protocolo_rel}: copie "
                f"{ultima.datos.ruta_version} sobre {protocolo_rel} antes de escribir"
            ]
        )

    protocolo = _validar_con_seccion(documento.protocolo, documento.datos, seccion, valor)
    reemplazar_seccion(documento, seccion, valor, protocolo)
    contenido_nuevo = texto_protocolo(documento).encode("utf-8")
    # Comprobación interna: el texto escrito se lee como el modelo validado.
    if decodificar_protocolo(contenido_nuevo).protocolo.model_dump() != protocolo.model_dump():
        raise ErrorCicloDeVida(["error interno: el texto nuevo del protocolo no es el esperado"])

    cambio = contenido_nuevo != contenido
    if cambio:
        if rutas.protocolo.read_bytes() != contenido:
            raise ErrorCicloDeVida(
                [f"{protocolo_rel} cambió mientras se escribía; vuelva a ejecutar el comando"]
            )
        escribir_atomico(rutas.protocolo, contenido_nuevo)
    return ResultadoEscritura(
        ruta_protocolo=protocolo_rel,
        seccion=seccion,
        cambio=cambio,
        hash_anterior=hash_anterior,
        hash_protocolo=hash_bytes(contenido_nuevo),
        estado=protocolo.estado,
        version_protocolo=protocolo.metadatos.version_protocolo,
        validacion=validar_archivo(rutas.protocolo),
    )


def _leer_fragmento(archivo: Path, seccion: str) -> Any:
    """Lee el fragmento y devuelve el valor de su única clave, que debe ser `seccion`."""
    try:
        contenido = archivo.read_bytes()
    except OSError as error:
        raise ErrorCicloDeVida(
            [f"no se pudo leer el fragmento {archivo}: {error.strerror}"]
        ) from None
    try:
        datos = analizar_fragmento(contenido)
    except ErrorLecturaProtocolo as error:
        raise ErrorCicloDeVida(
            [f"fragmento {archivo}: {problema.mensaje}" for problema in error.problemas]
        ) from None
    claves = [str(clave) for clave in datos]
    if claves != [seccion]:
        raise ErrorCicloDeVida(
            [
                f"el fragmento {archivo} debe tener una sola clave de primer nivel, «{seccion}», "
                f"con el contenido completo de la sección; tiene: {', '.join(claves)}"
            ]
        )
    return datos[seccion]


def _validar_con_seccion(actual: Protocolo, datos: Any, seccion: str, valor: Any) -> Protocolo:
    """Valida contra el esquema el protocolo completo con la sección nueva."""
    candidato = a_python(datos)
    candidato[seccion] = a_python(valor)
    try:
        protocolo = Protocolo.model_validate(candidato)
    except ValidationError as error:
        raise ErrorCicloDeVida(
            [
                f"la sección no cumple el esquema (P-E00): {describir_error_de_esquema(detalle)}"
                for detalle in error.errors()
            ]
        ) from None
    anterior = actual.metadatos.version_protocolo
    if protocolo.metadatos.version_protocolo != anterior:
        raise ErrorCicloDeVida(
            [
                f"metadatos.version_protocolo no se escribe con este comando (es {anterior}): "
                "el paquete la asigna al aprobar y al enmendar"
            ]
        )
    return protocolo
