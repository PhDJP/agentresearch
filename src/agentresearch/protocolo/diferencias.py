"""Diff estructural del protocolo, campo por campo (ADR-0008, punto 13).

El diff lo genera el paquete, no el LLM. Compara el modelo pydantic completo
de dos versiones del protocolo (con sus valores por defecto), de modo que
escribir un valor por defecto explícito, reordenar claves o cambiar
comentarios y comillas no cuenta como cambio de contenido.

- Los mapas se comparan clave por clave.
- Las listas cuyos elementos tienen `id` se comparan por su `id`, que aparece
  en la ruta (`criterios.inclusion[CI2].texto`); un cambio de orden entre los
  mismos `id` se reporta una vez como `reordenado`.
- Las listas de escalares se reportan completas en un solo cambio
  `modificado`, con los valores `agregados` y `eliminados` contados como
  multiconjunto.
- Las demás listas se comparan por posición (`metadatos.autores[0].nombre`).
"""

import json
from collections import Counter
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Literal

from agentresearch.protocolo.modelo import Protocolo

Operacion = Literal["agregado", "eliminado", "modificado", "reordenado"]


@dataclass(frozen=True, slots=True)
class Cambio:
    """Un cambio entre dos versiones del protocolo."""

    ruta: str
    operacion: Operacion
    antes: Any
    despues: Any
    agregados: list[Any] | None = None
    """Solo en listas de escalares: valores que aparecen en `despues` y no en `antes`."""
    eliminados: list[Any] | None = None
    """Solo en listas de escalares: valores que aparecen en `antes` y no en `despues`."""

    def como_dict(self) -> dict[str, Any]:
        datos: dict[str, Any] = {
            "ruta": self.ruta,
            "operacion": self.operacion,
            "antes": self.antes,
            "despues": self.despues,
        }
        if self.agregados is not None or self.eliminados is not None:
            datos["agregados"] = self.agregados or []
            datos["eliminados"] = self.eliminados or []
        return datos

    def __str__(self) -> str:
        if self.operacion == "agregado":
            return f"{self.ruta}: agregado {_mostrar(self.despues)}"
        if self.operacion == "eliminado":
            return f"{self.ruta}: eliminado {_mostrar(self.antes)}"
        if self.operacion == "reordenado":
            return f"{self.ruta}: reordenado {_mostrar(self.antes)} → {_mostrar(self.despues)}"
        texto = f"{self.ruta}: {_mostrar(self.antes)} → {_mostrar(self.despues)}"
        if self.agregados or self.eliminados:
            texto += (
                f" (agregados: {_mostrar(self.agregados or [])}; "
                f"eliminados: {_mostrar(self.eliminados or [])})"
            )
        return texto


def diferencias_protocolo(anterior: Protocolo, nuevo: Protocolo) -> list[Cambio]:
    """Compara dos versiones del protocolo y devuelve sus cambios, en orden de documento."""
    return diferencias(anterior.model_dump(mode="json"), nuevo.model_dump(mode="json"))


def diferencias(antes: Any, despues: Any) -> list[Cambio]:
    """Compara dos valores en tipos simples de Python (mapas, listas y escalares)."""
    cambios: list[Cambio] = []
    _comparar(antes, despues, "", cambios)
    return cambios


def _comparar(antes: Any, despues: Any, ruta: str, cambios: list[Cambio]) -> None:
    if isinstance(antes, dict) and isinstance(despues, dict):
        _comparar_mapas(antes, despues, ruta, cambios)
    elif isinstance(antes, list) and isinstance(despues, list):
        if _son_escalares(antes) and _son_escalares(despues):
            _comparar_escalares(antes, despues, ruta, cambios)
        elif _tienen_ids(antes, despues):
            _comparar_por_id(antes, despues, ruta, cambios)
        else:
            _comparar_por_posicion(antes, despues, ruta, cambios)
    elif not _iguales(antes, despues):
        cambios.append(Cambio(ruta, "modificado", antes, despues))


def _comparar_mapas(
    antes: dict[str, Any], despues: dict[str, Any], ruta: str, cambios: list[Cambio]
) -> None:
    for clave, valor in antes.items():
        ruta_clave = f"{ruta}.{clave}" if ruta else clave
        if clave in despues:
            _comparar(valor, despues[clave], ruta_clave, cambios)
        else:
            cambios.append(Cambio(ruta_clave, "eliminado", valor, None))
    for clave, valor in despues.items():
        if clave not in antes:
            ruta_clave = f"{ruta}.{clave}" if ruta else clave
            cambios.append(Cambio(ruta_clave, "agregado", None, valor))


def _comparar_escalares(
    antes: list[Any], despues: list[Any], ruta: str, cambios: list[Cambio]
) -> None:
    if len(antes) == len(despues) and all(map(_iguales, antes, despues)):
        return
    cambios.append(
        Cambio(
            ruta,
            "modificado",
            antes,
            despues,
            agregados=_diferencia_multiconjunto(despues, antes),
            eliminados=_diferencia_multiconjunto(antes, despues),
        )
    )


def _comparar_por_id(
    antes: list[dict[str, Any]], despues: list[dict[str, Any]], ruta: str, cambios: list[Cambio]
) -> None:
    anteriores = {elemento["id"]: elemento for elemento in antes}
    nuevos = {elemento["id"]: elemento for elemento in despues}
    for identificador, elemento in anteriores.items():
        if identificador not in nuevos:
            cambios.append(Cambio(f"{ruta}[{identificador}]", "eliminado", elemento, None))
    for identificador, elemento in nuevos.items():
        ruta_elemento = f"{ruta}[{identificador}]"
        if identificador in anteriores:
            _comparar(anteriores[identificador], elemento, ruta_elemento, cambios)
        else:
            cambios.append(Cambio(ruta_elemento, "agregado", None, elemento))
    comunes_antes = [i for i in anteriores if i in nuevos]
    comunes_despues = [i for i in nuevos if i in anteriores]
    if comunes_antes != comunes_despues:
        cambios.append(Cambio(ruta, "reordenado", list(anteriores), list(nuevos)))


def _comparar_por_posicion(
    antes: list[Any], despues: list[Any], ruta: str, cambios: list[Cambio]
) -> None:
    for posicion in range(max(len(antes), len(despues))):
        ruta_elemento = f"{ruta}[{posicion}]"
        if posicion >= len(despues):
            cambios.append(Cambio(ruta_elemento, "eliminado", antes[posicion], None))
        elif posicion >= len(antes):
            cambios.append(Cambio(ruta_elemento, "agregado", None, despues[posicion]))
        else:
            _comparar(antes[posicion], despues[posicion], ruta_elemento, cambios)


def _son_escalares(valores: list[Any]) -> bool:
    return all(not isinstance(valor, dict | list) for valor in valores)


def _tienen_ids(antes: list[Any], despues: list[Any]) -> bool:
    """Indica si ambas listas son de mapas con un `id` de texto único en cada lista."""
    for lista in (antes, despues):
        if not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in lista):
            return False
        ids = [elemento["id"] for elemento in lista]
        if len(set(ids)) != len(ids):
            return False
    return bool(antes or despues)


def _iguales(antes: Any, despues: Any) -> bool:
    """Igualdad que no confunde `True` con `1`, pero sí iguala `1` y `1.0`."""
    if isinstance(antes, bool) or isinstance(despues, bool):
        return type(antes) is type(despues) and antes == despues
    if isinstance(antes, int | float) and isinstance(despues, int | float):
        return antes == despues
    return type(antes) is type(despues) and bool(antes == despues)


def _diferencia_multiconjunto(minuendo: list[Any], sustraendo: list[Any]) -> list[Any]:
    """Elementos de `minuendo` que sobran respecto de `sustraendo`, en su orden original."""
    disponibles = Counter(_clave(valor) for valor in sustraendo)
    sobrantes = []
    for valor in minuendo:
        clave = _clave(valor)
        if disponibles[clave] > 0:
            disponibles[clave] -= 1
        else:
            sobrantes.append(valor)
    return sobrantes


def _clave(valor: Any) -> Hashable:
    """Clave que distingue `True` de `1` al contar valores escalares."""
    return (type(valor) is bool, valor)


def _mostrar(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=False)
