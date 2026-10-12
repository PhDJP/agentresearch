"""Pruebas de la regla de versionado (datos sintéticos)."""

from datetime import UTC, datetime
from typing import Any

import pytest

from agentresearch.registros import (
    ConfiguracionPublicacion,
    Registro,
    RegistroNormalizado,
    cargar_politica,
    construir_registros,
    decodificar_configuracion,
)
from agentresearch.registros.politica import Base, CampoConfigurado, FuenteConfigurada
from agentresearch.registros.versionado import (
    CAMPOS_SIEMPRE_VERSIONADOS,
    campos_versionables,
    registro_versionable,
)
from agentresearch.trazabilidad import json_canonico

COMPLETA = "{tipo: institucion, detalle: Biblioteca Ficticia, medio: correo, fecha: '2026-09-29'}"
PENDIENTE = "{tipo: institucion, detalle: null, medio: null, fecha: null}"
RESUMEN = "Texto ficticio del resumen que jamás debe versionarse."


def configuracion(fuentes: dict[str, dict[str, str]]) -> ConfiguracionPublicacion:
    """Configuración con `{fuente: {campo: base_yaml}}`."""
    lineas = ["fuentes:"]
    for fuente, campos in fuentes.items():
        lineas.append(f"  {fuente}:")
        lineas.append("    campos:")
        for campo, base in campos.items():
            lineas.append(f"      {campo}:")
            lineas.append(f"        base: {base}")
    if len(lineas) == 1:
        lineas = ["fuentes: {}"]
    return decodificar_configuracion(
        "\n".join(lineas).encode("utf-8"),
        reloj=lambda: datetime(2026, 10, 12, tzinfo=UTC),
    )


def registro(**cambios: Any) -> Registro:
    datos: dict[str, Any] = {
        "fuente": "scopus",
        "formato": "scopus_csv",
        "archivo": "scopus.csv",
        "posicion": 2,
        "tipo_id_fuente": "eid",
        "id_fuente": "2-s2.0-0001",
        "titulo": "Estudio ficticio de mieles",
        "autores": ("Pérez, Ana",),
        "anio": 2021,
        "doi": "10.5555/miel.1",
        "pmid": "123",
        "resumen": RESUMEN,
        "palabras_clave_autor": ("miel",),
        "palabras_clave_indexadas": ("apicultura",),
        "otros": {"Cited by": "4"},
    }
    datos.update(cambios)
    (resultado,) = construir_registros("imp-0001", [RegistroNormalizado(**datos)])
    return resultado


POLITICA = cargar_politica()


# ------------------------------------------------------ campos_versionables


def test_solo_los_campos_con_base_completa_se_versionan_en_el_orden_del_esquema() -> None:
    config = configuracion(
        {"scopus": {"autores": COMPLETA, "doi": PENDIENTE, "titulo": COMPLETA, "anio": PENDIENTE}}
    )

    assert campos_versionables("scopus", POLITICA, config) == ("titulo", "autores")


def test_una_fuente_sin_entrada_no_tiene_campos_habilitados() -> None:
    config = configuracion({"scopus": {"titulo": COMPLETA}})

    assert campos_versionables("wos", POLITICA, config) == ()
    assert campos_versionables("fuente-no-declarada", POLITICA, config) == ()


def test_una_configuracion_sin_fuentes_no_versiona_ningun_campo() -> None:
    assert campos_versionables("scopus", POLITICA, configuracion({})) == ()


def test_un_campo_ausente_de_la_configuracion_no_se_versiona() -> None:
    config = configuracion({"scopus": {"titulo": COMPLETA}})

    assert "doi" not in campos_versionables("scopus", POLITICA, config)


def test_una_fuente_que_el_paquete_no_conoce_habilita_lo_que_el_estudio_registre() -> None:
    config = configuracion({"base-nueva": {"titulo": COMPLETA, "doi": COMPLETA}})

    assert campos_versionables("base-nueva", POLITICA, config) == ("titulo", "doi")


def test_el_techo_de_la_politica_tambien_se_aplica_a_una_configuracion_en_memoria() -> None:
    """Una configuración armada sin pasar por la carga no puede saltarse el techo."""
    base = Base.model_validate(
        {"tipo": "licencia", "detalle": "CC0", "fecha": "2026-09-29"},
        context={"ahora": datetime(2026, 10, 12, tzinfo=UTC)},
    )
    config = ConfiguracionPublicacion(
        fuentes={
            "acs": FuenteConfigurada(
                campos={
                    "pmid": CampoConfigurado(base=base),  # ACS no aporta pmid
                    "resumen": CampoConfigurado(base=base),  # nunca publicable
                    "doi": CampoConfigurado(base=base),
                }
            )
        }
    )

    assert campos_versionables("acs", POLITICA, config) == ("doi",)


# ------------------------------------------------------ registro_versionable


def test_sin_campos_habilitados_solo_salen_la_procedencia_y_el_hash() -> None:
    original = registro()

    resultado = registro_versionable(original, ())

    assert set(resultado) == {*CAMPOS_SIEMPRE_VERSIONADOS, "hash_completo"}
    assert resultado["id"] == "imp-0001-00001"
    assert resultado["posicion"] == 2
    assert resultado["hash_completo"] == original.hash_completo


def test_un_campo_pendiente_no_se_versiona_pero_el_registro_completo_conserva_su_valor() -> None:
    config = configuracion({"scopus": {"titulo": COMPLETA, "doi": PENDIENTE}})
    original = registro()

    resultado = registro_versionable(original, campos_versionables("scopus", POLITICA, config))

    assert resultado["titulo"] == "Estudio ficticio de mieles"
    assert "doi" not in resultado
    assert original.doi == "10.5555/miel.1"  # el registro completo no cambia


def test_los_campos_nunca_publicables_no_salen_aunque_se_pasen() -> None:
    original = registro()
    pedidos = (
        "titulo",
        "resumen",
        "palabras_clave_autor",
        "palabras_clave_indexadas",
        "otros",
        "referencias",
        "hash_completo",
    )

    resultado = registro_versionable(original, pedidos)

    assert set(resultado) - {*CAMPOS_SIEMPRE_VERSIONADOS, "hash_completo"} == {"titulo"}
    assert RESUMEN not in json_canonico(resultado)
    assert "Cited by" not in json_canonico(resultado)


def test_un_campo_habilitado_sin_valor_sale_como_nulo() -> None:
    original = registro(volumen=None)

    resultado = registro_versionable(original, ("volumen", "titulo"))

    assert "volumen" in resultado
    assert resultado["volumen"] is None


def test_la_salida_es_json_canonico_determinista() -> None:
    original = registro()
    campos = ("doi", "titulo", "autores", "anio")

    assert json_canonico(registro_versionable(original, campos)) == json_canonico(
        registro_versionable(original, tuple(reversed(campos)))
    )


# ------------------------------------------- id_fuente rige por el campo que repite


@pytest.mark.parametrize(
    ("tipo", "valor", "habilitados", "sale"),
    [
        # El DOI se rige por `doi`.
        ("doi", "10.5555/miel.1", ("id_fuente",), False),
        ("doi", "10.5555/miel.1", ("id_fuente", "doi"), True),
        ("doi", "10.5555/miel.1", ("doi",), False),
        # El PMID se rige por `pmid`.
        ("pmid", "123", ("id_fuente",), False),
        ("pmid", "123", ("id_fuente", "pmid"), True),
        ("pmid", "123", ("id_fuente", "doi"), False),
        # Los identificadores propios de la base rigen por sí mismos.
        ("eid", "2-s2.0-0001", ("id_fuente",), True),
        ("ut", "WOS:0001", ("id_fuente",), True),
        ("lens_id", "000-111", ("id_fuente",), True),
    ],
)
def test_id_fuente_de_tipo_doi_o_pmid_rige_por_su_campo(
    tipo: str, valor: str, habilitados: tuple[str, ...], sale: bool
) -> None:
    resultado = registro_versionable(
        registro(tipo_id_fuente=tipo, id_fuente=valor), habilitados
    )

    assert ("id_fuente" in resultado) is sale
    assert ("tipo_id_fuente" in resultado) is sale
    if sale:
        assert resultado["id_fuente"] == valor
        assert resultado["tipo_id_fuente"] == tipo


def test_el_doi_de_acs_no_se_publica_por_id_fuente_si_doi_no_esta_habilitado() -> None:
    """El caso de ACS: el identificador de la fuente es el DOI (ADR-0010, punto 19)."""
    config = configuracion({"acs": {"id_fuente": COMPLETA, "titulo": COMPLETA}})
    original = registro(
        fuente="acs", formato="ris", tipo_id_fuente="doi", id_fuente="10.5555/miel.1"
    )

    campos = campos_versionables("acs", POLITICA, config)
    resultado = registro_versionable(original, campos)

    assert campos == ("id_fuente", "titulo")
    assert "10.5555/miel.1" not in json_canonico(resultado)
    assert "id_fuente" not in resultado
    assert "tipo_id_fuente" not in resultado


def test_un_registro_sin_identificador_conserva_su_forma() -> None:
    original = registro(tipo_id_fuente="ninguno", id_fuente=None)

    resultado = registro_versionable(original, ("id_fuente", "titulo"))

    assert resultado["tipo_id_fuente"] == "ninguno"
    assert resultado["id_fuente"] is None
