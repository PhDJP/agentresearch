"""Pruebas de los modelos provisionales de artículo, estudio y vínculo."""

import pytest
from pydantic import ValidationError

from agentresearch.registros import RegistroNormalizado, construir_registros
from agentresearch.registros.estudios import Articulo, Estudio, VinculoArticuloEstudio


def test_un_articulo_referencia_registros_sin_modificarlos() -> None:
    normalizado = RegistroNormalizado(fuente="fuente-a", formato="csv", archivo="a.csv", posicion=2)
    (registro,) = construir_registros("imp-0001", [normalizado])
    copia = registro.model_copy()

    articulo = Articulo(id="art-00001", ids_registros=(registro.id,))

    assert articulo.ids_registros == ("imp-0001-00001",)
    assert registro == copia


def test_un_articulo_puede_reunir_registros_de_varias_fuentes() -> None:
    articulo = Articulo(id="art-00002", ids_registros=("imp-0001-00001", "imp-0002-00007"))

    assert len(articulo.ids_registros) == 2


def test_un_articulo_sin_registros_es_valido_por_ahora() -> None:
    assert Articulo(id="art-00003").ids_registros == ()


@pytest.mark.parametrize("id_articulo", ["art-1", "art-000001", "est-00001", "articulo-1", ""])
def test_el_id_de_un_articulo_se_valida(id_articulo: str) -> None:
    with pytest.raises(ValidationError):
        Articulo(id=id_articulo)


def test_un_articulo_rechaza_ids_de_registro_invalidos_o_repetidos() -> None:
    with pytest.raises(ValidationError):
        Articulo(id="art-00001", ids_registros=("registro-1",))
    with pytest.raises(ValidationError):
        Articulo(id="art-00001", ids_registros=("imp-0001-00001", "imp-0001-00001"))


@pytest.mark.parametrize("id_estudio", ["est-1", "est-000001", "art-00001", ""])
def test_el_id_de_un_estudio_se_valida(id_estudio: str) -> None:
    with pytest.raises(ValidationError):
        Estudio(id=id_estudio)


def test_la_relacion_articulo_estudio_es_de_muchos_a_muchos() -> None:
    vinculos = [
        VinculoArticuloEstudio(id_articulo="art-00001", id_estudio="est-00001"),
        # Un estudio reportado en dos artículos.
        VinculoArticuloEstudio(id_articulo="art-00002", id_estudio="est-00001"),
        # Un artículo que reporta dos estudios.
        VinculoArticuloEstudio(id_articulo="art-00001", id_estudio="est-00002"),
    ]

    assert {v.id_estudio for v in vinculos if v.id_articulo == "art-00001"} == {
        "est-00001",
        "est-00002",
    }
    assert {v.id_articulo for v in vinculos if v.id_estudio == "est-00001"} == {
        "art-00001",
        "art-00002",
    }


@pytest.mark.parametrize(
    ("id_articulo", "id_estudio"),
    [("est-00001", "est-00001"), ("art-00001", "art-00001"), ("art-1", "est-00001")],
)
def test_un_vinculo_rechaza_ids_con_forma_invalida(id_articulo: str, id_estudio: str) -> None:
    with pytest.raises(ValidationError):
        VinculoArticuloEstudio(id_articulo=id_articulo, id_estudio=id_estudio)


def test_los_modelos_provisionales_rechazan_campos_desconocidos() -> None:
    with pytest.raises(ValidationError):
        Estudio(id="est-00001", titulo="x")  # type: ignore[call-arg]
