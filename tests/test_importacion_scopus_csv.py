"""Pruebas del lector del CSV de Scopus y del límite de campo (todo sintético; tema ficticio)."""

import csv
from pathlib import Path

from agentresearch.importacion.motor_csv import LIMITE_CAMPO
from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.importacion.servicio import formatos_disponibles, leer

from .apoyo_importacion import csv_texto, escribir

ENCABEZADO = [
    "Authors",
    "Author full names",
    "Title",
    "Year",
    "Source title",
    "Volume",
    "Issue",
    "Art. No.",
    "Page start",
    "Page end",
    "Cited by",
    "DOI",
    "Abstract",
    "Author Keywords",
    "Index Keywords",
    "PubMed ID",
    "Language of Original Document",
    "Document Type",
    "EID",
]


def _fila(numero: int = 1, **cambios: str) -> list[str]:
    base = {
        "Authors": "Cristal A.; Vidrio B.C.",
        "Author full names": "Cristal, Ana (1); Vidrio, Beatriz (2)",
        "Title": f"Abejas de cristal {numero}",
        "Year": "2024",
        "Source title": "Revista de Abejas",
        "Volume": "12",
        "Issue": "3",
        "Art. No.": "100123",
        "Page start": "",
        "Page end": "",
        "Cited by": "4",
        "DOI": f"10.5555/ABEJA.{numero}",
        "Abstract": "Resumen ficticio.",
        "Author Keywords": "miel; cristal",
        "Index Keywords": "néctar; colmena",
        "PubMed ID": "",
        "Language of Original Document": "English",
        "Document Type": "Article",
        "EID": f"2-s2.0-{numero:011d}",
    }
    base.update(cambios)
    return [base[c] for c in ENCABEZADO]


def _leer(
    tmp_path: Path, texto: str, *, bom: bool = False, fin_de_linea: str = "\n"
) -> ResultadoLectura:
    ruta = escribir(tmp_path / "scopus.csv", texto, bom=bom, fin_de_linea=fin_de_linea)
    return leer(ruta, "scopus_csv", "scopus")


def _reglas(resultado: ResultadoLectura) -> list[str]:
    return [h.regla for h in resultado.hallazgos]


def test_formato_disponible() -> None:
    assert "scopus_csv" in formatos_disponibles()


def test_registro_completo(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]), bom=True)
    assert resultado.numero_registros == 1
    registro = resultado.registros[0]
    assert registro.formato == "scopus_csv"
    assert registro.posicion == 2
    assert registro.titulo == "Abejas de cristal 1"
    assert registro.autores == ("Cristal A.", "Vidrio B.C.")
    assert registro.anio == 2024
    assert registro.fuente_publicacion == "Revista de Abejas"
    assert (registro.volumen, registro.numero) == ("12", "3")
    assert registro.paginas is None
    assert registro.otros["Art. No."] == "100123"
    assert registro.otros["Author full names"].startswith("Cristal, Ana (1)")
    assert registro.doi == "10.5555/abeja.1"
    assert registro.resumen == "Resumen ficticio."
    assert registro.palabras_clave_autor == ("miel", "cristal")
    assert registro.palabras_clave_indexadas == ("néctar", "colmena")
    assert registro.pmid is None
    assert registro.idioma == "English"
    assert registro.tipo_documento == "Article"
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("eid", "2-s2.0-00000000001")
    assert "Cited by" not in registro.otros
    assert _reglas(resultado) == []


def test_paginas_con_inicio_y_fin(tmp_path: Path) -> None:
    texto = csv_texto(ENCABEZADO, [_fila(1, **{"Page start": "10", "Page end": "20"})])
    assert _leer(tmp_path, texto).registros[0].paginas == "10-20"


def test_crlf_y_comillas_y_saltos_de_linea_en_celdas(tmp_path: Path) -> None:
    uno = _fila(1, Abstract='Dice "hola"\nen dos líneas')
    dos = _fila(2)
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [uno, dos]), fin_de_linea="\r\n")
    assert resultado.numero_registros == 2
    assert resultado.registros[0].resumen == 'Dice "hola" en dos líneas'
    # La segunda fila de datos empieza en la línea física 4, no en la fila 3.
    assert [r.posicion for r in resultado.registros] == [2, 4]


def test_cited_by_no_cambia_el_hash(tmp_path: Path) -> None:
    uno = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)])).registros[0]
    ruta = escribir(tmp_path / "otro.csv", csv_texto(ENCABEZADO, [_fila(1, **{"Cited by": "99"})]))
    dos = leer(ruta, "scopus_csv", "scopus").registros[0]
    assert uno.hash_completo == dos.hash_completo


def test_l_a04_columna_esperada_ausente_y_columnas_por_nombre(tmp_path: Path) -> None:
    # Sin la columna del resumen y con las columnas en otro orden.
    encabezado = [c for c in reversed(ENCABEZADO) if c != "Abstract"]
    filas = [[dict(zip(ENCABEZADO, _fila(1), strict=True))[c] for c in encabezado]]
    resultado = _leer(tmp_path, csv_texto(encabezado, filas))
    avisos = [h for h in resultado.hallazgos if h.regla == "L-A04"]
    assert len(avisos) == 1
    assert "resumen" in avisos[0].mensaje
    assert resultado.registros[0].titulo == "Abejas de cristal 1"
    assert resultado.registros[0].autores == ("Cristal A.", "Vidrio B.C.")


def test_l_e02_columna_obligatoria_ausente(tmp_path: Path) -> None:
    encabezado = [c for c in ENCABEZADO if c != "Title"]
    filas = [[dict(zip(ENCABEZADO, _fila(1), strict=True))[c] for c in encabezado]]
    resultado = _leer(tmp_path, csv_texto(encabezado, filas))
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [(h.linea, h.fila) for h in errores] == [(1, 1)]
    assert resultado.numero_registros == 0


def test_l_e02_fila_con_mas_y_con_menos_columnas(tmp_path: Path) -> None:
    mas = [*_fila(2), "sobra"]
    menos = _fila(3)[:-3]
    texto = csv_texto(ENCABEZADO, [_fila(1), mas, menos, _fila(4)])
    resultado = _leer(tmp_path, texto)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [(h.fila, h.linea) for h in errores] == [(3, 3), (4, 4)]
    assert "más" in errores[0].mensaje
    assert "menos" in errores[1].mensaje
    assert [r.titulo for r in resultado.registros] == ["Abejas de cristal 1", "Abejas de cristal 4"]


def test_archivo_vacio_y_solo_encabezado(tmp_path: Path) -> None:
    vacio = _leer(tmp_path, "")
    assert [h.regla for h in vacio.hallazgos] == ["L-E02"]
    solo = _leer(tmp_path, csv_texto(ENCABEZADO, []))
    assert solo.numero_registros == 0
    assert "L-E02" not in _reglas(solo)


def test_l_e03_eid_repetido_y_l_a05_sin_eid(tmp_path: Path) -> None:
    repetido = csv_texto(ENCABEZADO, [_fila(1), _fila(2), _fila(1)])
    assert _reglas(_leer(tmp_path, repetido)).count("L-E03") == 1
    sin_eid = csv_texto(ENCABEZADO, [_fila(1, EID=""), _fila(2, EID="", DOI="10.5555/ABEJA.1")])
    resultado = _leer(tmp_path, sin_eid)
    assert _reglas(resultado).count("L-A05") == 1
    assert "L-E03" not in _reglas(resultado)


def test_l_a02_y_l_a01(tmp_path: Path) -> None:
    texto = csv_texto(ENCABEZADO, [_fila(1, Title=""), _fila(2, EID="", DOI="")])
    resultado = _leer(tmp_path, texto)
    assert _reglas(resultado).count("L-A02") == 1
    assert _reglas(resultado).count("L-A01") == 1


def test_celda_de_exactamente_el_limite_se_lee(tmp_path: Path) -> None:
    grande = "x" * LIMITE_CAMPO
    resultado = _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1, Abstract=grande), _fila(2)]))
    assert resultado.numero_registros == 2
    assert resultado.detenido_en_fila is None
    assert resultado.registros[0].resumen == grande


def test_celda_sobre_el_limite_detiene_la_lectura_en_esa_fila(tmp_path: Path) -> None:
    grande = "x" * (LIMITE_CAMPO + 1)
    texto = csv_texto(ENCABEZADO, [_fila(1), _fila(2), _fila(3, Abstract=grande), _fila(4)])
    resultado = _leer(tmp_path, texto)
    assert resultado.numero_registros == 2
    assert resultado.detenido_en_fila == 4
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [(h.fila, h.linea) for h in errores] == [(4, 4)]
    assert "2 registros" in errores[0].mensaje
    assert [r.titulo for r in resultado.registros] == ["Abejas de cristal 1", "Abejas de cristal 2"]


def test_celda_multilinea_sobre_el_limite_no_deja_filas_basura(tmp_path: Path) -> None:
    grande = ("x" * 1000 + "\n") * (LIMITE_CAMPO // 1000 + 2)
    texto = csv_texto(ENCABEZADO, [_fila(1), _fila(2, Abstract=grande), _fila(3)])
    resultado = _leer(tmp_path, texto)
    assert resultado.numero_registros == 1
    assert resultado.detenido_en_fila == 3
    assert [r.titulo for r in resultado.registros] == ["Abejas de cristal 1"]
    # Ni filas posteriores ni fragmentos de la celda: solo el error de la celda grande.
    assert [h.regla for h in resultado.hallazgos if h.severidad == "error"] == ["L-E02"]


def test_el_limite_de_campo_global_se_restaura(tmp_path: Path) -> None:
    anterior = csv.field_size_limit(131_072)
    try:
        _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1)]))
        assert csv.field_size_limit() == 131_072
        grande = "x" * (LIMITE_CAMPO + 1)
        _leer(tmp_path, csv_texto(ENCABEZADO, [_fila(1, Abstract=grande)]))
        assert csv.field_size_limit() == 131_072
    finally:
        csv.field_size_limit(anterior)


def test_los_mensajes_no_llevan_valores(tmp_path: Path) -> None:
    texto = csv_texto(ENCABEZADO, [_fila(1), _fila(1)])
    resultado = _leer(tmp_path, texto)
    mensajes = " ".join(h.mensaje for h in resultado.hallazgos)
    assert "2-s2.0" not in mensajes
    assert "Abejas" not in mensajes


def test_celda_del_encabezado_sobre_el_limite(tmp_path: Path) -> None:
    grande = "x" * (LIMITE_CAMPO + 1)
    resultado = _leer(tmp_path, csv_texto([grande], []))
    assert resultado.numero_registros == 0
    assert resultado.detenido_en_fila == 1
    assert [h.regla for h in resultado.hallazgos] == ["L-E02"]
