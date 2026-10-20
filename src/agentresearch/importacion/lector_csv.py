"""Lector del CSV genérico con archivo de mapeo (especificación 2b, «Formatos»; cubre Lens).

El mapeo dice qué columna va a cada campo. Las columnas sin destino van a `otros`
con su nombre. Mismas reglas de estructura y de límite de campo que `scopus_csv`.
"""

from agentresearch.importacion.ensamblado import (
    Lectura,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
)
from agentresearch.importacion.entrada import Carga
from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.identidad import hallazgos_de_identidad
from agentresearch.importacion.mapeo import CAMPOS_DE_LISTA, Mapeo
from agentresearch.importacion.motor_csv import LIMITE_CAMPO, leer_tabla
from agentresearch.importacion.perfiles import PerfilEtiquetas
from agentresearch.importacion.registro_etiquetas import construir_registro
from agentresearch.registros import RegistroNormalizado, TipoIdFuente

_SIN_COLUMNA = ""
"""Marcador de «campo sin columna»: ninguna columna puede llamarse así sin ser descartada."""


def perfil_de_mapeo(mapeo: Mapeo) -> PerfilEtiquetas:
    """Traduce un mapeo a un perfil de columnas."""
    escalares: dict[str, tuple[str, ...]] = {}
    listas: dict[str, tuple[str, ...]] = {}
    separadores: dict[str, str] = {}
    anio: tuple[str, ...] = ()
    paginas = _SIN_COLUMNA
    id_etiqueta: tuple[TipoIdFuente, str] | None = None
    for columna, destino in mapeo.destinos.items():
        if destino.campo == "id_fuente" and destino.tipo_id is not None:
            id_etiqueta = (destino.tipo_id, columna)
        elif destino.campo in CAMPOS_DE_LISTA:
            listas[destino.campo] = (columna,)
            if destino.separador is not None:
                separadores[columna] = destino.separador
        elif destino.campo == "anio":
            anio = (columna,)
        elif destino.campo == "paginas":
            paginas = columna
        else:
            escalares[destino.campo] = (columna,)
    return PerfilEtiquetas(
        escalares=escalares,
        listas=listas,
        anio=anio,
        paginas_inicio=paginas,
        paginas_fin=_SIN_COLUMNA,
        separadores=separadores,
        id_etiqueta=id_etiqueta,
    )


def _errores_de_mapeo(mapeo: Mapeo, mensajes: list[str]) -> tuple[Hallazgo, ...]:
    return tuple(crear_hallazgo("L-E02", mapeo.nombre, m) for m in mensajes)


def leer_csv(carga: Carga, fuente: str, mapeo: Mapeo) -> Lectura:
    """Lee un CSV genérico con su mapeo."""
    archivo = carga.nombre
    if mapeo.problemas:
        return Lectura(registros=(), hallazgos=_errores_de_mapeo(mapeo, list(mapeo.problemas)))

    tabla = leer_tabla(carga.texto or "")
    hallazgos: list[Hallazgo] = []
    encabezado = tabla.encabezado
    if encabezado is None:
        mensaje = (
            "el archivo está vacío: falta el encabezado"
            if tabla.detenido_en_fila is None
            else f"una celda del encabezado supera el límite de campo ({LIMITE_CAMPO} caracteres)"
        )
        hallazgos.append(
            crear_hallazgo(
                "L-E02",
                archivo,
                mensaje,
                linea=tabla.detenido_en_linea,
                fila=tabla.detenido_en_fila,
            )
        )
        return Lectura(
            registros=(), hallazgos=tuple(hallazgos), detenido_en_fila=tabla.detenido_en_fila
        )

    faltantes = [c for c in mapeo.destinos if c not in encabezado]
    if faltantes:
        mensajes = [
            f"la columna «{c}» del mapeo no está en el encabezado de {archivo}" for c in faltantes
        ]
        return Lectura(registros=(), hallazgos=_errores_de_mapeo(mapeo, mensajes))

    perfil = perfil_de_mapeo(mapeo)
    registros: list[RegistroNormalizado] = []
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
                "csv",
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
        "titulo": perfil.escalares.get("titulo", ()),
        "autores": perfil.listas.get("autores", ()),
        "anio": perfil.anio,
        "doi": perfil.escalares.get("doi", ()),
        "resumen": perfil.escalares.get("resumen", ()),
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
