"""Pruebas del lector de BibTeX (todo sintético; tema ficticio)."""

from pathlib import Path

import pytest

from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.importacion.servicio import formatos_disponibles, leer

from .apoyo_importacion import escribir

ENTRADA = """@article{Cristal2024,
  author = {Cristal, Ana and Vidrio, Beatriz Carla},
  title = {Abejas de cristal y su miel},
  journal = {Revista de Abejas},
  year = {2024},
  volume = {12},
  number = {3},
  pages = {},
  doi = {10.5555/ABEJA.B1},
  abstract = {Resumen ficticio sobre abejas.},
  author_keywords = {miel; cristal},
  keywords = {néctar; colmena},
  language = {English},
  type = {Article},
  pmid = {77777777},
  note = {Cited by: 4; All Open Access; Gold Open Access},
  url = {https://www.example.org/pages/publications/1},
  source = {Scopus},
}
"""


def _leer(
    tmp_path: Path,
    texto: str,
    fuente: str = "scopus",
    *,
    bom: bool = False,
    fin_de_linea: str = "\n",
) -> ResultadoLectura:
    ruta = escribir(tmp_path / "export.bib", texto, bom=bom, fin_de_linea=fin_de_linea)
    return leer(ruta, "bibtex", fuente)


def _reglas(resultado: ResultadoLectura) -> list[str]:
    return [h.regla for h in resultado.hallazgos]


def test_formato_disponible() -> None:
    assert "bibtex" in formatos_disponibles()


def test_entrada_completa_con_el_perfil_scopus(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, ENTRADA, bom=True)
    assert resultado.numero_registros == 1
    registro = resultado.registros[0]
    assert registro.formato == "bibtex"
    assert registro.posicion == 1
    assert registro.titulo == "Abejas de cristal y su miel"
    assert registro.autores == ("Cristal, Ana", "Vidrio, Beatriz Carla")
    assert registro.anio == 2024
    assert registro.fuente_publicacion == "Revista de Abejas"
    assert (registro.volumen, registro.numero) == ("12", "3")
    assert registro.paginas is None
    assert registro.doi == "10.5555/abeja.b1"
    assert registro.resumen == "Resumen ficticio sobre abejas."
    assert registro.palabras_clave_autor == ("miel", "cristal")
    assert registro.palabras_clave_indexadas == ("néctar", "colmena")
    assert registro.idioma == "English"
    assert registro.tipo_documento == "Article"
    assert registro.pmid == "77777777"
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("ninguno", None)
    assert registro.otros["entry_type"] == "article"
    assert registro.otros["note"] == "All Open Access; Gold Open Access"
    assert registro.otros["source"] == "Scopus"
    assert "Cristal2024" not in registro.otros.values()
    assert "pages" not in registro.otros
    assert _reglas(resultado) == []
    assert resultado.cobertura["paginas"] == 0


def test_la_clave_y_el_conteo_de_citas_no_cambian_el_hash(tmp_path: Path) -> None:
    uno = _leer(tmp_path, ENTRADA).registros[0]
    otro = ENTRADA.replace("Cristal2024", "Cristal2024a").replace("Cited by: 4", "Cited by: 40")
    ruta = escribir(tmp_path / "otro.bib", otro)
    dos = leer(ruta, "bibtex", "scopus").registros[0]
    assert uno.hash_completo == dos.hash_completo


def test_nota_sin_el_conteo_y_solo_el_conteo(tmp_path: Path) -> None:
    solo = _leer(
        tmp_path, ENTRADA.replace("Cited by: 4; All Open Access; Gold Open Access", "Cited by: 4")
    )
    assert "note" not in solo.registros[0].otros
    sin = _leer(tmp_path, ENTRADA.replace("Cited by: 4; ", ""))
    assert sin.registros[0].otros["note"] == "All Open Access; Gold Open Access"


def test_tildes_de_latex(tmp_path: Path) -> None:
    texto = (
        "@article{k,\n"
        "  title = {Abejas {\\'e}ticas con {\\\"u}n y \\~{n}and\\'u y {\\o}},\n"
        "  author = {Mu{\\~n}oz, Jos{\\'e}},\n"
        "  year = {2020},\n  doi = {10.5555/x},\n  abstract = {r},\n}\n"
    )
    registro = _leer(tmp_path, texto).registros[0]
    assert registro.titulo == "Abejas éticas con ün y ñandú y ø"
    assert registro.autores == ("Muñoz, José",)


def test_string_y_concatenacion(tmp_path: Path) -> None:
    texto = (
        '@string{editorial = "Editorial Ficticia"}\n'
        "@STRING{lugar = {Ciudad Ficticia}}\n"
        "@article{k,\n"
        '  title = "Primera " # "parte " # {y segunda},\n'
        "  author = {A},\n"
        "  year = 2020,\n"
        "  doi = {10.5555/x},\n"
        "  abstract = {r},\n"
        '  note = editorial # ", " # LUGAR # " " # 2021,\n'
        "  publisher = editorial,\n"
        "  month = jan,\n"
        "}\n"
    )
    registro = _leer(tmp_path, texto, fuente="otra").registros[0]
    assert registro.titulo == "Primera parte y segunda"
    assert registro.anio == 2020
    assert registro.otros["note"] == "Editorial Ficticia, Ciudad Ficticia 2021"
    assert registro.otros["publisher"] == "Editorial Ficticia"
    assert registro.otros["month"] == "jan"


def test_porcentaje_ampersand_y_tilde_no_se_pierden(tmp_path: Path) -> None:
    texto = (
        "@article{k,\n  title = {Abejas {CO}2 al 50% y A & B ~ C},\n  author = {A},\n"
        "  year = {2020},\n  doi = {10.5555/x},\n  abstract = {r},\n}\n"
    )
    assert _leer(tmp_path, texto).registros[0].titulo == "Abejas CO2 al 50% y A & B ~ C"


def test_resumen_con_marcas_y_caracteres_no_ascii_y_espacio_duro(tmp_path: Path) -> None:
    texto = (
        "@article{k,\n  title = {T},\n  author = {A},\n  year = {2020},\n  doi = {10.5555/x},\n"
        "  abstract = {Nivel de CO<sub>2</sub> α ± 0.5\n  en dos líneas},\n}\n"
    )
    registro = _leer(tmp_path, texto).registros[0]
    assert registro.resumen == "Nivel de CO<sub>2</sub> α ± 0.5 en dos líneas"


def test_perfil_generico_no_asume_que_keywords_son_indexadas(tmp_path: Path) -> None:
    registro = _leer(tmp_path, ENTRADA, fuente="otra").registros[0]
    assert registro.palabras_clave_indexadas == ()
    assert registro.otros["keywords"] == "néctar; colmena"
    assert registro.palabras_clave_autor == ("miel", "cristal")
    assert "Cited by: 4" in registro.otros["note"]


def test_clave_repetida_se_recupera_se_cuenta_y_no_genera_hallazgo(tmp_path: Path) -> None:
    primera = ENTRADA
    repetida = ENTRADA.replace("10.5555/ABEJA.B1", "10.5555/ABEJA.B2").replace(
        "Abejas de cristal y su miel", "Otro título"
    )
    resultado = _leer(tmp_path, primera + "\n" + repetida)
    assert resultado.numero_registros == 2
    assert _reglas(resultado) == []
    segundo = resultado.registros[1]
    assert segundo.titulo == "Otro título"
    assert segundo.autores == ("Cristal, Ana", "Vidrio, Beatriz Carla")
    assert segundo.posicion == len(ENTRADA.splitlines()) + 2
    assert [r.doi for r in resultado.registros] == ["10.5555/abeja.b1", "10.5555/abeja.b2"]


def test_la_entrada_recuperada_conserva_el_orden_del_archivo(tmp_path: Path) -> None:
    otra = ENTRADA.replace("Cristal2024", "Vidrio2023").replace("10.5555/ABEJA.B1", "10.5555/Z")
    repetida = ENTRADA.replace("10.5555/ABEJA.B1", "10.5555/Y")
    resultado = _leer(tmp_path, ENTRADA + otra + repetida)
    assert [r.doi for r in resultado.registros] == ["10.5555/abeja.b1", "10.5555/z", "10.5555/y"]


def test_l_e02_campo_repetido_en_una_entrada(tmp_path: Path) -> None:
    mala = "@article{malo,\n  title = {Uno},\n  title = {Dos},\n  year = {2020},\n}\n"
    texto = (
        ENTRADA
        + mala
        + ENTRADA.replace("Cristal2024", "Otra2024").replace("10.5555/ABEJA.B1", "10.5555/OTRA")
    )
    resultado = _leer(tmp_path, texto)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [h.linea for h in errores] == [len(ENTRADA.splitlines()) + 1]
    assert "campo repetido" in errores[0].mensaje
    assert resultado.numero_registros == 2


@pytest.mark.parametrize("fin_de_linea", ["\n", "\r\n", "\r"])
def test_l_e02_la_linea_informada_es_la_linea_fisica_del_archivo(
    tmp_path: Path, fin_de_linea: str
) -> None:
    validas = "".join(
        ENTRADA.replace("Cristal2024", f"K{n}").replace("10.5555/ABEJA.B1", f"10.5555/{n}")
        for n in range(3)
    )
    malformada = '@article{malo,\n  title = {Sin cierre\n  year = "2020"\n'
    texto = validas + malformada
    lineas = texto.splitlines()
    esperada = next(i for i, linea in enumerate(lineas, 1) if linea.startswith("@article{malo"))
    resultado = _leer(tmp_path, texto, fin_de_linea=fin_de_linea)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [h.linea for h in errores] == [esperada]
    assert errores[0].severidad == "error"
    assert resultado.numero_registros == 3
    assert [r.posicion for r in resultado.registros] == [
        1 + n * len(ENTRADA.splitlines()) for n in range(3)
    ]


def test_ningun_aviso_de_la_biblioteca_llega_a_la_terminal(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    malo = '@article{malo,\n  title = {Sin cierre\n  year = "2020"\n'
    repetida = ENTRADA + ENTRADA + "@article{dup,\n title={a},\n title={b}\n}\n"
    _leer(tmp_path, repetida + malo)
    capturado = capfd.readouterr()
    assert capturado.err == ""
    assert capturado.out == ""


def test_se_restaura_el_registrador_de_la_biblioteca(tmp_path: Path) -> None:
    import logging

    registro = logging.getLogger("bibtexparser")
    antes = (list(registro.handlers), registro.propagate)
    _leer(tmp_path, ENTRADA + "@article{malo,\n  title = {Sin cierre\n")
    assert (list(registro.handlers), registro.propagate) == antes


def test_l_a04_l_a02_l_a01_y_l_a05(tmp_path: Path) -> None:
    sin_resumen = ENTRADA.replace("  abstract = {Resumen ficticio sobre abejas.},\n", "")
    assert [h.regla for h in _leer(tmp_path, sin_resumen).hallazgos] == ["L-A04"]
    sin_titulo = ENTRADA.replace("  title = {Abejas de cristal y su miel},\n", "")
    assert _reglas(_leer(tmp_path, sin_titulo)) == ["L-A04", "L-A02"]
    sin_doi = ENTRADA.replace("  doi = {10.5555/ABEJA.B1},\n", "")
    reglas = _reglas(_leer(tmp_path, sin_doi))
    assert "L-A01" in reglas
    assert "L-A04" in reglas
    doble = ENTRADA + ENTRADA.replace("Cristal2024", "Otra2024")
    assert _reglas(_leer(tmp_path, doble)) == ["L-A05"]


def test_archivo_sin_entradas(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, "% solo un comentario\n")
    assert resultado.numero_registros == 0
    assert _reglas(resultado) == ["L-A04"] * 5


def test_los_mensajes_no_llevan_valores(tmp_path: Path) -> None:
    mala = "@article{malo,\n  title = {Titulo-licenciado},\n  title = {Dos},\n}\n"
    resultado = _leer(tmp_path, ENTRADA + ENTRADA + mala)
    mensajes = " ".join(h.mensaje for h in resultado.hallazgos)
    assert mensajes
    assert not any(valor in mensajes for valor in ("licenciado", "10.5555", "Cristal"))
