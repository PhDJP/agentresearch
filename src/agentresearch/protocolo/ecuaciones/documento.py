"""El archivo `protocolo/ecuaciones.md` (ADR-0009, puntos 12 a 15).

Es determinista: no lleva marca de tiempo, así que el mismo protocolo con la
misma versión del agente produce los mismos bytes. Su cabecera guarda el
hash del protocolo de origen, que `validar` e `historial` comparan con el
actual para avisar de unas ecuaciones desactualizadas.
"""

import re
from dataclasses import dataclass
from typing import Any

from agentresearch.protocolo.ecuaciones import ConjuntoEcuaciones
from agentresearch.protocolo.ecuaciones.comun import Ecuacion
from agentresearch.protocolo.estudio import RutasProtocolo

_LINEA_HASH = re.compile(r"^- Hash del protocolo: (sha256:[0-9a-f]{64})$", re.MULTILINE)

_PASOS_MANUALES = {
    "scopus": (
        "Abra la búsqueda avanzada de documentos de Scopus y pegue la ecuación completa.",
        "Exporte todos los resultados en CSV, con todos los campos disponibles (incluidos el "
        "resumen y las palabras clave). Es el formato que importará el hito 2 (ADR-0003).",
    ),
    "wos": (
        "Abra la búsqueda avanzada de la Web of Science Core Collection y pegue la ecuación "
        "completa en el cuadro que admite etiquetas de campo (TS=).",
        "Exporte todos los resultados como texto plano con etiquetas (.txt), con el registro "
        "completo. Es el formato que importará el hito 2 (ADR-0003).",
    ),
}


@dataclass(frozen=True, slots=True)
class OrigenEcuaciones:
    """De qué protocolo salen las ecuaciones."""

    ruta_protocolo: str
    version_protocolo: str
    estado: str
    hash_protocolo: str
    version_agente: str


def texto_ecuaciones(conjunto: ConjuntoEcuaciones, origen: OrigenEcuaciones) -> str:
    """El contenido de `ecuaciones.md`, en Markdown con fin de línea LF."""
    bloqueadas = conjunto.bloqueadas
    lineas = [
        "# Ecuaciones de búsqueda",
        "",
        "Generado por agentresearch a partir del protocolo; no lo edite a mano. Regenérelo con "
        "`agentresearch protocolo ecuaciones --escribir` después de aprobar o enmendar el "
        "protocolo (ADR-0009).",
        "",
        f"- Protocolo: {origen.ruta_protocolo}",
        f"- Versión del protocolo: {origen.version_protocolo} ({origen.estado})",
        f"- Hash del protocolo: {origen.hash_protocolo}",
        f"- Versión del agente: {origen.version_agente}",
        f"- Fuentes bloqueadas: {', '.join(bloqueadas) if bloqueadas else 'ninguna'}",
        "",
        "## Límites del protocolo",
        "",
    ]
    lineas += [f"- {linea}" for linea in conjunto.ecuaciones[-1].limites.descripcion]
    for ecuacion in conjunto.ecuaciones:
        lineas += ["", *_seccion(ecuacion)]
    if conjunto.sin_traductor:
        lineas += ["", "## Fuentes sin traductor", ""]
        lineas += [
            f"- {fuente}: no tiene traductor propio; use la ecuación genérica y adáptela a la "
            "sintaxis de la base."
            for fuente in conjunto.sin_traductor
        ]
    return "\n".join(lineas) + "\n"


def _seccion(ecuacion: Ecuacion) -> list[str]:
    lineas = [f"## {ecuacion.nombre[0].upper()}{ecuacion.nombre[1:]}", ""]
    lineas.append(f"- Campos: {ecuacion.campos}")
    lineas.append(f"- Límites: {_texto_limites(ecuacion)}")
    if ecuacion.longitud is not None:
        maximo = (
            f"de un máximo de {ecuacion.maximo}"
            if ecuacion.maximo is not None
            else "sin máximo documentado"
        )
        lineas.append(f"- Longitud: {ecuacion.longitud} {ecuacion.descripcion_longitud}, {maximo}")
    if ecuacion.documentacion:
        lineas.append(
            "- Sintaxis verificada en: "
            + "; ".join(f"[{d.titulo}]({d.url}) ({d.verificada})" for d in ecuacion.documentacion)
        )
    lineas.append("")
    if ecuacion.texto is None:
        lineas.append(
            "**Sin ecuación:** la fuente quedó bloqueada. Resuelva los avisos bloqueantes y "
            "vuelva a generar las ecuaciones."
        )
    else:
        lineas += ["```text", ecuacion.texto, "```"]
    if ecuacion.avisos:
        lineas += ["", "Avisos:", ""]
        lineas += [f"- {aviso}" for aviso in ecuacion.avisos]
    if ecuacion.manual and ecuacion.texto is not None:
        lineas += ["", *_pasos(ecuacion)]
    return lineas


def _texto_limites(ecuacion: Ecuacion) -> str:
    limites = ecuacion.limites
    partes = []
    if limites.sufijo:
        partes.append(f"en la ecuación ({limites.sufijo.removeprefix(' AND ')})")
    if limites.instrucciones:
        partes.append("en la interfaz (ver los pasos)" if ecuacion.manual else "en la interfaz")
    if limites.pendientes_del_conector:
        partes.append(f"se aplicarán con el conector de {ecuacion.nombre} (hito 3)")
    if not partes:
        if ecuacion.fuente == "generica":
            return "aplíquelos con los filtros de la base (ver «Límites del protocolo»)"
        return "no hay límites que aplicar"
    return "; ".join(partes)


def _pasos(ecuacion: Ecuacion) -> list[str]:
    pegar, exportar = _PASOS_MANUALES[ecuacion.fuente]
    instrucciones = ecuacion.limites.instrucciones
    if instrucciones:
        filtros = ["2. Aplique en la interfaz estos filtros:"]
        filtros += [f"   - {instruccion}." for instruccion in instrucciones]
    else:
        filtros = [
            "2. No hace falta aplicar filtros en la interfaz: los límites están en la ecuación."
        ]
    return [
        "Pasos para ejecutarla:",
        "",
        f"1. {pegar}",
        *filtros,
        f"3. {exportar}",
        "4. Anote la fecha y la hora de la búsqueda y el número de resultados que mostró la "
        "interfaz: el hito 2 los pedirá al importar la exportación (PRISMA-ScR, ítem 7).",
    ]


def hash_de_ecuaciones(texto: str) -> str | None:
    """El hash del protocolo de origen que guarda la cabecera de `ecuaciones.md`."""
    coincidencia = _LINEA_HASH.search(texto)
    return coincidencia.group(1) if coincidencia else None


@dataclass(frozen=True, slots=True)
class EstadoEcuaciones:
    """Si `ecuaciones.md` corresponde al protocolo actual (ADR-0009, punto 14)."""

    ruta: str
    existe: bool
    hash_protocolo: str | None
    """El hash de origen que guarda la cabecera, si se pudo leer."""
    desactualizadas: bool

    def nota(self) -> str | None:
        """Aviso de `validar` e `historial` si las ecuaciones están desactualizadas."""
        if not self.desactualizadas:
            return None
        if self.hash_protocolo is None:
            detalle = "su cabecera no tiene el hash del protocolo de origen"
        else:
            detalle = f"se generaron para el protocolo con hash {self.hash_protocolo}"
        return (
            f"ecuaciones desactualizadas: {self.ruta} no corresponde al protocolo actual "
            f"({detalle}). Regenérelas con `agentresearch protocolo ecuaciones --escribir`"
        )

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta": self.ruta,
            "existe": self.existe,
            "hash_protocolo": self.hash_protocolo,
            "desactualizadas": self.desactualizadas,
        }


def estado_ecuaciones(rutas: RutasProtocolo, hash_actual: str | None) -> EstadoEcuaciones:
    """Compara el hash de origen de `ecuaciones.md` con el del protocolo actual.

    Sin `ecuaciones.md`, o sin hash actual (protocolo ilegible), no hay nota.
    """
    ruta = rutas.relativa(rutas.ecuaciones)
    if not rutas.ecuaciones.is_file():
        return EstadoEcuaciones(ruta, False, None, False)
    try:
        registrado = hash_de_ecuaciones(rutas.ecuaciones.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        registrado = None
    desactualizadas = hash_actual is not None and registrado != hash_actual
    return EstadoEcuaciones(ruta, True, registrado, desactualizadas)
