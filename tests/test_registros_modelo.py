"""Pruebas del modelo del registro normalizado (datos sintéticos, temas ficticios)."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentresearch.registros import modelo
from agentresearch.registros.modelo import (
    LIMITE_POSICION,
    LimiteDePosicionExcedido,
    Registro,
    RegistroNormalizado,
    construir_registros,
    formatear_id_registro,
)


def normalizado(**cambios: Any) -> RegistroNormalizado:
    """Un registro normalizado sintético, con los campos que se indiquen cambiados."""
    datos: dict[str, Any] = {
        "fuente": "fuente-a",
        "formato": "ris",
        "archivo": "exportacion-1.ris",
        "posicion": 1,
        "titulo": "Estudio ficticio de la fermentación de mieles",
        "autores": ("Pérez, Ana", "Gómez, Luis"),
        "anio": 2021,
    }
    datos.update(cambios)
    return RegistroNormalizado(**datos)


def test_un_campo_desconocido_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        normalizado(campo_inventado="x")


def test_un_registro_sin_doi_ni_revista_es_valido() -> None:
    """Una patente o una tesis no exige DOI ni fuente de publicación (ADR-0010, punto 22)."""
    patente = normalizado(tipo_documento="Patent", doi=None, fuente_publicacion=None)

    assert patente.doi is None
    assert patente.fuente_publicacion is None


def test_los_valores_por_omision_son_nulos_o_vacios() -> None:
    minimo = RegistroNormalizado(fuente="fuente-a", formato="csv", archivo="a.csv", posicion=2)

    assert minimo.titulo is None
    assert minimo.autores == ()
    assert minimo.otros == {}
    assert minimo.tipo_id_fuente == "ninguno"


def test_el_registro_normalizado_no_tiene_identificadores_de_importacion() -> None:
    assert "id" not in RegistroNormalizado.model_fields
    assert "id_importacion" not in RegistroNormalizado.model_fields
    assert {"id", "id_importacion"} <= set(Registro.model_fields)


def test_el_registro_es_inmutable() -> None:
    registro = normalizado()

    with pytest.raises(ValidationError):
        registro.titulo = "otro"  # type: ignore[misc]


@pytest.mark.parametrize("formato", ["pdf", "RIS", "", "xlsx"])
def test_un_formato_desconocido_se_rechaza(formato: str) -> None:
    with pytest.raises(ValidationError):
        normalizado(formato=formato)


@pytest.mark.parametrize("posicion", [0, -1])
def test_la_posicion_en_el_archivo_empieza_en_uno(posicion: int) -> None:
    with pytest.raises(ValidationError):
        normalizado(posicion=posicion)


def test_el_id_de_la_fuente_exige_su_tipo() -> None:
    with pytest.raises(ValidationError):
        normalizado(tipo_id_fuente="ninguno", id_fuente="2-s2.0-1234")
    with pytest.raises(ValidationError):
        normalizado(tipo_id_fuente="eid", id_fuente=None)


def test_un_id_de_la_fuente_con_su_tipo_es_valido() -> None:
    registro = normalizado(tipo_id_fuente="eid", id_fuente="2-s2.0-1234")

    assert registro.tipo_id_fuente == "eid"
    assert registro.id_fuente == "2-s2.0-1234"


def test_construir_registros_asigna_ids_consecutivos_desde_uno() -> None:
    normalizados = [normalizado(posicion=1), normalizado(posicion=7), normalizado(posicion=9)]

    registros = construir_registros("imp-0003", normalizados)

    assert [r.id for r in registros] == ["imp-0003-00001", "imp-0003-00002", "imp-0003-00003"]
    assert {r.id_importacion for r in registros} == {"imp-0003"}
    # La posición en el archivo original no cambia.
    assert [r.posicion for r in registros] == [1, 7, 9]


def test_construir_registros_conserva_los_campos_del_normalizado() -> None:
    original = normalizado(otros={"Z9": "3"}, tipo_id_fuente="ut", id_fuente="WOS:001")

    (registro,) = construir_registros("imp-0001", [original])

    assert registro.model_dump(exclude={"id", "id_importacion"}) == original.model_dump()


def test_el_limite_de_posicion_es_de_cinco_digitos() -> None:
    assert LIMITE_POSICION == 99_999
    assert formatear_id_registro("imp-0001", 99_999) == "imp-0001-99999"
    with pytest.raises(LimiteDePosicionExcedido, match="99999"):
        formatear_id_registro("imp-0001", 100_000)


def test_la_posicion_del_id_empieza_en_uno() -> None:
    with pytest.raises(ValueError, match="empieza en 1"):
        formatear_id_registro("imp-0001", 0)


def test_construir_registros_falla_al_superar_el_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modelo, "LIMITE_POSICION", 2)

    with pytest.raises(LimiteDePosicionExcedido):
        construir_registros("imp-0001", [normalizado(), normalizado(), normalizado()])


@pytest.mark.parametrize(
    ("id_registro", "id_importacion"),
    [
        ("imp-0001-1", "imp-0001"),  # posición con menos de cinco dígitos
        ("imp-0001-100000", "imp-0001"),  # seis dígitos
        ("imp-0001-00000", "imp-0001"),  # la posición empieza en 1
        ("imp-0002-00001", "imp-0001"),  # otra importación
        ("registro-1", "imp-0001"),
        ("imp-0001-00001", "importacion-1"),
    ],
)
def test_ids_con_forma_invalida_se_rechazan(id_registro: str, id_importacion: str) -> None:
    with pytest.raises(ValidationError):
        Registro(
            **normalizado().model_dump(),
            id=id_registro,
            id_importacion=id_importacion,
        )
