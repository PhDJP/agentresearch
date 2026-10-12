"""Pruebas del `hash_completo` del registro normalizado (ADR-0010, punto 20)."""

import hashlib
from typing import Any

import pytest

from agentresearch.registros import (
    CAMPOS_DEL_HASH,
    Registro,
    RegistroNormalizado,
    construir_registros,
)

# Valor de referencia: si cambia, cambió la serialización canónica o el conjunto
# de campos del hash, y eso exige incrementar `VERSION_NORMALIZACION` (ADR-0010).
CANONICO_DE_REFERENCIA = (
    '{"anio":2021,"autores":["Pérez, Ana","Gómez, Luis"],"doi":"10.5555/miel.1",'
    '"fuente_publicacion":null,"id_fuente":"2-s2.0-0001","idioma":null,"numero":null,'
    '"otros":{"N1":"nota"},"paginas":null,"palabras_clave_autor":[],'
    '"palabras_clave_indexadas":[],"pmid":null,"resumen":"Resumen ficticio.",'
    '"tipo_documento":null,"tipo_id_fuente":"eid","titulo":"Estudio ficticio de mieles",'
    '"volumen":null}'
)
HASH_DE_REFERENCIA = "sha256:3e110385126191b264d67038b48969686b298b14754e932dc08c6bbee21afa04"


def registro(**cambios: Any) -> RegistroNormalizado:
    datos: dict[str, Any] = {
        "fuente": "fuente-a",
        "formato": "ris",
        "archivo": "a.ris",
        "posicion": 1,
        "tipo_id_fuente": "eid",
        "id_fuente": "2-s2.0-0001",
        "titulo": "Estudio ficticio de mieles",
        "autores": ("Pérez, Ana", "Gómez, Luis"),
        "anio": 2021,
        "doi": "10.5555/miel.1",
        "resumen": "Resumen ficticio.",
        "otros": {"N1": "nota"},
    }
    datos.update(cambios)
    return RegistroNormalizado(**datos)


def test_el_hash_coincide_con_el_valor_de_referencia() -> None:
    esperado = "sha256:" + hashlib.sha256(CANONICO_DE_REFERENCIA.encode("utf-8")).hexdigest()

    assert esperado == HASH_DE_REFERENCIA
    assert registro().hash_completo == HASH_DE_REFERENCIA


def test_los_campos_del_hash_son_los_bibliograficos() -> None:
    """Todos los campos del esquema salvo la procedencia, `fuente` y `formato`."""
    excluidos = {"fuente", "formato", "archivo", "posicion"}

    assert set(CAMPOS_DEL_HASH) == set(RegistroNormalizado.model_fields) - excluidos
    assert len(CAMPOS_DEL_HASH) == len(set(CAMPOS_DEL_HASH))


def test_el_hash_no_depende_de_la_procedencia_ni_de_los_ids() -> None:
    base = registro()
    otra_descarga = registro(archivo="otra-descarga (1).ris", posicion=480)
    otra_fuente = registro(fuente="fuente-b", formato="csv")

    (con_ids,) = construir_registros("imp-0007", [base])
    (con_otros_ids,) = construir_registros("imp-0009", [otra_descarga])

    assert base.hash_completo == otra_descarga.hash_completo
    assert base.hash_completo == otra_fuente.hash_completo
    assert con_ids.hash_completo == con_otros_ids.hash_completo == base.hash_completo
    assert isinstance(con_ids, Registro)


@pytest.mark.parametrize(
    "cambio",
    [
        {"tipo_id_fuente": "ut", "id_fuente": "2-s2.0-0001"},
        {"id_fuente": "2-s2.0-0002"},
        {"titulo": "Otro título"},
        {"autores": ("Gómez, Luis", "Pérez, Ana")},  # el orden importa
        {"anio": 2022},
        {"fuente_publicacion": "Revista Ficticia"},
        {"volumen": "12"},
        {"numero": "3"},
        {"paginas": "10-20"},
        {"doi": "10.5555/miel.2"},
        {"pmid": "123456"},
        {"tipo_documento": "Article"},
        {"idioma": "es"},
        {"resumen": "Otro resumen."},
        {"palabras_clave_autor": ("miel",)},
        {"palabras_clave_indexadas": ("apicultura",)},
        {"otros": {"N1": "otra nota"}},
        {"otros": {"N1": "nota", "N2": "más"}},
    ],
)
def test_el_hash_cambia_si_cambia_un_campo_bibliografico(cambio: dict[str, Any]) -> None:
    assert registro(**cambio).hash_completo != registro().hash_completo


def test_el_orden_de_las_claves_de_otros_no_importa() -> None:
    uno = registro(otros={"A": "1", "B": "2"})
    otro = registro(otros={"B": "2", "A": "1"})

    assert uno.hash_completo == otro.hash_completo


def test_dos_formas_del_mismo_texto_dan_el_mismo_hash() -> None:
    """La normalización se aplica al construir, así que no cambia el hash."""
    normal = registro(titulo="Café de montaña")
    descompuesto = registro(titulo="  Café de   montaña ")

    assert normal.hash_completo == descompuesto.hash_completo


def test_el_hash_tiene_el_formato_sha256() -> None:
    valor = registro().hash_completo

    assert valor.startswith("sha256:")
    assert len(valor) == len("sha256:") + 64
