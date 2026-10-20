"""Lector de RIS (especificación 2b, «Formatos»).

Etiquetas de dos caracteres con la forma `XX  - valor`. `TY` abre un registro y
`ER` lo cierra; la línea `ER` puede llevar o no el espacio final. Se toleran las
líneas de cabecera anteriores al primer `TY` (RIS de ACS: `Provider:`,
`Database:`, `Content:`), las líneas vacías y las de continuación (una línea sin
etiqueta dentro de un registro continúa el valor anterior).
"""

import re
from dataclasses import dataclass, field

from agentresearch.importacion.ensamblado import (
    Lectura,
    hallazgo_de_cabecera,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
)
from agentresearch.importacion.entrada import Carga
from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.identidad import hallazgos_de_identidad
from agentresearch.importacion.perfiles import perfil_ris
from agentresearch.importacion.registro_etiquetas import construir_registro

_ETIQUETA = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")


@dataclass
class _Abierto:
    inicio: int
    etiquetas: list[tuple[str, str]] = field(default_factory=list)


def leer_ris(carga: Carga, fuente: str) -> Lectura:
    """Lee un RIS ya decodificado y devuelve sus registros y hallazgos."""
    perfil = perfil_ris(fuente)
    archivo = carga.nombre
    hallazgos: list[Hallazgo] = []
    cabecera: list[tuple[int, str]] = []
    cerrados: list[_Abierto] = []
    abierto: _Abierto | None = None
    hubo_registro = False

    def _sin_cierre(registro: _Abierto) -> None:
        hallazgos.append(
            crear_hallazgo(
                "L-E02",
                archivo,
                "registro sin cierre: falta la etiqueta ER antes del siguiente TY o del fin "
                "del archivo",
                linea=registro.inicio,
            )
        )

    for numero, linea in enumerate(carga.lineas, 1):
        coincidencia = _ETIQUETA.match(linea)
        if coincidencia is not None:
            etiqueta, valor = coincidencia.groups()
            if etiqueta == "TY":
                if abierto is not None:
                    _sin_cierre(abierto)
                abierto = _Abierto(numero, [("TY", valor)])
                hubo_registro = True
            elif etiqueta == "ER":
                if abierto is None:
                    hallazgos.append(
                        crear_hallazgo(
                            "L-E02",
                            archivo,
                            "etiqueta ER fuera de un registro",
                            linea=numero,
                        )
                    )
                else:
                    cerrados.append(abierto)
                    abierto = None
            elif abierto is None:
                hallazgos.append(
                    crear_hallazgo(
                        "L-E02",
                        archivo,
                        f"etiqueta {etiqueta} fuera de un registro",
                        linea=numero,
                    )
                )
            else:
                abierto.etiquetas.append((etiqueta, valor))
        elif not linea.strip():
            continue
        elif abierto is not None:
            # Continuación del valor anterior.
            ultima, valor_anterior = abierto.etiquetas[-1]
            abierto.etiquetas[-1] = (ultima, f"{valor_anterior} {linea.strip()}")
        elif not hubo_registro:
            cabecera.append((numero, linea))
        else:
            hallazgos.append(
                crear_hallazgo("L-E02", archivo, "línea fuera de un registro", linea=numero)
            )
    if abierto is not None:
        _sin_cierre(abierto)

    registros = tuple(
        construir_registro(fuente, "ris", archivo, r.inicio, r.etiquetas, perfil) for r in cerrados
    )
    lineas_cabecera, aviso = hallazgo_de_cabecera(archivo, cabecera)
    if aviso is not None:
        hallazgos.append(aviso)
    vistos = {etiqueta for r in cerrados for etiqueta, _valor in r.etiquetas}
    origen = {
        "titulo": perfil.escalares["titulo"],
        "autores": perfil.listas["autores"],
        "anio": perfil.anio,
        "doi": perfil.escalares["doi"],
        "resumen": perfil.escalares["resumen"],
    }
    hallazgos.extend(hallazgos_de_campos_esperados(archivo, origen, vistos))
    hallazgos.extend(hallazgos_de_calidad(archivo, registros))
    hallazgos.extend(hallazgos_de_identidad(archivo, registros))
    return Lectura(
        registros=registros,
        hallazgos=tuple(hallazgos),
        lineas_cabecera=lineas_cabecera,
    )
