"""Pruebas de L-A01, L-E03 y L-A05: dentro de un archivo y entre archivos."""

from agentresearch.importacion.identidad import (
    hallazgos_de_identidad,
    repeticiones_entre_archivos,
)

from .apoyo_importacion import registro


def test_l_a01_registro_sin_identificador_ni_doi() -> None:
    hallazgos = hallazgos_de_identidad(
        "a.bib", [registro(posicion=4, titulo="T"), registro(posicion=9, doi="10.5555/x")]
    )
    assert [(h.regla, h.linea, h.severidad) for h in hallazgos] == [("L-A01", 4, "advertencia")]


def test_l_e03_identificador_repetido_dentro_del_archivo() -> None:
    registros = [
        registro(tipo_id_fuente="eid", id_fuente="2-s2.0-1", posicion=2),
        registro(tipo_id_fuente="eid", id_fuente="2-s2.0-2", posicion=3),
        registro(tipo_id_fuente="eid", id_fuente="2-s2.0-1", posicion=4),
    ]
    hallazgos = hallazgos_de_identidad("a.csv", registros)
    assert [(h.regla, h.severidad, h.linea) for h in hallazgos] == [("L-E03", "error", 4)]
    assert "línea 2" in hallazgos[0].mensaje
    assert "2-s2.0-1" not in hallazgos[0].mensaje


def test_l_e03_el_tipo_forma_parte_de_la_identidad() -> None:
    registros = [
        registro(tipo_id_fuente="eid", id_fuente="X1", posicion=2),
        registro(tipo_id_fuente="ut", id_fuente="X1", posicion=3),
    ]
    assert hallazgos_de_identidad("a.csv", registros) == ()


def test_l_a05_doi_repetido_sin_identificador_de_la_fuente() -> None:
    registros = [
        registro(doi="10.5555/ABC", posicion=4, formato="bibtex"),
        registro(doi="https://doi.org/10.5555/abc", posicion=30, formato="bibtex"),
    ]
    hallazgos = hallazgos_de_identidad("a.bib", registros)
    assert [(h.regla, h.severidad, h.linea) for h in hallazgos] == [("L-A05", "advertencia", 30)]


def test_el_doi_no_hace_de_identidad_para_el_error() -> None:
    # Un registro con identificador y otro sin él, con el mismo DOI: ni L-E03 ni L-A05.
    registros = [
        registro(tipo_id_fuente="eid", id_fuente="E1", doi="10.5555/x", posicion=2),
        registro(doi="10.5555/x", posicion=3),
    ]
    assert hallazgos_de_identidad("a.csv", registros) == ()


def test_con_identificador_se_compara_solo_por_el() -> None:
    # Mismo DOI pero identificadores distintos: dos registros distintos, sin hallazgo.
    registros = [
        registro(tipo_id_fuente="eid", id_fuente="E1", doi="10.5555/x", posicion=2),
        registro(tipo_id_fuente="eid", id_fuente="E2", doi="10.5555/x", posicion=3),
    ]
    assert hallazgos_de_identidad("a.csv", registros) == ()


def test_repeticiones_entre_archivos_l_e03() -> None:
    primero = [
        registro(tipo_id_fuente="eid", id_fuente="E1", posicion=2),
        registro(tipo_id_fuente="eid", id_fuente="E2", posicion=3),
    ]
    segundo = [registro(tipo_id_fuente="eid", id_fuente="E1", posicion=7)]
    repeticiones, hallazgos = repeticiones_entre_archivos([("a.csv", primero), ("b.csv", segundo)])
    assert len(repeticiones) == 1
    assert repeticiones[0].regla == "L-E03"
    assert repeticiones[0].tipo == "eid"
    assert [(o.archivo, o.linea) for o in repeticiones[0].ocurrencias] == [
        ("a.csv", 2),
        ("b.csv", 7),
    ]
    assert [(h.regla, h.archivo, h.linea) for h in hallazgos] == [("L-E03", "b.csv", 7)]
    assert "a.csv, línea 2" in hallazgos[0].mensaje


def test_repeticiones_entre_archivos_l_a05() -> None:
    primero = [registro(doi="10.5555/x", posicion=2)]
    segundo = [registro(doi="10.5555/x", posicion=5)]
    repeticiones, hallazgos = repeticiones_entre_archivos([("a.bib", primero), ("b.bib", segundo)])
    assert [r.regla for r in repeticiones] == ["L-A05"]
    assert [h.regla for h in hallazgos] == ["L-A05"]


def test_un_repetido_solo_dentro_de_un_archivo_no_es_entre_archivos() -> None:
    mismo = [
        registro(tipo_id_fuente="eid", id_fuente="E1", posicion=2),
        registro(tipo_id_fuente="eid", id_fuente="E1", posicion=3),
    ]
    otro = [registro(tipo_id_fuente="eid", id_fuente="E9", posicion=2)]
    assert repeticiones_entre_archivos([("a.csv", mismo), ("b.csv", otro)]) == ((), ())
