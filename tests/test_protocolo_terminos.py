"""Pruebas de la gramática de términos de búsqueda y de las variantes (ADR-0009, puntos 1 a 3)."""

from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo import validar_archivo
from agentresearch.protocolo.archivo import (
    actualizar_documento,
    decodificar_protocolo,
    texto_protocolo,
)
from agentresearch.protocolo.terminos import (
    Palabra,
    TerminoNoValido,
    analizar_termino,
    problemas_de_variantes,
)

from .apoyo import reemplazar_en

# --- Análisis de un término -----------------------------------------------------------


def test_una_palabra() -> None:
    termino = analizar_termino("secado")

    assert termino.palabras == (Palabra("secado", truncada=False),)
    assert not termino.entre_comillas
    assert not termino.truncado
    assert not termino.es_frase
    assert str(termino) == "secado"


def test_una_palabra_truncada() -> None:
    termino = analizar_termino("dehydrat*")

    assert termino.palabras == (Palabra("dehydrat", truncada=True),)
    assert termino.truncado
    assert str(termino) == "dehydrat*"


def test_una_frase_con_truncamiento() -> None:
    termino = analizar_termino('  "hemp  seed*" ')

    assert termino.entre_comillas
    assert termino.es_frase
    assert termino.palabras == (Palabra("hemp", False), Palabra("seed", True))
    assert termino.texto == "hemp seed*"
    assert str(termino) == '"hemp seed*"'
    assert termino.original == '  "hemp  seed*" '


def test_una_palabra_sola_entre_comillas_es_exacta() -> None:
    termino = analizar_termino('"CBD"')

    assert termino.entre_comillas
    assert not termino.es_frase
    assert str(termino) == '"CBD"'


@pytest.mark.parametrize(
    ("texto", "raiz"),
    [("by-product", "product"), ("farmer's", "s"), ("farmer’s", "s"), ("secado", "secado")],
)
def test_la_raiz_es_la_parte_tras_el_ultimo_separador(texto: str, raiz: str) -> None:
    [palabra] = analizar_termino(texto).palabras

    assert palabra.raiz == raiz
    assert palabra.tiene_separador == (texto != "secado")


def test_tildes_y_guiones() -> None:
    assert analizar_termino("liofilización").tiene_tilde
    assert analizar_termino("β-zarambina").tiene_tilde
    assert not analizar_termino("drying").tiene_tilde
    assert analizar_termino("post-extraction").tiene_guion
    assert not analizar_termino('"hemp seed"').tiene_guion


@pytest.mark.parametrize(
    ("texto", "fragmento"),
    [
        ("", "vacío"),
        ("fruto seco", "varias palabras sin comillas"),
        ('"fruto" seco', "rodear el término completo"),
        ('"fruto "seco"', "rodear el término completo"),
        ('" "', "comillas están vacías"),
        ("AND", "operador de búsqueda"),
        ('"salt Or pepper"', "operador de búsqueda"),
        ("TS=secado", "sintaxis propia de una fuente"),
        ("secado[tiab]", "sintaxis propia de una fuente"),
        ("{secado}", "sintaxis propia de una fuente"),
        ("colo$r", r"comodín \$"),
        ("wom?n", "comodín ?"),
        ("*secado", "al inicio o en medio"),
        ("sec*ado", "al inicio o en medio"),
        ("secado**", "al inicio o en medio"),
        ("*", "debe seguir a una palabra"),
        ("by-*", "guion o un apóstrofo al inicio o al final"),
        ("'secado", "guion o un apóstrofo al inicio o al final"),
        ("by--product", "dos separadores seguidos"),
        ("secado,", "contiene el carácter ','"),
    ],
)
def test_terminos_no_validos(texto: str, fragmento: str) -> None:
    with pytest.raises(TerminoNoValido, match=fragmento):
        analizar_termino(texto)


# --- Variantes ------------------------------------------------------------------------


def test_variantes_validas_no_tienen_problemas() -> None:
    assert (
        problemas_de_variantes(
            ["secado", "dehydrat*", '"hemp seed*"'],
            {"dehydrat*": ["dehydration"], '"hemp seed*"': ['"hemp seed"', '"hemp seeds"']},
        )
        == []
    )


def test_problemas_de_variantes() -> None:
    problemas = problemas_de_variantes(
        ["secado", "dehydrat*", "fruto seco"],
        {
            "secado": ["secados"],
            "fruto seco": ["frutos"],
            "dehydrat*": ["dehydration", "dehyd*", "sec?do"],
        },
    )

    assert problemas == [
        ("secado", "la clave 'secado' no es un término truncado de este bloque"),
        ("fruto seco", "la clave 'fruto seco' no es un término truncado de este bloque"),
        ("dehydrat*", "la variante 'dehyd*' de 'dehydrat*' no puede llevar *"),
        (
            "dehydrat*",
            "la variante 'sec?do' de 'dehydrat*': «sec?do» usa el comodín ?, que no todas las "
            "fuentes admiten; solo se admite el truncamiento final con *",
        ),
    ]


# --- P-E11 en el protocolo ------------------------------------------------------------


def test_p_e11_nombra_el_bloque_y_la_ubicacion(protocolo_de_estudio: Path) -> None:
    reemplazar_en(protocolo_de_estudio, '"dehydrat*"', '"dehydrat*", "fruto seco"')

    [hallazgo] = [h for h in validar_archivo(protocolo_de_estudio).errores if h.id_regla == "P-E11"]

    assert hallazgo.ubicacion == "busqueda.bloques[1].terminos[3]"
    assert hallazgo.linea is not None
    assert hallazgo.mensaje.startswith(
        "el término 'fruto seco' del bloque B2 no se puede traducir: tiene varias palabras"
    )
    assert "ADR-0009" in hallazgo.referencia


def test_las_variantes_se_leen_y_escriben_conservando_los_comentarios(
    protocolo_de_estudio: Path,
) -> None:
    documento = decodificar_protocolo(protocolo_de_estudio.read_bytes())
    nuevo = documento.protocolo.model_copy(deep=True)
    nuevo.busqueda.bloques[1].variantes = {"dehydrat*": ["dehydration", "dehydrated"]}

    actualizar_documento(documento, nuevo)
    texto = texto_protocolo(documento)
    releido = decodificar_protocolo(texto.encode("utf-8"))

    assert releido.protocolo.busqueda.bloques[1].variantes == {
        "dehydrat*": ["dehydration", "dehydrated"]
    }
    assert texto.startswith("# Protocolo sintético para pruebas.")
    assert "variantes:\n        dehydrat*: [dehydration, dehydrated]\n" in texto


def test_un_bloque_sin_variantes_no_las_escribe(datos_sinteticos: dict[str, Any]) -> None:
    assert "variantes" not in datos_sinteticos["busqueda"]["bloques"][1]
