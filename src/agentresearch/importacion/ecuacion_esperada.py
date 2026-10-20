"""Versión del protocolo vigente en la fecha de una búsqueda y su ecuación esperada.

ADR-0010, punto 12. La versión vigente es la última aprobación o enmienda con
fecha anterior o igual a la de la búsqueda. La ecuación esperada de esa versión
se toma de `protocolo/ecuaciones.md` si su cabecera tiene el hash de esa
versión; si no, se genera desde `protocolo/versiones/X.Y.Z.yaml` con el agente
instalado, y se registra de dónde salió. Para una fuente sin traductor, la
esperada es la genérica.

La relación con la ecuación ejecutada es una de tres: `identica`, `desviacion`
(una fuente con traductor cuya ecuación se modificó) o `adaptacion_generica`
(una fuente sin traductor que parte de la genérica).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version as version_del_paquete

from agentresearch.protocolo.archivo import ErrorLecturaProtocolo, decodificar_protocolo
from agentresearch.protocolo.ciclo_de_vida import EstadoRegistro, VersionRegistrada
from agentresearch.protocolo.ecuaciones import TRADUCTORES, generar_ecuaciones
from agentresearch.protocolo.ecuaciones.comun import Ecuacion
from agentresearch.protocolo.ecuaciones.documento import hash_de_ecuaciones
from agentresearch.protocolo.eventos_busqueda import OrigenEcuacionEsperada, RelacionEcuacion
from agentresearch.trazabilidad import hash_texto

_VERSION_AGENTE = re.compile(r"^- Versión del agente: (.+)$", re.MULTILINE)


class ErrorEcuacionEsperada(Exception):
    """No se pudo determinar la ecuación esperada de la fuente en esa versión del protocolo."""


@dataclass(frozen=True, slots=True)
class EcuacionEsperadaCalculada:
    texto: str
    hash: str
    origen: OrigenEcuacionEsperada
    version_agente: str


def version_vigente_en(estado: EstadoRegistro, momento: datetime) -> VersionRegistrada | None:
    """La última aprobación o enmienda registrada en `momento` o antes; `None` si no hay."""
    vigente: VersionRegistrada | None = None
    for version in estado.versiones:
        registrada = datetime.fromisoformat(version.evento.fecha_hora_utc)
        if registrada.astimezone(UTC) <= momento.astimezone(UTC):
            vigente = version
    return vigente


def es_fuente_con_traductor(fuente: str) -> bool:
    return fuente.strip().lower() in TRADUCTORES


def normalizar_espacios(texto: str) -> str:
    """Une los espacios y los saltos de línea para comparar dos ecuaciones."""
    return " ".join(texto.split())


def calcular_ecuacion_esperada(
    estado: EstadoRegistro, version: VersionRegistrada, fuente: str
) -> EcuacionEsperadaCalculada:
    """La ecuación esperada de `fuente` para `version` del protocolo.

    Lanza `ErrorEcuacionEsperada` si la copia de la versión no se puede leer o si
    la ecuación de la fuente quedó bloqueada en esa versión.
    """
    rutas = estado.rutas
    copia = rutas.resolver(version.datos.ruta_version)
    try:
        documento = decodificar_protocolo(copia.read_bytes())
    except (OSError, ErrorLecturaProtocolo) as error:
        raise ErrorEcuacionEsperada(
            f"no se pudo leer la copia {version.datos.ruta_version} de la versión "
            f"{version.version}: {error}"
        ) from None
    conjunto = generar_ecuaciones(documento.protocolo)
    clave = fuente.strip().lower()
    ecuacion = next((e for e in conjunto.ecuaciones if e.fuente == clave), conjunto.ecuaciones[-1])
    if ecuacion.texto is None:
        raise ErrorEcuacionEsperada(
            f"la ecuación de «{fuente}» está bloqueada en la versión {version.version} del "
            "protocolo (hay avisos bloqueantes); no hay ecuación esperada"
        )
    desde_md = _desde_ecuaciones_md(estado, version, ecuacion)
    if desde_md is not None:
        texto, version_agente = desde_md
        return EcuacionEsperadaCalculada(texto, hash_texto(texto), "ecuaciones_md", version_agente)
    return EcuacionEsperadaCalculada(
        ecuacion.texto,
        hash_texto(ecuacion.texto),
        "regenerada",
        version_del_paquete("agentresearch"),
    )


def _desde_ecuaciones_md(
    estado: EstadoRegistro, version: VersionRegistrada, ecuacion: Ecuacion
) -> tuple[str, str] | None:
    ruta = estado.rutas.ecuaciones
    try:
        contenido = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if hash_de_ecuaciones(contenido) != version.hash_protocolo:
        return None
    titulo = f"## {ecuacion.nombre[0].upper()}{ecuacion.nombre[1:]}"
    coincidencia = re.search(
        rf"^{re.escape(titulo)}$(.*?)(?=^## |\Z)", contenido, re.MULTILINE | re.DOTALL
    )
    if coincidencia is None:
        return None
    bloque = re.search(r"```text\n(.*?)\n```", coincidencia.group(1), re.DOTALL)
    if bloque is None:
        return None
    agente = _VERSION_AGENTE.search(contenido)
    return bloque.group(1), agente.group(1) if agente else version_del_paquete("agentresearch")


def clasificar_relacion(fuente: str, esperada: str, ejecutada: str) -> RelacionEcuacion:
    """`identica`, `desviacion` (fuente con traductor) o `adaptacion_generica` (sin traductor)."""
    if normalizar_espacios(esperada) == normalizar_espacios(ejecutada):
        return "identica"
    return "desviacion" if es_fuente_con_traductor(fuente) else "adaptacion_generica"
