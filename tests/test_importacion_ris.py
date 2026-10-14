"""Pruebas del lector de RIS y de `leer` (todo sintético; tema ficticio)."""

from pathlib import Path

import pytest

from agentresearch.importacion import servicio
from agentresearch.importacion.entrada import ErrorDeArchivo
from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.importacion.servicio import formatos_disponibles, leer

from .apoyo_importacion import escribir


def _reglas(resultado: ResultadoLectura) -> list[str]:
    return [h.regla for h in resultado.hallazgos]


REGISTRO_SCOPUS = """TY  - JOUR
AU  - Cristal, A.
AU  - Vidrio, B.C.
TI  - Abejas de cristal y su miel
PY  - 2024
T2  - Revista de Abejas
VL  - 12
IS  - 3
C7  - 100123
DO  - 10.5555/ABEJA.1
UR  - https://www.example.org/pages/publications/1
AD  - Instituto de Abejas, Ciudad Ficticia
AB  - Resumen ficticio sobre abejas.
KW  - miel
KW  - cristal
PB  - Editorial Ficticia
SN  - 12345678 (ISSN)
LA  - English
J2  - Rev. Abejas
M3  - Article
C2  - 99999999
DB  - Scopus
N1  - CODEN: ABEJA
N1  - Cited By: 4
N1  - Export Date: 13 October 2026
N1  - EID: 2-s2.0-000000000001
ER  -

"""


def _leer(
    tmp_path: Path,
    texto: str,
    fuente: str = "scopus",
    *,
    bom: bool = False,
    fin_de_linea: str = "\n",
) -> ResultadoLectura:
    ruta = escribir(tmp_path / "datos.ris", texto, bom=bom, fin_de_linea=fin_de_linea)
    return leer(ruta, "ris", fuente)


def test_formato_ris_disponible() -> None:
    assert "ris" in formatos_disponibles()


def test_registro_completo_con_el_perfil_scopus(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, REGISTRO_SCOPUS)
    assert resultado.numero_registros == 1
    registro = resultado.registros[0]
    assert registro.formato == "ris"
    assert registro.fuente == "scopus"
    assert registro.archivo == "datos.ris"
    assert registro.posicion == 1
    assert registro.titulo == "Abejas de cristal y su miel"
    assert registro.autores == ("Cristal, A.", "Vidrio, B.C.")
    assert registro.anio == 2024
    assert registro.fuente_publicacion == "Revista de Abejas"
    assert (registro.volumen, registro.numero) == ("12", "3")
    assert registro.doi == "10.5555/abeja.1"
    assert registro.resumen == "Resumen ficticio sobre abejas."
    assert registro.idioma == "English"
    assert registro.pmid == "99999999"
    assert registro.tipo_documento == "Article"
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("eid", "2-s2.0-000000000001")
    assert registro.palabras_clave_autor == ()
    assert registro.otros["KW"] == "miel; cristal"
    assert registro.otros["C7"] == "100123"
    assert registro.otros["N1"] == "CODEN: ABEJA"
    assert registro.otros["TY"] == "JOUR"
    assert "Y2" not in registro.otros
    assert _reglas(resultado) == []


def test_bom_y_crlf_y_caracteres_no_ascii(tmp_path: Path) -> None:
    texto = "TY  - JOUR\nAU  - Ñandú, Ü.\nTI  - Étude ficticielle\nPY  - 2020\nDO  - 10.5555/x\n"
    texto += "AB  - Résumé\nER  - \n"
    resultado = _leer(tmp_path, texto, bom=True, fin_de_linea="\r\n")
    registro = resultado.registros[0]
    assert registro.titulo == "Étude ficticielle"
    assert registro.autores == ("Ñandú, Ü.",)
    assert registro.posicion == 1


def test_er_con_y_sin_espacio_final_y_lineas_vacias(tmp_path: Path) -> None:
    texto = (
        "TY  - JOUR\nTI  - Uno\nPY  - 2020\nDO  - 10.5555/1\nAU  - A\nAB  - r\nER  - \n\n\n"
        "TY  - JOUR\nTI  - Dos\nPY  - 2021\nDO  - 10.5555/2\nAU  - B\nAB  - r\nER  -\n\n"
    )
    resultado = _leer(tmp_path, texto)
    assert [r.titulo for r in resultado.registros] == ["Uno", "Dos"]
    assert [r.posicion for r in resultado.registros] == [1, 10]


def test_l_a03_cabecera_de_acs_se_avisa_y_se_muestra(tmp_path: Path) -> None:
    texto = (
        "Provider: Proveedor Ficticio\nDatabase: Base Ficticia\nContent: text/plain\n\n"
        "TY  - JOUR\nAU  - A\nTI  - T\nPY  - 2020\nDO  - 10.5555/1\nAB  - r\nER  - \n"
    )
    resultado = _leer(tmp_path, texto, fuente="acs")
    assert [c.linea for c in resultado.lineas_cabecera] == [1, 2, 3]
    assert resultado.lineas_cabecera[0].texto.startswith("Provider:")
    assert _reglas(resultado) == ["L-A03"]
    assert resultado.registros[0].posicion == 5


def test_lineas_de_continuacion(tmp_path: Path) -> None:
    texto = (
        "TY  - JOUR\nAU  - A\nTI  - Un título muy largo\n  que sigue aquí\nPY  - 2020\n"
        "DO  - 10.5555/1\nAB  - r\nER  - \n"
    )
    resultado = _leer(tmp_path, texto)
    assert resultado.registros[0].titulo == "Un título muy largo que sigue aquí"


def test_perfil_acs_descarta_y2_y_usa_el_doi_como_identificador(tmp_path: Path) -> None:
    base = "TY  - JOUR\nAU  - A\nT1  - T\nPY  - 2020\nY1  - 2020/01/02\nDO  - {doi}\n"
    base += "JO  - Revista\nJA  - Revista\nAB  - r\nY2  - {y2}\n"
    base += "UR  - https://doi.org/{doi}\nER  - \n"
    uno = _leer(tmp_path, base.format(doi="10.5555/ACS.1", y2="10/14/2026"), fuente="acs")
    dos_ruta = escribir(tmp_path / "otra.ris", base.format(doi="10.5555/ACS.1", y2="11/20/2026"))
    dos = leer(dos_ruta, "ris", "acs")
    r1, r2 = uno.registros[0], dos.registros[0]
    assert (r1.tipo_id_fuente, r1.id_fuente) == ("doi", "10.5555/acs.1")
    assert "Y2" not in r1.otros
    assert r1.otros["Y1"] == "2020/01/02"
    assert r1.fuente_publicacion == "Revista"
    assert r1.otros["JA"] == "Revista"
    assert r1.hash_completo == r2.hash_completo
    assert uno.hash_archivo != dos.hash_archivo


def test_scopus_export_date_y_cited_by_no_cambian_el_hash(tmp_path: Path) -> None:
    otro = REGISTRO_SCOPUS.replace("Cited By: 4", "Cited By: 9").replace(
        "13 October 2026", "20 November 2026"
    )
    r1 = _leer(tmp_path, REGISTRO_SCOPUS).registros[0]
    ruta = escribir(tmp_path / "otro.ris", otro)
    r2 = leer(ruta, "ris", "scopus").registros[0]
    assert r1.hash_completo == r2.hash_completo
    assert r2.otros["N1"] == "CODEN: ABEJA"


def test_scopus_sin_linea_eid_queda_sin_identificador(tmp_path: Path) -> None:
    texto = REGISTRO_SCOPUS.replace("N1  - EID: 2-s2.0-000000000001\n", "")
    registro = _leer(tmp_path, texto).registros[0]
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("ninguno", None)
    assert registro.doi == "10.5555/abeja.1"


def test_fuente_sin_perfil_usa_la_tabla_base(tmp_path: Path) -> None:
    registro = _leer(tmp_path, REGISTRO_SCOPUS, fuente="lens").registros[0]
    assert registro.pmid is None
    assert registro.otros["C2"] == "99999999"
    assert registro.tipo_documento is None
    assert registro.otros["M3"] == "Article"
    assert registro.tipo_id_fuente == "ninguno"
    assert "EID: 2-s2.0-000000000001" in registro.otros["N1"]


def test_anio_y_paginas(tmp_path: Path) -> None:
    texto = (
        "TY  - JOUR\nAU  - A\nTI  - T\nPY  - 2021/05/06/\nSP  - 10\nEP  - 20\nDO  - 10.5555/1\n"
        "AB  - r\nER  - \nTY  - JOUR\nAU  - A\nTI  - T2\nPY  - sin año\nEP  - 30\nDO  - 10.5555/2\n"
        "AB  - r\nER  - \n"
    )
    uno, dos = _leer(tmp_path, texto).registros
    assert (uno.anio, uno.paginas) == (2021, "10-20")
    assert (dos.anio, dos.paginas) == (None, None)
    assert dos.otros["PY"] == "sin año"
    assert dos.otros["EP"] == "30"


def test_l_e02_registro_sin_cierre_antes_del_siguiente_ty(tmp_path: Path) -> None:
    texto = (
        "TY  - JOUR\nTI  - Sin cierre\nAU  - A\nPY  - 2020\nDO  - 10.5555/1\nAB  - r\n"
        "TY  - JOUR\nTI  - Con cierre\nAU  - A\nPY  - 2020\nDO  - 10.5555/2\nAB  - r\nER  - \n"
    )
    resultado = _leer(tmp_path, texto)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [(h.linea, h.severidad) for h in errores] == [(1, "error")]
    assert [r.titulo for r in resultado.registros] == ["Con cierre"]


def test_l_e02_registro_sin_cierre_al_final_del_archivo(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, "TY  - JOUR\nTI  - Uno\nAU  - A\nPY  - 2020\n")
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [h.linea for h in errores] == [1]
    assert resultado.numero_registros == 0


def test_l_e02_etiqueta_fuera_de_un_registro(tmp_path: Path) -> None:
    texto = (
        "AU  - Suelto\nTY  - JOUR\nTI  - T\nAU  - A\nPY  - 2020\nDO  - 10.5555/1\nAB  - r\nER  - \n"
        "ER  - \nPY  - 1999\nTexto suelto\n"
    )
    resultado = _leer(tmp_path, texto)
    errores = [(h.linea, h.mensaje) for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [linea for linea, _ in errores] == [1, 9, 10, 11]
    assert resultado.numero_registros == 1


def test_l_a04_campo_esperado_ausente(tmp_path: Path) -> None:
    texto = REGISTRO_SCOPUS.replace("AB  - Resumen ficticio sobre abejas.\n", "")
    resultado = _leer(tmp_path, texto)
    avisos = [h for h in resultado.hallazgos if h.regla == "L-A04"]
    assert len(avisos) == 1
    assert "resumen" in avisos[0].mensaje


def test_l_a02_registro_sin_titulo_con_su_linea(tmp_path: Path) -> None:
    texto = REGISTRO_SCOPUS + REGISTRO_SCOPUS.replace(
        "TI  - Abejas de cristal y su miel\n", ""
    ).replace("2-s2.0-000000000001", "2-s2.0-000000000002")
    resultado = _leer(tmp_path, texto)
    avisos = [h for h in resultado.hallazgos if h.regla == "L-A02"]
    assert [h.linea for h in avisos] == [29]


def test_l_e03_identificador_repetido_y_l_a05(tmp_path: Path) -> None:
    repetido = REGISTRO_SCOPUS + REGISTRO_SCOPUS
    resultado = _leer(tmp_path, repetido)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E03"]
    assert [h.linea for h in errores] == [29]
    sin_eid = REGISTRO_SCOPUS.replace("N1  - EID: 2-s2.0-000000000001\n", "")
    resultado = _leer(tmp_path, sin_eid + sin_eid)
    assert _reglas(resultado).count("L-A05") == 1
    assert "L-E03" not in _reglas(resultado)


def test_l_a01_sin_identificador_ni_doi(tmp_path: Path) -> None:
    texto = "TY  - JOUR\nTI  - T\nAU  - A\nPY  - 2020\nAB  - r\nER  - \n"
    resultado = _leer(tmp_path, texto)
    assert "L-A01" in _reglas(resultado)
    assert "L-A04" in _reglas(resultado)  # no trae DOI


def test_los_mensajes_no_contienen_datos_del_registro(tmp_path: Path) -> None:
    texto = REGISTRO_SCOPUS.replace("Abejas de cristal y su miel", "Secreto-licenciado")
    resultado = _leer(tmp_path, texto + texto)
    mensajes = " ".join(h.mensaje for h in resultado.hallazgos)
    assert mensajes
    assert "licenciado" not in mensajes
    assert "2-s2.0" not in mensajes


def test_archivo_vacio(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, "")
    assert resultado.numero_registros == 0
    assert _reglas(resultado) == ["L-A04"] * 5


def test_l_e01_a_traves_de_leer(tmp_path: Path) -> None:
    ruta = tmp_path / "latin1.ris"
    ruta.write_bytes(b"TY  - JOUR\nTI  - Caf\xe9\nER  - \n")
    resultado = leer(ruta, "ris", "scopus")
    assert [h.regla for h in resultado.hallazgos] == ["L-E01"]
    assert resultado.hallazgos[0].linea == 2
    assert resultado.numero_registros == 0


def test_leer_valida_fuente_formato_y_archivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = escribir(tmp_path / "a.ris", REGISTRO_SCOPUS)
    with pytest.raises(ValueError, match="fuente"):
        leer(ruta, "ris", "  ")
    with pytest.raises(ErrorDeArchivo):
        leer(tmp_path / "no_existe.ris", "ris", "scopus")
    monkeypatch.setattr(servicio, "_LECTORES", {})
    with pytest.raises(ValueError, match="sin lector"):
        leer(ruta, "ris", "scopus")


def test_leer_no_escribe_nada(tmp_path: Path) -> None:
    ruta = escribir(tmp_path / "a.ris", REGISTRO_SCOPUS)
    antes = sorted(p.name for p in tmp_path.iterdir())
    leer(ruta, "ris", "scopus")
    assert sorted(p.name for p in tmp_path.iterdir()) == antes
