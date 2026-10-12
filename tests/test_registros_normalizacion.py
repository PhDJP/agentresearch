"""Pruebas de la normalización de texto y de DOI (datos sintéticos).

El prefijo `10.5555` es el que se usa en documentación y pruebas: no pertenece a
ningún editor real.
"""

from typing import Any

import pytest

from agentresearch.registros import (
    VERSION_NORMALIZACION,
    RegistroNormalizado,
    normalizar_doi,
    normalizar_texto,
    normalizar_texto_opcional,
)

SICI = "10.5555/(SICI)1097-4571(199806)49:6<517::AID-ASI4>3.0.CO;2-8"


def test_la_version_de_la_normalizacion_empieza_en_uno() -> None:
    assert VERSION_NORMALIZACION == 1


# --------------------------------------------------------------------- texto


def test_unicode_se_lleva_a_nfc() -> None:
    descompuesto = "Café de Colombia"  # e + acento combinante

    assert normalizar_texto(descompuesto) == "Café de Colombia"


def test_espacios_duros_y_saltos_de_linea_pasan_a_un_espacio() -> None:
    assert normalizar_texto("  uno   dos\n\n\ttres cuatro  ") == "uno dos tres cuatro"


def test_normalizar_texto_es_idempotente() -> None:
    texto = "  Teórico  de \n la época  "

    una_vez = normalizar_texto(texto)

    assert normalizar_texto(una_vez) == una_vez


def test_un_texto_vacio_o_de_espacios_pasa_a_none() -> None:
    assert normalizar_texto_opcional("  \n  ") is None
    assert normalizar_texto_opcional(None) is None
    assert normalizar_texto_opcional(" a  b ") == "a b"


# ----------------------------------------------------------------------- DOI


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        # Forma básica y prefijos.
        ("10.5555/ABC", "10.5555/abc"),
        ("doi:10.5555/AbC", "10.5555/abc"),
        ("DOI: 10.5555/abc", "10.5555/abc"),
        ("https://doi.org/10.5555/AbC", "10.5555/abc"),
        ("http://dx.doi.org/10.5555/abc", "10.5555/abc"),
        ("doi.org/10.5555/abc", "10.5555/abc"),
        # Proxy de la biblioteca: en el servidor y en la consulta.
        ("https://doi-org.biblioteca.example.edu/10.5555/abc", "10.5555/abc"),
        ("https://biblioteca.example.edu/login?url=https://doi.org/10.5555/abc", "10.5555/abc"),
        # Consulta, fragmento y codificación porcentual.
        ("https://doi.org/10.5555/abc?casa_token=XYZ", "10.5555/abc"),
        ("https://doi.org/10.5555/abc#seccion", "10.5555/abc"),
        ("https://doi.org/10.5555%2Fabc", "10.5555/abc"),
        # Puntuación final.
        ("10.5555/abc.", "10.5555/abc"),
        ("doi:10.5555/abc,", "10.5555/abc"),
        ("10.5555/abc;", "10.5555/abc"),
        ("10.5555/abc.;", "10.5555/abc"),
        # Subdivisión del registrante.
        ("10.1000.10/ABC", "10.1000.10/abc"),
        # Solo las letras ASCII pasan a minúsculas.
        ("10.5555/ÁBC", "10.5555/Ábc"),
        # Cierres finales sin su apertura, en texto libre.
        ("(doi:10.5555/abc)", "10.5555/abc"),
        ("(doi:10.5555/abc).", "10.5555/abc"),
        ("[10.5555/abc]", "10.5555/abc"),
        ("<https://doi.org/10.5555/abc>", "10.5555/abc"),
        ('"10.5555/abc"', "10.5555/abc"),
        ("“10.5555/abc”", "10.5555/abc"),
        ("'10.5555/abc'", "10.5555/abc"),
        ("ver (10.5555/(abc)) aquí", "10.5555/(abc)"),
        # Paréntesis balanceados: se conserva (tipo SICI), solo o dentro de texto libre.
        (SICI, SICI.lower()),
        (f"doi:{SICI}", SICI.lower()),
        (f"({SICI})", SICI.lower()),
        (f"ver {SICI}.", SICI.lower()),
        ("doi:10.5555/abc(def)", "10.5555/abc(def)"),
        # Un DOI solo (sin texto alrededor) conserva sus cierres.
        ("10.5555/abc)", "10.5555/abc)"),
        # `#` y `?` codificados son parte del DOI; solo los literales abren fragmento y consulta.
        ("https://doi.org/10.5555/a%23b", "10.5555/a#b"),
        ("https://doi.org/10.5555/a%3Fb", "10.5555/a?b"),
        ("https://doi.org/10.5555/a%3fb", "10.5555/a?b"),
        ("https://doi.org/10.5555/a%23b?x=1", "10.5555/a#b"),
        ("https://doi.org/10.5555/a%3Fb#seccion", "10.5555/a?b"),
        ("https://doi.org/10.5555%2Fa%23b%3Fc", "10.5555/a#b?c"),
        # Una barra final de una URL se quita; la de un DOI suelto se conserva.
        ("https://doi.org/10.5555/abc/", "10.5555/abc"),
        ("https://doi.org/10.5555/abc/?utm=1", "10.5555/abc"),
        ("https://doi.org/10.5555/abc//", "10.5555/abc"),
        ("10.5555/abc/", "10.5555/abc/"),
    ],
)
def test_normalizar_doi(entrada: str, esperado: str) -> None:
    assert normalizar_doi(entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        "",
        "   ",
        "sin doi aquí",
        "10.55/abc",  # registrante demasiado corto
        "110.5555/abc",  # precedido por un dígito
        "10.5555/",
        "10.5555/.",
        "https://example.org/pagina",
    ],
)
def test_un_texto_sin_doi_da_none(entrada: str | None) -> None:
    assert normalizar_doi(entrada) is None


@pytest.mark.parametrize(
    "entrada",
    [
        "10.5555/ABC",
        "(doi:10.5555/abc).",
        f"({SICI})",
        "https://doi.org/10.5555%2Fabc?x=1",
        "https://doi.org/10.5555/a%23b",
        "https://doi.org/10.5555/abc/",
    ],
)
def test_normalizar_doi_es_idempotente(entrada: str) -> None:
    una_vez = normalizar_doi(entrada)

    assert normalizar_doi(una_vez) == una_vez


def test_el_doi_se_normaliza_tambien_con_espacios_y_nfc_previos() -> None:
    assert normalizar_doi("  doi: 10.5555/ABC \n") == "10.5555/abc"


# ----------------------------------------------- aplicada por el modelo


def _registro(**cambios: Any) -> RegistroNormalizado:
    datos: dict[str, Any] = {
        "fuente": "fuente-a",
        "formato": "csv",
        "archivo": "a.csv",
        "posicion": 3,
    }
    datos.update(cambios)
    return RegistroNormalizado(**datos)


def test_el_modelo_normaliza_los_campos_de_texto() -> None:
    registro = _registro(
        titulo="  Estudio   de\nmieles ",
        fuente_publicacion="Revista Ficticia",
        resumen="Primer párrafo.\n\nSegundo   párrafo.",
        doi="https://doi.org/10.5555/ABC",
    )

    assert registro.titulo == "Estudio de mieles"
    assert registro.fuente_publicacion == "Revista Ficticia"
    assert registro.resumen == "Primer párrafo. Segundo párrafo."
    assert registro.doi == "10.5555/abc"


def test_un_texto_vacio_pasa_a_none_en_el_modelo() -> None:
    registro = _registro(titulo="   ", volumen="\n", doi="sin doi")

    assert registro.titulo is None
    assert registro.volumen is None
    assert registro.doi is None


def test_el_modelo_descarta_las_entradas_vacias_de_listas_y_otros() -> None:
    registro = _registro(
        autores=("  Pérez, Ana ", "", "   ", "Gómez, Luis"),
        palabras_clave_autor=("miel", " "),
        otros={" N1 ": "  nota \n larga ", "N2": "  ", "": "x"},
    )

    assert registro.autores == ("Pérez, Ana", "Gómez, Luis")
    assert registro.palabras_clave_autor == ("miel",)
    assert registro.otros == {"N1": "nota larga"}


def test_un_id_de_la_fuente_vacio_con_tipo_se_rechaza() -> None:
    """El texto vacío pasa a None y entonces falta el identificador que el tipo exige."""
    with pytest.raises(ValueError, match="id_fuente"):
        _registro(tipo_id_fuente="eid", id_fuente="  ")


def test_normalizar_un_registro_ya_normalizado_no_lo_cambia() -> None:
    registro = _registro(
        titulo="  Título  con  espacios ",
        doi="(doi:10.5555/ABC)",
        autores=("A,  B",),
        otros={"X": " y  z "},
    )

    otra_vez = RegistroNormalizado(**registro.model_dump())

    assert otra_vez == registro


def test_una_url_entre_signos_tambien_pierde_su_consulta() -> None:
    assert normalizar_doi("<https://doi.org/10.5555/abc?casa_token=XYZ>") == "10.5555/abc"


# ---------------------------------- id_fuente de tipo doi (se normaliza como DOI)


@pytest.mark.parametrize(
    ("id_fuente", "esperado"),
    [
        ("10.1021/ACS.X", "10.1021/acs.x"),
        ("doi:10.1021/ACS.X", "10.1021/acs.x"),
        ("https://doi.org/10.1021/ACS.X", "10.1021/acs.x"),
        ("  10.1021/ACS.X \n", "10.1021/acs.x"),
        # Sin DOI dentro, queda como texto normalizado.
        ("  no es un   doi ", "no es un doi"),
    ],
)
def test_el_id_de_la_fuente_de_tipo_doi_se_normaliza_como_doi(
    id_fuente: str, esperado: str
) -> None:
    registro = _registro(tipo_id_fuente="doi", id_fuente=id_fuente)

    assert registro.id_fuente == esperado


def test_el_id_de_la_fuente_de_tipo_doi_coincide_con_el_campo_doi() -> None:
    registro = _registro(
        tipo_id_fuente="doi", id_fuente="10.1021/ACS.X", doi="https://doi.org/10.1021/acs.x"
    )

    assert registro.id_fuente == registro.doi == "10.1021/acs.x"


@pytest.mark.parametrize(
    ("tipo", "id_fuente"),
    [("eid", "2-S2.0-ABC"), ("ut", "WOS:000AB"), ("pmid", "123"), ("lens_id", "000-AAA-111")],
)
def test_los_demas_identificadores_solo_se_normalizan_como_texto(tipo: str, id_fuente: str) -> None:
    registro = _registro(tipo_id_fuente=tipo, id_fuente=f"  {id_fuente}  ")

    assert registro.id_fuente == id_fuente  # sin minúsculas ni extracción de DOI


def test_dos_formas_del_mismo_doi_como_id_de_la_fuente_dan_el_mismo_hash() -> None:
    mayusculas = _registro(tipo_id_fuente="doi", id_fuente="10.1021/ACS.X")
    minusculas = _registro(tipo_id_fuente="doi", id_fuente="doi:10.1021/acs.x")

    assert mayusculas.hash_completo == minusculas.hash_completo
