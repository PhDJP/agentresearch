"""Lector de Web of Science, texto plano (especificación 2b, «Formatos»).

Etiquetas de dos caracteres seguidas de un espacio y el valor. `FN` y `VR` son
la cabecera del formato y **no** avisan L-A03: solo se avisa lo que haya antes
del primer registro además de ellas. Un registro abre con `PT` y cierra con
`ER`, y `EF` cierra el archivo. Una línea con tres espacios iniciales continúa
la etiqueta anterior; qué significa depende del tipo de la etiqueta (`texto` se
une con un espacio; `lista_por_linea`, una línea por elemento).
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
from agentresearch.importacion.perfiles import PerfilEtiquetas, perfil_wos
from agentresearch.importacion.registro_etiquetas import construir_registro

_ETIQUETA = re.compile(r"^([A-Z][A-Z0-9])(?: (.*))?$")
_CABECERA_DEL_FORMATO = ("FN", "VR")


@dataclass
class _Abierto:
    inicio: int
    etiquetas: list[tuple[str, list[str]]] = field(default_factory=list)
    """Cada etiqueta con su valor y sus líneas de continuación, en orden."""


def _pares(abierto: _Abierto, perfil: PerfilEtiquetas) -> list[tuple[str, str]]:
    """Convierte las etiquetas con continuaciones en pares `(etiqueta, valor)`."""
    pares: list[tuple[str, str]] = []
    for etiqueta, lineas in abierto.etiquetas:
        if perfil.tipos.get(etiqueta) == "lista_por_linea":
            pares.extend((etiqueta, linea) for linea in lineas)
        else:
            pares.append((etiqueta, " ".join(linea for linea in lineas if linea)))
    return pares


def leer_wos(carga: Carga, fuente: str) -> Lectura:
    """Lee un archivo de Web of Science ya decodificado."""
    perfil = perfil_wos(fuente)
    archivo = carga.nombre
    hallazgos: list[Hallazgo] = []
    cabecera: list[tuple[int, str]] = []
    cerrados: list[_Abierto] = []
    abierto: _Abierto | None = None
    hubo_registro = False
    fin_visto = False

    def _error(mensaje: str, linea: int) -> None:
        hallazgos.append(crear_hallazgo("L-E02", archivo, mensaje, linea=linea))

    def _sin_cierre(registro: _Abierto) -> None:
        _error(
            "registro sin cierre: falta la etiqueta ER antes del siguiente PT, de EF o del "
            "fin del archivo",
            registro.inicio,
        )

    for numero, linea in enumerate(carga.lineas, 1):
        if not linea.strip():
            continue
        if fin_visto:
            _error("contenido después de EF", numero)
            continue
        if linea.startswith("   "):
            if abierto is not None and abierto.etiquetas:
                abierto.etiquetas[-1][1].append(linea.strip())
            elif not hubo_registro:
                cabecera.append((numero, linea))
            else:
                _error("línea de continuación fuera de un registro", numero)
            continue
        coincidencia = _ETIQUETA.match(linea)
        if coincidencia is None:
            if abierto is not None or hubo_registro:
                _error("línea sin etiqueta reconocible", numero)
            else:
                cabecera.append((numero, linea))
            continue
        etiqueta, valor = coincidencia.group(1), coincidencia.group(2) or ""
        if etiqueta == "PT":
            if abierto is not None:
                _sin_cierre(abierto)
            abierto = _Abierto(numero, [("PT", [valor])])
            hubo_registro = True
        elif etiqueta == "ER":
            if abierto is None:
                _error("etiqueta ER fuera de un registro", numero)
            else:
                cerrados.append(abierto)
                abierto = None
        elif etiqueta == "EF":
            if abierto is not None:
                _sin_cierre(abierto)
                abierto = None
            fin_visto = True
        elif abierto is not None:
            abierto.etiquetas.append((etiqueta, [valor]))
        elif not hubo_registro:
            if etiqueta not in _CABECERA_DEL_FORMATO:
                cabecera.append((numero, linea))
        else:
            _error(f"etiqueta {etiqueta} fuera de un registro", numero)
    if abierto is not None:
        _sin_cierre(abierto)

    registros = tuple(
        construir_registro(fuente, "wos_txt", archivo, r.inicio, _pares(r, perfil), perfil)
        for r in cerrados
    )
    lineas_cabecera, aviso = hallazgo_de_cabecera(archivo, cabecera)
    if aviso is not None:
        hallazgos.append(aviso)
    vistos = {etiqueta for r in cerrados for etiqueta, _lineas in r.etiquetas}
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
