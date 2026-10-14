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
    agregar_otros,
    componer_paginas,
    extraer_anio,
    hallazgo_de_cabecera,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
    unir_otros,
)
from agentresearch.importacion.entrada import Carga
from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.identidad import hallazgos_de_identidad
from agentresearch.importacion.perfiles import PerfilRis, perfil_ris
from agentresearch.importacion.volatiles import procesar_n1_scopus
from agentresearch.registros import RegistroNormalizado, normalizar_texto

_ETIQUETA = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")


@dataclass
class _Abierto:
    inicio: int
    etiquetas: list[tuple[str, str]] = field(default_factory=list)


def _primero_no_vacio(valores: list[str]) -> str | None:
    """Quita de la lista y devuelve el primer valor no vacío; el resto queda en ella."""
    for indice, valor in enumerate(valores):
        if normalizar_texto(valor):
            return valores.pop(indice)
    return None


def _construir(
    fuente: str, archivo: str, inicio: int, etiquetas: list[tuple[str, str]], perfil: PerfilRis
) -> RegistroNormalizado:
    restantes: dict[str, list[str]] = {}
    for etiqueta, valor in etiquetas:
        restantes.setdefault(etiqueta, []).append(valor)
    for volatil in perfil.volatiles:
        restantes.pop(volatil, None)

    campos: dict[str, object] = {}
    for campo, candidatas in perfil.escalares.items():
        for etiqueta in candidatas:
            elegido = _primero_no_vacio(restantes.get(etiqueta, []))
            if elegido is not None:
                campos[campo] = elegido
                break
    for campo, candidatas in perfil.listas.items():
        elementos: list[str] = []
        for etiqueta in candidatas:
            elementos.extend(restantes.pop(etiqueta, []))
        campos[campo] = tuple(elementos)

    extra: dict[str, list[str]] = {}
    texto_anio: str | None = None
    etiqueta_anio = perfil.anio[0]
    for candidata in perfil.anio:
        texto_anio = _primero_no_vacio(restantes.get(candidata, []))
        if texto_anio is not None:
            etiqueta_anio = candidata
            break
    anio, sobrante = extraer_anio(etiqueta_anio, texto_anio)
    agregar_otros(extra, sobrante)
    paginas, sobrante = componer_paginas(
        (perfil.paginas_inicio, _primero_no_vacio(restantes.get(perfil.paginas_inicio, []))),
        (perfil.paginas_fin, _primero_no_vacio(restantes.get(perfil.paginas_fin, []))),
    )
    agregar_otros(extra, sobrante)

    tipo_id: str = "ninguno"
    id_fuente: str | None = None
    if perfil.eid_en_n1:
        eid, resto_n1 = procesar_n1_scopus(restantes.pop("N1", []))
        restantes["N1"] = resto_n1
        if eid is not None:
            tipo_id, id_fuente = "eid", eid
    elif perfil.tipo_id_desde_doi:
        doi = campos.get("doi")
        if isinstance(doi, str) and normalizar_texto(doi):
            tipo_id, id_fuente = "doi", doi

    agregar_otros(restantes, extra)
    return RegistroNormalizado.model_validate(
        {
            "fuente": fuente,
            "formato": "ris",
            "archivo": archivo,
            "posicion": inicio,
            "tipo_id_fuente": tipo_id,
            "id_fuente": id_fuente,
            "anio": anio,
            "paginas": paginas,
            "otros": unir_otros(restantes),
            **campos,
        }
    )


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

    registros = tuple(_construir(fuente, archivo, r.inicio, r.etiquetas, perfil) for r in cerrados)
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
