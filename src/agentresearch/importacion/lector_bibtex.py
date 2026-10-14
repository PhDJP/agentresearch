"""Lector de BibTeX con `bibtexparser==2.0.1` y `pylatexenc==2.11` (especificación 2b).

La biblioteca queda detrás de esta interfaz para poder cambiarla sin tocar el
resto. Se usa **sin middlewares**: entrega los valores crudos (con sus
delimitadores) y este módulo resuelve las concatenaciones `#` y los `@string`
(`concatenaciones.py`) y decodifica LaTeX, de modo que todos los valores, incluidos
los de una entrada recuperada, reciben el mismo tratamiento.

Límites de la 2.0.1 que se cubren aquí:

- una concatenación con `#` queda como texto crudo: se resuelve con el resolvedor
  propio;
- la entrada de **clave repetida** no queda en `entries`: la biblioteca la deja en
  `failed_blocks` como `DuplicateBlockKeyBlock`, y se recupera desde su
  `ignore_error_block`. No es un error ni genera hallazgo (decisión del
  2026-10-13);
- una entrada con un **campo repetido** (`DuplicateFieldKeyBlock`) y cualquier
  otra mal formada (`ParsingFailedBlock`) dan L-E02 con su `start_line`, que la
  biblioteca cuenta desde 0, sumando 1. No se analiza el texto de los mensajes;
- la biblioteca avisa con `logging` (`bibtexparser.*`) y con `warnings.warn`: se
  capturan ambos y nada llega a `stderr`.
"""

import logging
import re
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

from bibtexparser.entrypoint import parse_string
from bibtexparser.model import (
    DuplicateBlockKeyBlock,
    DuplicateFieldKeyBlock,
    Entry,
    ParsingFailedBlock,
)
from pylatexenc.latex2text import LatexNodes2Text

from agentresearch.importacion.concatenaciones import resolver_valor
from agentresearch.importacion.ensamblado import (
    Lectura,
    hallazgos_de_calidad,
    hallazgos_de_campos_esperados,
)
from agentresearch.importacion.entrada import Carga
from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.identidad import hallazgos_de_identidad
from agentresearch.importacion.perfiles import perfil_bibtex
from agentresearch.importacion.registro_etiquetas import construir_registro
from agentresearch.registros import RegistroNormalizado

_TERMINADOR = re.compile(r"\r\n|\r")
_NECESITA_LATEX = re.compile(r"[\\{}]")
_PORCENTAJE = re.compile(r"(?<!\\)%")
_AMPERSAND = re.compile(r"(?<!\\)&")
_TILDE = re.compile(r"(?<!\\)~")


def decodificar_latex(texto: str) -> str:
    """Decodifica las secuencias de LaTeX de un valor (`{\\'e}` -> `é`).

    Es el único uso de `pylatexenc`. Solo se toca un valor con barra invertida o
    llaves. `%`, `&` y `~` sin escapar se protegen antes: en LaTeX son un
    comentario, un tabulador y un espacio duro, y borrarían o cambiarían texto
    legítimo. Las fórmulas entre `$` quedan como están.
    """
    if _NECESITA_LATEX.search(texto) is None:
        return texto
    protegido = _PORCENTAJE.sub(r"\\%", texto)
    protegido = _AMPERSAND.sub(r"\\&", protegido)
    protegido = _TILDE.sub(r"\\textasciitilde{}", protegido)
    convertidor = LatexNodes2Text(math_mode="verbatim")
    return str(convertidor.latex_to_text(protegido))


@contextmanager
def _sin_avisos_a_la_terminal() -> Iterator[list[str]]:
    """Captura los avisos de `bibtexparser` (`logging` y `warnings`) y los guarda aparte."""

    class _Acumulador(logging.Handler):
        def __init__(self) -> None:
            super().__init__(level=logging.DEBUG)
            self.mensajes: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.mensajes.append(record.getMessage())

    registro = logging.getLogger("bibtexparser")
    acumulador = _Acumulador()
    propaga = registro.propagate
    registro.addHandler(acumulador)
    registro.propagate = False
    try:
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            yield acumulador.mensajes
            acumulador.mensajes.extend(str(a.message) for a in avisos)
    finally:
        registro.removeHandler(acumulador)
        registro.propagate = propaga


def leer_bibtex(carga: Carga, fuente: str) -> Lectura:
    """Lee un BibTeX ya decodificado."""
    perfil = perfil_bibtex(fuente)
    archivo = carga.nombre
    texto = _TERMINADOR.sub("\n", carga.texto or "")
    with _sin_avisos_a_la_terminal():
        biblioteca = parse_string(texto, parse_stack=[])
    cadenas = {cadena.key.lower(): cadena.value for cadena in biblioteca.strings}

    entradas: list[Entry] = list(biblioteca.entries)
    hallazgos: list[Hallazgo] = []
    for bloque in biblioteca.failed_blocks:
        if isinstance(bloque, DuplicateBlockKeyBlock) and isinstance(
            bloque.ignore_error_block, Entry
        ):
            entradas.append(bloque.ignore_error_block)
            continue
        hallazgos.append(_error_de_bloque(archivo, bloque))
    entradas.sort(key=lambda entrada: entrada.start_line or 0)

    registros: list[RegistroNormalizado] = []
    for entrada in entradas:
        etiquetas = [("entry_type", entrada.entry_type.lower())]
        for campo in entrada.fields:
            valor = decodificar_latex(resolver_valor(str(campo.value), cadenas))
            etiquetas.append((campo.key.lower(), valor))
        registros.append(
            construir_registro(
                fuente, "bibtex", archivo, (entrada.start_line or 0) + 1, etiquetas, perfil
            )
        )

    vistos = _campos_presentes(entradas)
    origen = {
        "titulo": perfil.escalares["titulo"],
        "autores": perfil.listas["autores"],
        "anio": perfil.anio,
        "doi": perfil.escalares["doi"],
        "resumen": perfil.escalares["resumen"],
    }
    resultado = tuple(registros)
    hallazgos.extend(hallazgos_de_campos_esperados(archivo, origen, vistos))
    hallazgos.extend(hallazgos_de_calidad(archivo, resultado))
    hallazgos.extend(hallazgos_de_identidad(archivo, resultado))
    return Lectura(registros=resultado, hallazgos=tuple(hallazgos))


def _campos_presentes(entradas: list[Entry]) -> set[str]:
    return {campo.key.lower() for entrada in entradas for campo in entrada.fields}


def _error_de_bloque(archivo: str, bloque: ParsingFailedBlock) -> Hallazgo:
    """L-E02 de un bloque que la biblioteca no pudo leer, con la línea física (`start_line` + 1)."""
    linea = (bloque.start_line or 0) + 1
    if isinstance(bloque, DuplicateFieldKeyBlock):
        mensaje = "entrada con un campo repetido: no se puede decidir cuál es el valor"
    else:
        mensaje = "entrada BibTeX mal formada: la biblioteca no la pudo leer"
    return crear_hallazgo("L-E02", archivo, mensaje, linea=linea)
