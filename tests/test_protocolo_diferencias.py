"""Pruebas del diff estructural del protocolo (ADR-0008, punto 13)."""

import copy
from typing import Any

from agentresearch.protocolo import Protocolo
from agentresearch.protocolo.diferencias import Cambio, diferencias, diferencias_protocolo


def _diff(antes: dict[str, Any], despues: dict[str, Any]) -> list[Cambio]:
    return diferencias_protocolo(Protocolo.model_validate(antes), Protocolo.model_validate(despues))


def test_sin_cambios_no_hay_diferencias(datos_sinteticos: dict[str, Any]) -> None:
    assert _diff(datos_sinteticos, copy.deepcopy(datos_sinteticos)) == []


def test_un_valor_por_defecto_explicito_no_es_un_cambio(datos_sinteticos: dict[str, Any]) -> None:
    antes = copy.deepcopy(datos_sinteticos)
    del antes["marco"]["pcc"]["contexto"]["restrictivo"]
    del antes["metadatos"]["autores"][0]["orcid"]

    assert _diff(antes, datos_sinteticos) == []


def test_texto_modificado_en_un_criterio_se_ubica_por_su_id(
    datos_sinteticos: dict[str, Any],
) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    texto_anterior = despues["criterios"]["inclusion"][0]["texto"]
    despues["criterios"]["inclusion"][0]["texto"] = "Texto nuevo del criterio"

    assert _diff(datos_sinteticos, despues) == [
        Cambio(
            "criterios.inclusion[CI1].texto",
            "modificado",
            texto_anterior,
            "Texto nuevo del criterio",
        )
    ]


def test_criterio_agregado_y_eliminado(datos_sinteticos: dict[str, Any]) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    eliminado = despues["criterios"]["exclusion"].pop(0)
    nuevo = {"id": "CE9", "texto": "Nuevo", "fase": "ambas", "tipo": "otro"}
    despues["criterios"]["exclusion"].append(nuevo)

    cambios = _diff(datos_sinteticos, despues)

    assert [(c.ruta, c.operacion) for c in cambios] == [
        (f"criterios.exclusion[{eliminado['id']}]", "eliminado"),
        ("criterios.exclusion[CE9]", "agregado"),
    ]
    assert cambios[0].antes["texto"] == eliminado["texto"]
    assert cambios[0].despues is None
    assert cambios[1].antes is None
    assert cambios[1].despues == {**nuevo, "ejemplos_si": [], "ejemplos_no": []}


def test_reordenar_elementos_con_id_se_reporta_una_vez(datos_sinteticos: dict[str, Any]) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    preguntas = despues["preguntas"]
    preguntas[0], preguntas[1] = preguntas[1], preguntas[0]

    assert _diff(datos_sinteticos, despues) == [
        Cambio("preguntas", "reordenado", ["PI1", "PI2", "PI3"], ["PI2", "PI1", "PI3"])
    ]


def test_termino_agregado_incluye_agregados_y_eliminados(
    datos_sinteticos: dict[str, Any],
) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    antes_terminos = list(despues["busqueda"]["bloques"][0]["terminos"])
    despues["busqueda"]["bloques"][0]["terminos"].append("fruto de zarambo")

    [cambio] = _diff(datos_sinteticos, despues)

    assert cambio.ruta == "busqueda.bloques[B1].terminos"
    assert cambio.operacion == "modificado"
    assert cambio.antes == antes_terminos
    assert cambio.despues == [*antes_terminos, "fruto de zarambo"]
    assert cambio.agregados == ["fruto de zarambo"]
    assert cambio.eliminados == []


def test_termino_reemplazado_en_una_lista_de_escalares() -> None:
    [cambio] = diferencias({"t": ["a", "b", "c"]}, {"t": ["a", "x", "c"]})

    assert cambio.agregados == ["x"]
    assert cambio.eliminados == ["b"]


def test_lista_de_escalares_solo_reordenada() -> None:
    [cambio] = diferencias({"t": ["a", "b"]}, {"t": ["b", "a"]})

    assert cambio.operacion == "modificado"
    assert cambio.agregados == []
    assert cambio.eliminados == []


def test_lista_de_escalares_cuenta_repeticiones_como_multiconjunto() -> None:
    [cambio] = diferencias({"t": ["a", "a", "b"]}, {"t": ["a", "b", "b"]})

    assert cambio.agregados == ["b"]
    assert cambio.eliminados == ["a"]


def test_lista_de_escalares_no_confunde_true_con_uno() -> None:
    [cambio] = diferencias({"t": [True]}, {"t": [1]})

    assert cambio.agregados == [1]
    assert cambio.eliminados == [True]


def test_listas_sin_id_se_comparan_por_posicion(datos_sinteticos: dict[str, Any]) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    despues["metadatos"]["autores"][0]["nombre"] = "Otra Persona"
    despues["metadatos"]["autores"].append({"nombre": "Tercera", "orcid": "", "rol": ""})

    cambios = _diff(datos_sinteticos, despues)

    assert [(c.ruta, c.operacion) for c in cambios] == [
        ("metadatos.autores[0].nombre", "modificado"),
        ("metadatos.autores[2]", "agregado"),
    ]


def test_elemento_eliminado_de_una_lista_sin_id() -> None:
    cambios = diferencias({"a": [{"x": 1}, {"x": 2}]}, {"a": [{"x": 1}]})

    assert cambios == [Cambio("a[1]", "eliminado", {"x": 2}, None)]


def test_cruce_agregado_y_modificado(datos_sinteticos: dict[str, Any]) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    despues["analisis"]["cruces"][0] = ["F1", "DE1"]
    despues["analisis"]["cruces"].append(["F2", "DE1"])

    cambios = _diff(datos_sinteticos, despues)

    assert [(c.ruta, c.operacion) for c in cambios] == [
        ("analisis.cruces[0]", "modificado"),
        ("analisis.cruces[1]", "agregado"),
    ]
    assert cambios[0].agregados == ["DE1"]


def test_valores_nulos_booleanos_y_numericos(datos_sinteticos: dict[str, Any]) -> None:
    despues = copy.deepcopy(datos_sinteticos)
    despues["busqueda"]["periodo"]["desde"] = 1990
    despues["marco"]["pcc"]["contexto"]["restrictivo"] = True
    despues["seleccion"]["piloto"]["umbral_kappa"] = 0.7

    cambios = {c.ruta: c for c in _diff(datos_sinteticos, despues)}

    assert (
        cambios["busqueda.periodo.desde"].antes == datos_sinteticos["busqueda"]["periodo"]["desde"]
    )
    assert cambios["busqueda.periodo.desde"].despues == 1990
    assert cambios["marco.pcc.contexto.restrictivo"].despues is True
    assert cambios["seleccion.piloto.umbral_kappa"].despues == 0.7


def test_uno_y_uno_punto_cero_son_iguales_pero_true_y_uno_no() -> None:
    assert diferencias({"k": 1}, {"k": 1.0}) == []
    assert diferencias({"k": True}, {"k": 1}) == [Cambio("k", "modificado", True, 1)]
    assert diferencias({"k": None}, {"k": ""}) == [Cambio("k", "modificado", None, "")]


def test_claves_agregadas_y_eliminadas_en_un_mapa() -> None:
    cambios = diferencias({"a": 1, "b": 2}, {"a": 1, "c": 3})

    assert cambios == [Cambio("b", "eliminado", 2, None), Cambio("c", "agregado", None, 3)]


def test_cambio_de_tipo_es_una_modificacion() -> None:
    assert diferencias({"a": {"x": 1}}, {"a": [1]}) == [Cambio("a", "modificado", {"x": 1}, [1])]


def test_lista_vacia_que_pasa_a_tener_elementos_con_id() -> None:
    cambios = diferencias({"l": []}, {"l": [{"id": "X1"}]})

    assert cambios == [Cambio("l[X1]", "agregado", None, {"id": "X1"})]


def test_ids_repetidos_se_comparan_por_posicion() -> None:
    cambios = diferencias(
        {"l": [{"id": "A", "v": 1}, {"id": "A", "v": 2}]},
        {"l": [{"id": "A", "v": 1}, {"id": "A", "v": 3}]},
    )

    assert cambios == [Cambio("l[1].v", "modificado", 2, 3)]


def test_como_dict_solo_incluye_agregados_en_listas_de_escalares() -> None:
    escalar = Cambio("t", "modificado", ["a"], ["b"], agregados=["b"], eliminados=["a"])
    simple = Cambio("k", "modificado", 1, 2)

    assert escalar.como_dict() == {
        "ruta": "t",
        "operacion": "modificado",
        "antes": ["a"],
        "despues": ["b"],
        "agregados": ["b"],
        "eliminados": ["a"],
    }
    assert simple.como_dict() == {"ruta": "k", "operacion": "modificado", "antes": 1, "despues": 2}


def test_texto_de_cada_operacion() -> None:
    assert str(Cambio("k", "modificado", "á", "b")) == 'k: "á" → "b"'
    assert str(Cambio("l[X1]", "agregado", None, {"id": "X1"})) == 'l[X1]: agregado {"id": "X1"}'
    assert str(Cambio("l[X1]", "eliminado", {"id": "X1"}, None)) == 'l[X1]: eliminado {"id": "X1"}'
    assert str(Cambio("l", "reordenado", ["A", "B"], ["B", "A"])) == (
        'l: reordenado ["A", "B"] → ["B", "A"]'
    )
    assert str(Cambio("t", "modificado", ["a"], ["b"], agregados=["b"], eliminados=["a"])) == (
        't: ["a"] → ["b"] (agregados: ["b"]; eliminados: ["a"])'
    )
