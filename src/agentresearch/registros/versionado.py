"""Regla de versionado: qué campos de un registro llegan al repositorio (ADR-0010, punto 4).

Combina la política del paquete (`politica_datos.yaml`) con la configuración de
publicación del estudio (`publicacion_datos.yaml`):

- un campo se versiona solo si no es `nunca_publicables`, el estudio lo habilita
  para esa fuente y su base está completa;
- una fuente sin entrada en `publicacion_datos.yaml` no tiene campos
  habilitados; un campo ausente no se versiona;
- `id_fuente` rige por el campo que repite: con `tipo_id_fuente` `doi` o
  `pmid` se versiona solo si `doi` o `pmid` está habilitado;
- los campos que no se versionan **sí se importan**: el registro completo se
  conserva en local, y lo que se restringe es la publicación.
"""

from collections.abc import Collection
from typing import Any

from agentresearch.registros.modelo import Registro
from agentresearch.registros.politica import (
    CAMPOS_HABILITABLES,
    ConfiguracionPublicacion,
    PoliticaDatos,
)

CAMPOS_SIEMPRE_VERSIONADOS = ("id", "id_importacion", "fuente", "formato", "archivo", "posicion")
"""Procedencia del registro: se versiona siempre, junto con `hash_completo`."""


def campos_versionables(
    fuente: str, politica: PoliticaDatos, configuracion: ConfiguracionPublicacion
) -> tuple[str, ...]:
    """Devuelve los campos habilitables que se versionan para `fuente`, en el orden del esquema.

    Un campo se incluye si el estudio lo habilita para esa fuente con una base
    completa y no es `nunca_publicables`. Si la fuente es conocida por la
    política, el campo debe estar además dentro de su techo. `id_fuente` se
    incluye aquí, pero su versionado efectivo depende del tipo de cada
    registro (ver `registro_versionable`).
    """
    entrada = configuracion.fuentes.get(fuente)
    if entrada is None:
        return ()
    techo = politica.fuentes.get(fuente)
    habilitados = {
        campo
        for campo, configurado in entrada.campos.items()
        if configurado.base.es_completa
        and campo not in politica.nunca_publicables
        and (techo is None or campo in techo.campos_habilitables)
    }
    return tuple(campo for campo in CAMPOS_HABILITABLES if campo in habilitados)


def registro_versionable(registro: Registro, campos: Collection[str]) -> dict[str, Any]:
    """Devuelve el registro con solo los campos versionables y los que se versionan siempre.

    `campos` es lo que devolvió `campos_versionables`. Solo se toman de ahí los
    campos habilitables, así que un campo `nunca_publicables` (el resumen, las
    palabras clave) o `otros` no sale aunque se pase. Un campo habilitado cuyo
    valor falta sale como `None`. Siempre salen la procedencia y
    `hash_completo`, con el que se verifica la regeneración del registro
    completo desde el original.
    """
    habilitados = set(campos) & set(CAMPOS_HABILITABLES)
    resultado: dict[str, Any] = {
        nombre: getattr(registro, nombre) for nombre in CAMPOS_SIEMPRE_VERSIONADOS
    }
    for campo in CAMPOS_HABILITABLES:
        if campo not in habilitados:
            continue
        if campo == "id_fuente":
            if not _id_fuente_versionable(registro, habilitados):
                continue
            resultado["tipo_id_fuente"] = registro.tipo_id_fuente
        resultado[campo] = getattr(registro, campo)
    resultado["hash_completo"] = registro.hash_completo
    return resultado


def _id_fuente_versionable(registro: Registro, habilitados: Collection[str]) -> bool:
    """Un `id_fuente` que repite el DOI o el PMID rige por ese campo."""
    if registro.tipo_id_fuente == "doi":
        return "doi" in habilitados
    if registro.tipo_id_fuente == "pmid":
        return "pmid" in habilitados
    return True
