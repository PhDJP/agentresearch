"""Pruebas del lector de Web of Science en texto plano (todo sintético; tema ficticio)."""

from pathlib import Path

from agentresearch.importacion.resultado import ResultadoLectura
from agentresearch.importacion.servicio import formatos_disponibles, leer

from .apoyo_importacion import escribir

CABECERA = "FN Archivo Ficticio de Prueba\nVR 1.0\n"

REGISTRO = """PT J
AU Cristal, A
   Vidrio, BC
AF Cristal, Ana
   Vidrio, Beatriz Carla
TI Abejas de cristal y su miel: un estudio
   ficticio de largo título
SO REVISTA DE ABEJAS
LA English
DT Article
DE miel; cristal; abejas de vidrio
ID NECTAR; COLMENA
AB Resumen ficticio sobre abejas
   que continúa aquí.
OI Cristal, A/0000-0000-0000-0001; Vidrio, BC/0000-0000-0000-
   0002
PD MAR
PY 2024
VL 12
IS 3
BP 101
EP 110
AR e100
DI 10.5555/ABEJA.W1
PM 88888888
DA 2026-10-13
UT WOS:000000000000001
ER

"""


def _leer(
    tmp_path: Path, texto: str, *, bom: bool = False, fin_de_linea: str = "\n"
) -> ResultadoLectura:
    ruta = escribir(tmp_path / "savedrecs.txt", texto, bom=bom, fin_de_linea=fin_de_linea)
    return leer(ruta, "wos_txt", "wos")


def _reglas(resultado: ResultadoLectura) -> list[str]:
    return [h.regla for h in resultado.hallazgos]


def test_formato_disponible() -> None:
    assert "wos_txt" in formatos_disponibles()


def test_fn_y_vr_no_disparan_l_a03(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, CABECERA + REGISTRO + "EF")
    assert "L-A03" not in _reglas(resultado)
    assert resultado.lineas_cabecera == ()
    assert resultado.numero_registros == 1


def test_l_a03_solo_lo_que_hay_entre_vr_y_el_primer_pt(tmp_path: Path) -> None:
    texto = CABECERA + "Generado por el sistema ficticio\n" + REGISTRO + "EF\n"
    resultado = _leer(tmp_path, texto)
    assert _reglas(resultado).count("L-A03") == 1
    assert [(c.linea, c.texto) for c in resultado.lineas_cabecera] == [
        (3, "Generado por el sistema ficticio")
    ]
    assert resultado.registros[0].posicion == 4


def test_registro_completo(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, CABECERA + REGISTRO + "EF")
    registro = resultado.registros[0]
    assert registro.formato == "wos_txt"
    assert registro.fuente == "wos"
    assert registro.posicion == 3
    assert registro.titulo == "Abejas de cristal y su miel: un estudio ficticio de largo título"
    assert registro.autores == ("Cristal, A", "Vidrio, BC")
    assert registro.otros["AF"] == "Cristal, Ana; Vidrio, Beatriz Carla"
    assert registro.fuente_publicacion == "REVISTA DE ABEJAS"
    assert registro.idioma == "English"
    assert registro.tipo_documento == "Article"
    assert registro.palabras_clave_autor == ("miel", "cristal", "abejas de vidrio")
    assert registro.palabras_clave_indexadas == ("NECTAR", "COLMENA")
    assert registro.resumen == "Resumen ficticio sobre abejas que continúa aquí."
    assert registro.anio == 2024
    assert (registro.volumen, registro.numero) == ("12", "3")
    assert registro.paginas == "101-110"
    assert registro.otros["AR"] == "e100"
    assert registro.doi == "10.5555/abeja.w1"
    assert registro.pmid == "88888888"
    assert (registro.tipo_id_fuente, registro.id_fuente) == ("ut", "WOS:000000000000001")
    assert registro.otros["OI"] == (
        "Cristal, A/0000-0000-0000-0001; Vidrio, BC/0000-0000-0000- 0002"
    )
    assert registro.otros["PD"] == "MAR"
    assert "DA" not in registro.otros
    assert "PT" in registro.otros
    assert _reglas(resultado) == []


def test_da_es_volatil_y_no_cambia_el_hash(tmp_path: Path) -> None:
    uno = _leer(tmp_path, CABECERA + REGISTRO + "EF").registros[0]
    otro = REGISTRO.replace("DA 2026-10-13", "DA 2027-01-01")
    ruta = escribir(tmp_path / "otro.txt", CABECERA + otro + "EF")
    dos = leer(ruta, "wos_txt", "wos").registros[0]
    assert uno.hash_completo == dos.hash_completo
    sin_da = escribir(tmp_path / "sin_da.txt", CABECERA + REGISTRO.replace("DA 2026-10-13\n", ""))
    assert leer(sin_da, "wos_txt", "wos").registros[0].hash_completo == uno.hash_completo


def test_bom_lf_sin_salto_final_y_sin_ef(tmp_path: Path) -> None:
    texto = (CABECERA + REGISTRO).rstrip("\n")  # termina en ER, sin EF ni salto final
    resultado = _leer(tmp_path, texto, bom=True)
    assert resultado.numero_registros == 1
    assert [h for h in resultado.hallazgos if h.severidad == "error"] == []


def test_crlf(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, CABECERA + REGISTRO + "EF\n", fin_de_linea="\r\n")
    assert resultado.registros[0].titulo is not None
    assert resultado.registros[0].posicion == 3


def test_varios_registros_y_posiciones(tmp_path: Path) -> None:
    segundo = REGISTRO.replace("WOS:000000000000001", "WOS:000000000000002").replace(
        "ABEJA.W1", "ABEJA.W2"
    )
    resultado = _leer(tmp_path, CABECERA + REGISTRO + segundo + "EF\n")
    assert [r.posicion for r in resultado.registros] == [3, 3 + len(REGISTRO.splitlines())]
    assert resultado.numero_registros == 2
    assert _reglas(resultado) == []


def test_exportacion_sin_resumen_avisa_l_a04(tmp_path: Path) -> None:
    sin_resumen = (
        "PT J\nAU Cristal, A\nTI Un título\nSO REVISTA\nPY 2024\nDI 10.5555/x\nUT WOS:1\nER\n\nEF"
    )
    resultado = _leer(tmp_path, CABECERA + sin_resumen)
    avisos = [h for h in resultado.hallazgos if h.regla == "L-A04"]
    assert len(avisos) == 1
    assert "resumen" in avisos[0].mensaje


def test_l_e02_registro_sin_cierre(tmp_path: Path) -> None:
    texto = CABECERA + "PT J\nTI Sin cierre\nAU A\nPY 2024\n" + REGISTRO + "EF\n"
    resultado = _leer(tmp_path, texto)
    errores = [h for h in resultado.hallazgos if h.regla == "L-E02"]
    assert [h.linea for h in errores] == [3]
    assert resultado.numero_registros == 1


def test_l_e02_sin_cierre_antes_de_ef_y_al_final(tmp_path: Path) -> None:
    antes_de_ef = _leer(tmp_path, CABECERA + "PT J\nTI Uno\nAU A\nEF\n")
    assert [h.linea for h in antes_de_ef.hallazgos if h.regla == "L-E02"] == [3]
    al_final = _leer(tmp_path, CABECERA + "PT J\nTI Uno\nAU A\n")
    assert [h.linea for h in al_final.hallazgos if h.regla == "L-E02"] == [3]


def test_l_e02_etiqueta_er_y_otras_fuera_de_un_registro(tmp_path: Path) -> None:
    texto = CABECERA + REGISTRO + "ER\nTI Suelto\nEF\nTexto tras EF\n"
    resultado = _leer(tmp_path, texto)
    lineas = [h.linea for h in resultado.hallazgos if h.regla == "L-E02"]
    n = 2 + len(REGISTRO.splitlines())
    assert lineas == [n + 1, n + 2, n + 4]


def test_l_e02_linea_sin_etiqueta_dentro_de_un_registro(tmp_path: Path) -> None:
    texto = CABECERA + "PT J\nTI Uno\nesto no es una etiqueta\nAU A\nER\nEF\n"
    resultado = _leer(tmp_path, texto)
    assert [h.linea for h in resultado.hallazgos if h.regla == "L-E02"] == [5]


def test_l_e03_ut_repetido_y_l_a01_sin_identificador(tmp_path: Path) -> None:
    sin_id = "PT J\nAU A\nTI Sin identificador\nPY 2024\nER\n\n"
    texto = CABECERA + REGISTRO + REGISTRO + sin_id + "EF\n"
    resultado = _leer(tmp_path, texto)
    assert _reglas(resultado).count("L-E03") == 1
    assert _reglas(resultado).count("L-A01") == 1


def test_el_mensaje_no_lleva_valores(tmp_path: Path) -> None:
    texto = CABECERA + REGISTRO + REGISTRO + "EF\n"
    resultado = _leer(tmp_path, texto)
    mensajes = " ".join(h.mensaje for h in resultado.hallazgos)
    assert "WOS:0000" not in mensajes
    assert "Abejas" not in mensajes


def test_archivo_sin_registros(tmp_path: Path) -> None:
    resultado = _leer(tmp_path, CABECERA + "EF\n")
    assert resultado.numero_registros == 0
    assert _reglas(resultado) == ["L-A04"] * 5


def test_cabecera_con_etiqueta_y_con_continuacion_antes_del_primer_pt(tmp_path: Path) -> None:
    texto = CABECERA + "XX nota ficticia\n   sigue la nota\n" + REGISTRO + "EF\n"
    resultado = _leer(tmp_path, texto)
    assert [c.linea for c in resultado.lineas_cabecera] == [3, 4]
    assert _reglas(resultado).count("L-A03") == 1


def test_l_e02_continuacion_fuera_de_un_registro(tmp_path: Path) -> None:
    texto = CABECERA + REGISTRO + "   continuación suelta\nEF\n"
    resultado = _leer(tmp_path, texto)
    n = 2 + len(REGISTRO.splitlines())
    assert [h.linea for h in resultado.hallazgos if h.regla == "L-E02"] == [n + 1]
