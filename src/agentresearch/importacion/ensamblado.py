"""Piezas comunes para armar registros a partir de lo que leen los lectores.

Los lectores pasan texto crudo: el modelo `RegistroNormalizado` aplica la
normalización al construirse (hoja de ruta, notas del 2a). Aquí viven las
decisiones de lectura que comparten todos los formatos: `anio`, `paginas`, los
campos repetidos de `otros` y los hallazgos que no dependen del formato
(L-A02, L-A03 y L-A04).
"""

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from agentresearch.importacion.hallazgos import Hallazgo, crear_hallazgo
from agentresearch.importacion.resultado import LineaCabecera
from agentresearch.registros import RegistroNormalizado, normalizar_texto

SEPARADOR_OTROS = "; "
"""Con qué se unen los valores de un campo repetido de `otros` (entra al `hash_completo`)."""

CAMPOS_ESPERADOS = ("titulo", "autores", "anio", "doi", "resumen")
"""Campos cuya ausencia en el archivo avisa L-A04 (especificación 2b, A7)."""

_PATRON_ANIO = re.compile(r"(?<![0-9])[0-9]{4}(?![0-9])")

ValoresPorClave = Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class Lectura:
    """Lo que entrega un lector, antes de que `leer` le agregue el hash y el archivo."""

    registros: tuple[RegistroNormalizado, ...]
    hallazgos: tuple[Hallazgo, ...]
    lineas_cabecera: tuple[LineaCabecera, ...] = ()
    detenido_en_fila: int | None = None


def unir_otros(valores: ValoresPorClave) -> dict[str, str]:
    """Une los valores repetidos de cada clave con `"; "`, sin los vacíos.

    Una clave sin ningún valor no vacío no aparece: un valor vacío es un campo
    ausente.
    """
    unidos: dict[str, str] = {}
    for clave, lista in valores.items():
        partes = [p for p in (normalizar_texto(v) for v in lista) if p]
        if partes:
            unidos[clave] = SEPARADOR_OTROS.join(partes)
    return unidos


def extraer_anio(etiqueta: str, valor: str | None) -> tuple[int | None, dict[str, list[str]]]:
    """Toma `anio` como el primer grupo de cuatro dígitos del valor.

    Si el valor no tiene un grupo así, `anio` queda nulo y el valor crudo va a
    `otros` con la etiqueta de origen: no se pierde nada.
    """
    texto = normalizar_texto(valor) if valor is not None else ""
    if not texto:
        return None, {}
    coincidencia = _PATRON_ANIO.search(texto)
    if coincidencia is None:
        return None, {etiqueta: [texto]}
    return int(coincidencia.group()), {}


def componer_paginas(
    inicio: tuple[str, str | None], fin: tuple[str, str | None]
) -> tuple[str | None, dict[str, list[str]]]:
    """Compone `paginas` como `inicio-fin`, o solo el inicio.

    Cada argumento es `(etiqueta, valor)`. Un fin sin inicio no se inventa como
    página: va a `otros` con su etiqueta.
    """
    valor_inicio = inicio[1]
    etiqueta_fin, valor_fin = fin
    texto_inicio = normalizar_texto(valor_inicio) if valor_inicio is not None else ""
    texto_fin = normalizar_texto(valor_fin) if valor_fin is not None else ""
    if texto_inicio and texto_fin:
        return f"{texto_inicio}-{texto_fin}", {}
    if texto_inicio:
        return texto_inicio, {}
    if texto_fin:
        return None, {etiqueta_fin: [texto_fin]}
    return None, {}


def agregar_otros(destino: dict[str, list[str]], extra: ValoresPorClave) -> None:
    """Agrega a `destino` los valores de `extra`, conservando el orden de aparición."""
    for clave, lista in extra.items():
        destino.setdefault(clave, []).extend(lista)


def hallazgos_de_calidad(
    archivo: str, registros: Sequence[RegistroNormalizado]
) -> tuple[Hallazgo, ...]:
    """L-A02: un registro sin título, con la línea donde empieza."""
    return tuple(
        crear_hallazgo("L-A02", archivo, "registro sin título", linea=registro.posicion)
        for registro in registros
        if registro.titulo is None
    )


def hallazgo_de_cabecera(
    archivo: str, lineas: Sequence[tuple[int, str]]
) -> tuple[tuple[LineaCabecera, ...], Hallazgo | None]:
    """L-A03: las líneas no vacías anteriores al primer registro, que se muestran."""
    cabecera = tuple(
        LineaCabecera(linea=numero, texto=texto) for numero, texto in lineas if texto.strip()
    )
    if not cabecera:
        return (), None
    hallazgo = crear_hallazgo(
        "L-A03",
        archivo,
        f"{len(cabecera)} línea(s) de cabecera antes del primer registro",
        linea=cabecera[0].linea,
    )
    return cabecera, hallazgo


def hallazgos_de_campos_esperados(
    archivo: str,
    origen_por_campo: Mapping[str, Sequence[str]],
    vistos: Collection[str],
) -> tuple[Hallazgo, ...]:
    """L-A04: un campo esperado cuya etiqueta o columna no aparece en el archivo.

    `origen_por_campo` dice qué etiquetas o columnas alimentan cada campo, y
    `vistos` las que el archivo tiene (el encabezado de un CSV, o las etiquetas
    que aparecen en algún registro). La exportación no incluyó ese campo.
    """
    hallazgos: list[Hallazgo] = []
    for campo in CAMPOS_ESPERADOS:
        origenes = origen_por_campo.get(campo, ())
        if any(origen in vistos for origen in origenes):
            continue
        hallazgos.append(
            crear_hallazgo(
                "L-A04",
                archivo,
                f"el archivo no trae el campo esperado «{campo}»: la exportación no lo incluyó",
            )
        )
    return tuple(hallazgos)
