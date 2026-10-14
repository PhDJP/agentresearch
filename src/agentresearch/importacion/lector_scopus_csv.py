"""Lector del CSV de Scopus (especificación 2b, «Formatos»).

Las columnas se leen por **nombre**, nunca por posición. Una fila con más o menos
columnas que el encabezado es L-E02 y se omite; una celda que supera el límite de
campo es L-E02 y detiene la lectura del archivo en esa fila (ver `motor_csv`).
"""

from agentresearch.importacion.ensamblado import (
    Lectura,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
)
from agentresearch.importacion.entrada import Carga
from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.identidad import hallazgos_de_identidad
from agentresearch.importacion.motor_csv import LIMITE_CAMPO, leer_tabla
from agentresearch.importacion.perfiles import (
    COLUMNAS_OBLIGATORIAS_SCOPUS_CSV,
    SCOPUS_CSV,
)
from agentresearch.importacion.registro_etiquetas import construir_registro
from agentresearch.registros import RegistroNormalizado


def leer_scopus_csv(carga: Carga, fuente: str) -> Lectura:
    """Lee un CSV de Scopus ya decodificado."""
    archivo = carga.nombre
    perfil = SCOPUS_CSV
    tabla = leer_tabla(carga.texto or "")
    hallazgos: list[Hallazgo] = []
    registros: list[RegistroNormalizado] = []

    encabezado = tabla.encabezado
    if encabezado is None:
        if tabla.detenido_en_fila is None:
            hallazgos.append(
                crear_hallazgo("L-E02", archivo, "el archivo está vacío: falta el encabezado")
            )
        else:
            hallazgos.append(
                crear_hallazgo(
                    "L-E02",
                    archivo,
                    f"una celda del encabezado supera el límite de campo ({LIMITE_CAMPO} "
                    "caracteres); se detiene la lectura",
                    linea=tabla.detenido_en_linea,
                    fila=tabla.detenido_en_fila,
                )
            )
        return Lectura(
            registros=(),
            hallazgos=tuple(hallazgos),
            detenido_en_fila=tabla.detenido_en_fila,
        )

    ausentes = [c for c in COLUMNAS_OBLIGATORIAS_SCOPUS_CSV if c not in encabezado]
    if ausentes:
        for columna in ausentes:
            hallazgos.append(
                crear_hallazgo(
                    "L-E02",
                    archivo,
                    f"falta la columna obligatoria «{columna}» en el encabezado",
                    linea=1,
                    fila=1,
                )
            )
        return Lectura(registros=(), hallazgos=tuple(hallazgos))

    for fila in tabla.filas:
        if len(fila.celdas) != len(encabezado):
            comparacion = "más" if len(fila.celdas) > len(encabezado) else "menos"
            hallazgos.append(
                crear_hallazgo(
                    "L-E02",
                    archivo,
                    f"la fila {fila.fila} tiene {comparacion} columnas ({len(fila.celdas)}) "
                    f"que el encabezado ({len(encabezado)})",
                    linea=fila.linea,
                    fila=fila.fila,
                )
            )
            continue
        registros.append(
            construir_registro(
                fuente,
                "scopus_csv",
                archivo,
                fila.linea,
                list(zip(encabezado, fila.celdas, strict=True)),
                perfil,
            )
        )
    if tabla.detenido_en_fila is not None:
        hallazgos.append(
            crear_hallazgo(
                "L-E02",
                archivo,
                f"una celda de la fila {tabla.detenido_en_fila} supera el límite de campo "
                f"({LIMITE_CAMPO} caracteres) o la fila no es CSV válido; se detiene la "
                f"lectura en esa fila y se conservan los {len(registros)} registros anteriores",
                linea=tabla.detenido_en_linea,
                fila=tabla.detenido_en_fila,
            )
        )

    origen = {
        "titulo": perfil.escalares["titulo"],
        "autores": perfil.listas["autores"],
        "anio": perfil.anio,
        "doi": perfil.escalares["doi"],
        "resumen": perfil.escalares["resumen"],
    }
    hallazgos.extend(hallazgos_de_campos_esperados(archivo, origen, set(encabezado)))
    resultado = tuple(registros)
    hallazgos.extend(hallazgos_de_calidad(archivo, resultado))
    hallazgos.extend(hallazgos_de_identidad(archivo, resultado))
    return Lectura(
        registros=resultado,
        hallazgos=tuple(hallazgos),
        detenido_en_fila=tabla.detenido_en_fila,
    )
