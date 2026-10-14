"""Identificadores repetidos y registros sin identidad (especificación 2b, «Reglas de lectura»).

- La identidad para el error L-E03 es el par `(tipo_id_fuente, id_fuente)`. El
  DOI **no** hace de identidad para el error.
- L-A05 avisa de un mismo DOI en registros que no tienen identificador de la
  fuente; un registro con identificador se compara solo por él.
- L-A01 avisa de un registro sin identificador de la fuente ni DOI.

Los mensajes citan archivo y línea, nunca el valor del identificador.
"""

from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.registros import RegistroNormalizado


class Ocurrencia(BaseModel):
    """Dónde aparece un identificador repetido."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    archivo: str = Field(min_length=1)
    linea: int = Field(ge=1)


class Repeticion(BaseModel):
    """Un identificador que aparece más de una vez entre los archivos de una búsqueda."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    regla: str
    tipo: str
    """`eid`, `ut`, `doi`, … para L-E03; `doi` para L-A05."""
    ocurrencias: tuple[Ocurrencia, ...]


def _clave(registro: RegistroNormalizado) -> tuple[str, str, str] | None:
    """Clave de comparación del registro: `(regla, tipo, valor)` o `None`."""
    if registro.tipo_id_fuente != "ninguno" and registro.id_fuente is not None:
        return ("L-E03", registro.tipo_id_fuente, registro.id_fuente)
    if registro.doi is not None:
        return ("L-A05", "doi", registro.doi)
    return None


def _grupos(
    archivos: Sequence[tuple[str, Sequence[RegistroNormalizado]]],
) -> dict[tuple[str, str, str], list[tuple[int, str, int]]]:
    """Agrupa las ocurrencias `(índice de archivo, nombre, línea)` por clave, en orden."""
    grupos: dict[tuple[str, str, str], list[tuple[int, str, int]]] = defaultdict(list)
    for indice, (nombre, registros) in enumerate(archivos):
        for registro in registros:
            clave = _clave(registro)
            if clave is not None:
                grupos[clave].append((indice, nombre, registro.posicion))
    return grupos


def _mensaje(regla: str, primero: tuple[int, str, int], mismo_archivo: bool) -> str:
    donde = f"línea {primero[2]}" if mismo_archivo else f"{primero[1]}, línea {primero[2]}"
    if regla == "L-E03":
        return f"identificador de la fuente repetido: ya aparece en {donde}"
    return f"DOI repetido en registros sin identificador de la fuente: ya aparece en {donde}"


def hallazgos_de_identidad(
    archivo: str, registros: Sequence[RegistroNormalizado]
) -> tuple[Hallazgo, ...]:
    """L-A01, L-E03 y L-A05 dentro de un archivo.

    El hallazgo de un repetido va en la segunda y las siguientes apariciones, con
    la línea de la primera en el mensaje.
    """
    hallazgos: list[Hallazgo] = []
    for registro in registros:
        if registro.tipo_id_fuente == "ninguno" and registro.doi is None:
            hallazgos.append(
                crear_hallazgo(
                    "L-A01",
                    archivo,
                    "registro sin identificador de la fuente ni DOI: no se podrá detectar "
                    "si está repetido",
                    linea=registro.posicion,
                )
            )
    for (regla, _tipo, _valor), ocurrencias in _grupos([(archivo, registros)]).items():
        primero = ocurrencias[0]
        for _indice, nombre, linea in ocurrencias[1:]:
            hallazgos.append(
                crear_hallazgo(regla, nombre, _mensaje(regla, primero, True), linea=linea)
            )
    return tuple(sorted(hallazgos, key=lambda h: (h.linea or 0, h.regla)))


def repeticiones_entre_archivos(
    archivos: Sequence[tuple[str, Sequence[RegistroNormalizado]]],
) -> tuple[tuple[Repeticion, ...], tuple[Hallazgo, ...]]:
    """Identificadores (L-E03) y DOI sin identificador (L-A05) que aparecen en dos o más archivos.

    Devuelve las repeticiones con todas sus ocurrencias, y un hallazgo por cada
    aparición posterior a la primera que cae en otro archivo.
    """
    repeticiones: list[Repeticion] = []
    hallazgos: list[Hallazgo] = []
    for (regla, tipo, _valor), ocurrencias in _grupos(archivos).items():
        if len({indice for indice, _n, _l in ocurrencias}) < 2:
            continue
        repeticiones.append(
            Repeticion(
                regla=regla,
                tipo=tipo,
                ocurrencias=tuple(Ocurrencia(archivo=n, linea=ln) for _i, n, ln in ocurrencias),
            )
        )
        primero = ocurrencias[0]
        for indice, nombre, linea in ocurrencias[1:]:
            if indice != primero[0]:
                hallazgos.append(
                    crear_hallazgo(regla, nombre, _mensaje(regla, primero, False), linea=linea)
                )
    return tuple(repeticiones), tuple(hallazgos)
