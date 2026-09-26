"""Pruebas del modelo pydantic del protocolo (versión de esquema 1)."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentresearch.protocolo import VERSION_ESQUEMA, Protocolo


def test_el_protocolo_sintetico_cumple_el_esquema(datos_sinteticos: dict[str, Any]) -> None:
    protocolo = Protocolo.model_validate(datos_sinteticos)

    assert protocolo.version_esquema == VERSION_ESQUEMA
    assert protocolo.estado == "borrador"
    assert [p.id for p in protocolo.preguntas] == ["PI1", "PI2", "PI3"]
    assert protocolo.preguntas[2].derivada_de == [["F1", "F2"]]
    assert protocolo.seleccion.piloto.umbral_kappa == pytest.approx(0.61)
    assert protocolo.busqueda.periodo.hasta is None


def test_la_version_de_esquema_es_uno() -> None:
    assert VERSION_ESQUEMA == 1


def test_rechaza_una_clave_desconocida(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["criterio"] = []

    with pytest.raises(ValidationError, match="criterio"):
        Protocolo.model_validate(datos_sinteticos)


def test_rechaza_una_clave_desconocida_anidada(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["criterios"]["inclusion"][0]["faze"] = "ambas"

    with pytest.raises(ValidationError, match="faze"):
        Protocolo.model_validate(datos_sinteticos)


def test_rechaza_una_seccion_obligatoria_ausente(datos_sinteticos: dict[str, Any]) -> None:
    del datos_sinteticos["seleccion"]

    with pytest.raises(ValidationError, match="seleccion"):
        Protocolo.model_validate(datos_sinteticos)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (("estado",), "aprobado"),
        (("version_esquema",), 2),
        (("seleccion", "regla_combinacion", "avanzan"), ["A", "G"]),
        (("seleccion", "revisores", 0, "tipo"), "persona"),
        (("busqueda", "bloques", 0, "componente"), "intervencion"),
        (("criterios", "inclusion", 0, "tipo"), "empirico"),
        (("criterios", "inclusion", 0, "fase"), "resumen"),
        (("estrategias", "bola_de_nieve", "direcciones"), ["arriba"]),
    ],
)
def test_rechaza_valores_fuera_de_la_enumeracion(
    datos_sinteticos: dict[str, Any], ruta: tuple[str | int, ...], valor: object
) -> None:
    _asignar(datos_sinteticos, ruta, valor)

    with pytest.raises(ValidationError):
        Protocolo.model_validate(datos_sinteticos)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (("seleccion", "tamano_lote_llm"), "25"),
        (("seleccion", "tamano_lote_llm"), 2.5),
        (("seleccion", "piloto", "umbral_kappa"), "0,61"),
        (("busqueda", "periodo", "desde"), "2000"),
        (("metadatos", "titulo"), 123),
        (("estrategias", "bases_de_datos", "activa"), "si"),
    ],
)
def test_no_convierte_tipos_de_forma_implicita(
    datos_sinteticos: dict[str, Any], ruta: tuple[str | int, ...], valor: object
) -> None:
    _asignar(datos_sinteticos, ruta, valor)

    with pytest.raises(ValidationError):
        Protocolo.model_validate(datos_sinteticos)


def test_acepta_un_entero_como_umbral_kappa(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["seleccion"]["piloto"]["umbral_kappa"] = 1

    protocolo = Protocolo.model_validate(datos_sinteticos)

    assert protocolo.seleccion.piloto.umbral_kappa == 1.0


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0-beta", ""])
def test_rechaza_una_version_de_protocolo_no_semantica(
    datos_sinteticos: dict[str, Any], version: str
) -> None:
    datos_sinteticos["metadatos"]["version_protocolo"] = version

    with pytest.raises(ValidationError, match="version_protocolo"):
        Protocolo.model_validate(datos_sinteticos)


def test_rechaza_un_cruce_de_un_solo_elemento(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["analisis"]["cruces"] = [["F1"]]

    with pytest.raises(ValidationError, match="cruces"):
        Protocolo.model_validate(datos_sinteticos)


def test_los_campos_vigilados_por_reglas_son_opcionales(
    datos_sinteticos: dict[str, Any],
) -> None:
    """La ausencia de estos campos la reportan las reglas P-E, no el esquema."""
    del datos_sinteticos["criterios"]["inclusion"][0]["fase"]
    del datos_sinteticos["preguntas"][0]["responde_con"]
    del datos_sinteticos["preguntas"][2]["derivada_de"]
    categoria = datos_sinteticos["extraccion"]["facetas"][0]["categorias"][0]
    del categoria["definicion"], categoria["regla"], categoria["ejemplos"]

    protocolo = Protocolo.model_validate(datos_sinteticos)

    assert protocolo.criterios.inclusion[0].fase is None
    assert protocolo.preguntas[0].responde_con == []
    assert protocolo.preguntas[2].derivada_de == []
    assert protocolo.extraccion.facetas[0].categorias[0].definicion == ""


def test_acepta_textos_vacios_de_un_borrador(datos_sinteticos: dict[str, Any]) -> None:
    datos_sinteticos["justificacion"] = ""
    datos_sinteticos["marco"]["pcc"]["poblacion"]["descripcion"] = ""
    datos_sinteticos["busqueda"]["bloques"] = []

    protocolo = Protocolo.model_validate(datos_sinteticos)

    assert protocolo.justificacion == ""
    assert protocolo.busqueda.bloques == []


def _asignar(datos: dict[str, Any], ruta: tuple[str | int, ...], valor: object) -> None:
    """Asigna `valor` en la posición anidada `ruta` de `datos`."""
    contenedor: Any = datos
    for clave in ruta[:-1]:
        contenedor = contenedor[clave]
    contenedor[ruta[-1]] = valor
