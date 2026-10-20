"""`importar historial`: las búsquedas registradas de un estudio (especificación 2c).

Lista cada búsqueda con su fuente, fecha y hora, versión del protocolo, relación
de la ecuación, resultados de la interfaz frente a registros leídos, archivos y
justificaciones; da los totales por fuente y el total general (los registros
identificados en bases de datos del diagrama de flujo, PRISMA-ScR ítem 14; la
deduplicación es del hito 4); comprueba la integridad de `importaciones/` y
informa, como nota y no como error, los originales que faltan en este equipo o
cuyo hash no coincide. No escribe nada.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentresearch.protocolo.ciclo_de_vida import BusquedaRegistrada, leer_estado_registro
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.trazabilidad import hash_bytes


@dataclass(frozen=True, slots=True)
class HistorialImportaciones:
    """El estado de las importaciones de un estudio."""

    busquedas: list[BusquedaRegistrada]
    problemas: list[str]
    """Fallos de integridad (P-E10): el registro o `importaciones/` no son íntegros."""
    notas: list[str] = field(default_factory=list)
    """Originales ausentes o distintos en este equipo; no son errores."""

    @property
    def integro(self) -> bool:
        return not self.problemas

    @property
    def totales_por_fuente(self) -> dict[str, int]:
        totales: dict[str, int] = defaultdict(int)
        for busqueda in self.busquedas:
            totales[busqueda.datos.fuente] += busqueda.datos.registros_leidos
        return dict(totales)

    @property
    def total(self) -> int:
        return sum(self.totales_por_fuente.values())

    def como_dict(self) -> dict[str, Any]:
        return {
            "integro": self.integro,
            "problemas": self.problemas,
            "notas": self.notas,
            "busquedas": [_resumen_busqueda(b) for b in self.busquedas],
            "totales_por_fuente": self.totales_por_fuente,
            "total_registros": self.total,
        }

    def lineas(self) -> list[str]:
        lineas: list[str] = []
        for busqueda in self.busquedas:
            datos = busqueda.datos
            lineas.append(
                f"{datos.id_importacion} ({busqueda.evento.id}): {datos.fuente}, "
                f"{datos.fecha_hora_busqueda} ({datos.fecha_hora_busqueda_utc}), protocolo "
                f"{datos.version_protocolo}"
            )
            lineas.append(f"  ecuación: {datos.relacion_ecuacion}")
            if datos.justificacion_ecuacion:
                lineas.append(f"  justificación de la ecuación: {datos.justificacion_ecuacion}")
            lineas.append(
                f"  registros leídos: {datos.registros_leidos}; resultados de la interfaz: "
                f"{datos.resultados_interfaz}"
            )
            if datos.justificacion_diferencia:
                lineas.append(f"  justificación de la diferencia: {datos.justificacion_diferencia}")
            lineas += [
                f"  archivo: {a.nombre_original} ({a.formato}, {a.registros} registros)"
                for a in datos.archivos
            ]
        if not self.busquedas:
            lineas.append("no hay búsquedas registradas")
        else:
            lineas += [f"total {fuente}: {n}" for fuente, n in self.totales_por_fuente.items()]
            lineas.append(f"total de registros identificados en bases de datos: {self.total}")
        lineas += [f"nota: {nota}" for nota in self.notas]
        if self.problemas:
            lineas += [f"error: {problema}" for problema in self.problemas]
            lineas.append("resultado: las importaciones no son íntegras")
        else:
            lineas.append("resultado: las importaciones son íntegras")
        return lineas


def _resumen_busqueda(busqueda: BusquedaRegistrada) -> dict[str, Any]:
    datos = busqueda.datos
    return {
        "id_importacion": datos.id_importacion,
        "evento": busqueda.evento.id,
        "fuente": datos.fuente,
        "plataforma": datos.plataforma,
        "fecha_hora_busqueda": datos.fecha_hora_busqueda,
        "fecha_hora_busqueda_utc": datos.fecha_hora_busqueda_utc,
        "version_protocolo": datos.version_protocolo,
        "relacion_ecuacion": datos.relacion_ecuacion,
        "justificacion_ecuacion": datos.justificacion_ecuacion,
        "resultados_interfaz": datos.resultados_interfaz,
        "registros_leidos": datos.registros_leidos,
        "justificacion_diferencia": datos.justificacion_diferencia,
        "archivos": [
            {k: getattr(a, k) for k in ("nombre_original", "formato", "hash", "registros")}
            for a in datos.archivos
        ],
    }


def construir_historial_importaciones(estudio: Path | str) -> HistorialImportaciones:
    """Lee el registro del estudio y reúne las búsquedas, la integridad y las notas."""
    rutas = RutasProtocolo.desde(Path(estudio) / "protocolo" / "protocolo.yaml")
    estado = leer_estado_registro(rutas)
    notas: list[str] = []
    if estado.integro:
        for busqueda in estado.busquedas:
            for archivo in busqueda.datos.archivos:
                ruta = rutas.resolver(archivo.copia)
                if not ruta.is_file():
                    notas.append(
                        f"falta en este equipo el original {archivo.copia} "
                        f"({busqueda.datos.id_importacion}); los originales no se versionan: "
                        "restáurelo desde su respaldo"
                    )
                elif hash_bytes(ruta.read_bytes()) != archivo.hash:
                    notas.append(
                        f"el original {archivo.copia} no coincide con el hash registrado "
                        f"({busqueda.datos.id_importacion})"
                    )
    return HistorialImportaciones(
        busquedas=list(estado.busquedas), problemas=list(estado.problemas), notas=notas
    )
