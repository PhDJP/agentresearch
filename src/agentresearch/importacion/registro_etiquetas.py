"""Arma un `RegistroNormalizado` a partir de las etiquetas de un registro (RIS y Web of Science).

Lo que no se mapea a un campo va a `otros` con la etiqueta de origen. Los
valores repetidos de una etiqueta se unen con «; ». Los volátiles del perfil se
descartan y no entran al `hash_completo`.
"""

from agentresearch.importacion.ensamblado import (
    agregar_otros,
    componer_paginas,
    extraer_anio,
    unir_otros,
)
from agentresearch.importacion.perfiles import PerfilEtiquetas
from agentresearch.importacion.volatiles import procesar_n1_scopus
from agentresearch.registros import FormatoRegistro, RegistroNormalizado, normalizar_texto


def _primero_no_vacio(valores: list[str]) -> str | None:
    """Quita de la lista y devuelve el primer valor no vacío; el resto queda en ella."""
    for indice, valor in enumerate(valores):
        if normalizar_texto(valor):
            return valores.pop(indice)
    return None


def construir_registro(
    fuente: str,
    formato: FormatoRegistro,
    archivo: str,
    inicio: int,
    etiquetas: list[tuple[str, str]],
    perfil: PerfilEtiquetas,
) -> RegistroNormalizado:
    """Construye el registro. `etiquetas` son pares `(etiqueta, valor)` en orden de aparición."""
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
            separador = perfil.separadores.get(etiqueta)
            for valor in restantes.pop(etiqueta, []):
                if separador is not None:
                    elementos.extend(valor.split(separador))
                else:
                    elementos.append(valor)
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
    elif perfil.id_etiqueta is not None:
        tipo, etiqueta_id = perfil.id_etiqueta
        valor_id = _primero_no_vacio(restantes.get(etiqueta_id, []))
        if valor_id is not None:
            tipo_id, id_fuente = tipo, valor_id
    elif perfil.tipo_id_desde_doi:
        doi = campos.get("doi")
        if isinstance(doi, str) and normalizar_texto(doi):
            tipo_id, id_fuente = "doi", doi

    agregar_otros(restantes, extra)
    return RegistroNormalizado.model_validate(
        {
            "fuente": fuente,
            "formato": formato,
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
