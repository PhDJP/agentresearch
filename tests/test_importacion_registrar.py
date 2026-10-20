"""Pruebas de `importar registrar` (todo sintético; temas ficticios)."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agentresearch.importacion import registrar as modulo_registrar
from agentresearch.importacion.git_ignorados import comprobar_con_git
from agentresearch.importacion.registrar import ErrorRegistro
from agentresearch.protocolo import RutasProtocolo, leer_estado_registro, validar_archivo
from agentresearch.protocolo.aprobacion import OperacionCancelada
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL
from agentresearch.trazabilidad import RegistroEncadenado, escribir_atomico, hash_bytes

from .apoyo import TerminalSimulada
from .apoyo_busquedas import (
    RESUMEN,
    Estudio,
    crear_estudio,
    desfase_menos_cinco,
    reloj_de_registro,
    ris,
    sin_comprobar_git,
)
from .apoyo_importacion import escribir

FRASE = "registrar imp-0001"
RUTA_ESCRIBIR = "agentresearch.importacion.registrar.escribir_atomico"


@pytest.fixture
def estudio(tmp_path: Path) -> Estudio:
    return crear_estudio(tmp_path)


def _rechazada(estudio: Estudio, busqueda: Path, regla: str, **opciones: Any) -> ErrorRegistro:
    """Intenta registrar, espera `ErrorRegistro` con `regla` y que no se haya escrito nada."""
    antes = estudio.archivos()
    with pytest.raises(ErrorRegistro) as error:
        estudio.registrar(busqueda, **opciones)
    assert any(regla in mensaje for mensaje in error.value.errores), error.value.errores
    assert estudio.archivos() == antes
    return error.value


# --- Registro completo -------------------------------------------------------------


def test_registro_completo_escribe_archivos_evento_y_anclaje(estudio: Estudio) -> None:
    a = estudio.archivo_ris("savedrecs.ris", 1, 2, 3)

    resultado, terminal = estudio.registrar(estudio.busqueda([a]))

    raiz = estudio.raiz
    carpeta = raiz / "importaciones" / "imp-0001"
    assert resultado.id_importacion == "imp-0001"
    assert (raiz / "exportaciones_originales" / "imp-0001" / "savedrecs.ris").read_bytes() == (
        a.read_bytes()
    )
    for nombre in ("importacion.json", "registros.jsonl", "registros.csv"):
        assert (carpeta / nombre).is_file()
    [evento] = [
        e
        for e in RegistroEncadenado(RutasProtocolo.desde(estudio.protocolo).eventos).leer()
        if e.tipo == "busqueda_registrada"
    ]
    assert evento == resultado.evento
    datos = evento.datos
    assert datos["registros_leidos"] == 3 == datos["resultados_interfaz"]
    assert datos["fecha_hora_busqueda"] == "2026-10-14T09:30-05:00"
    assert datos["fecha_hora_busqueda_utc"] == "2026-10-14T14:30Z"
    assert datos["version_protocolo"] == "1.0.0"
    assert datos["relacion_ecuacion"] == "identica"
    assert datos["registrado_por"] == {"tipo": "humano", "id": "investigador-1"}
    assert datos["archivos"][0]["copia"] == "exportaciones_originales/imp-0001/savedrecs.ris"
    assert datos["hash_registros_jsonl"] == hash_bytes((carpeta / "registros.jsonl").read_bytes())
    assert "Resumen" in terminal.texto or "Registro de la búsqueda imp-0001" in terminal.texto
    assert str(resultado.anclaje).startswith("evt-")
    assert validar_archivo(estudio.protocolo).errores == []
    assert leer_estado_registro(RutasProtocolo.desde(estudio.protocolo)).integro


def test_el_resumen_no_se_versiona_y_solo_salen_los_campos_habilitados(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)

    resultado, _ = estudio.registrar(estudio.busqueda([a]))

    carpeta = estudio.raiz / "importaciones" / "imp-0001"
    for nombre in ("importacion.json", "registros.jsonl", "registros.csv"):
        assert RESUMEN not in (carpeta / nombre).read_text(encoding="utf-8")
    primera = json.loads((carpeta / "registros.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert {"titulo", "autores", "doi", "id_fuente", "tipo_id_fuente"} <= set(primera)
    assert "anio" not in primera
    assert "resumen" not in primera
    assert resultado.evento.datos["campos_versionados"] == ["id_fuente", "titulo", "autores", "doi"]


def test_campos_pendientes_se_registran_con_la_advertencia_i_a01(tmp_path: Path) -> None:
    pendiente = """
fuentes:
  scopus:
    campos:
      titulo:
        base: {tipo: institucion, detalle: Biblioteca ficticia, medio: correo, fecha: 2026-10-05}
      doi:
        base: {tipo: institucion, detalle: null, medio: null, fecha: null}
"""
    estudio = crear_estudio(tmp_path, configuracion=pendiente)
    a = estudio.archivo_ris("a.ris", 1)

    resultado, terminal = estudio.registrar(estudio.busqueda([a]))

    datos = resultado.evento.datos
    assert datos["campos_versionados"] == ["titulo"]
    motivos = {c["campo"]: c["motivo"] for c in datos["campos_solo_locales"]}
    assert motivos["doi"] == "base_incompleta"
    assert motivos["anio"] == "sin_habilitar"
    assert motivos["resumen"] == "nunca_publicable"
    assert any("I-A01" in aviso for aviso in resultado.advertencias)
    assert "I-A01" in terminal.texto
    carpeta = estudio.raiz / "importaciones" / "imp-0001"
    linea = json.loads((carpeta / "registros.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "doi" not in linea
    assert "titulo" in linea


def test_id_fuente_de_tipo_doi_sin_doi_habilitado_queda_solo_local(tmp_path: Path) -> None:
    configuracion = """
fuentes:
  acs:
    campos:
      id_fuente:
        base: {tipo: institucion, detalle: Biblioteca ficticia, medio: correo, fecha: 2026-10-05}
      titulo:
        base: {tipo: institucion, detalle: Biblioteca ficticia, medio: correo, fecha: 2026-10-05}
"""
    fuente_acs = '  - id: acs\n    tipo: exportacion\n    cobertura: "x"\n    limites: "Ninguno"\n'
    estudio = crear_estudio(tmp_path, configuracion=configuracion, fuentes_extra=fuente_acs)
    archivo = escribir(
        estudio.descargas / "acs.ris",
        "TY  - JOUR\nAU  - Cristal, A.\nT1  - Abejas\nPY  - 2024\nDO  - 10.5555/ABEJA.1\nER  - \n",
    )
    busqueda = estudio.busqueda(
        [archivo],
        fuente="acs",
        ecuacion_ejecutada=estudio.ecuacion_esperada("acs") + " AND filtro",
    )

    resultado, _ = estudio.registrar(busqueda)

    datos = resultado.evento.datos
    assert "id_fuente" not in datos["campos_versionados"]
    assert {"campo": "id_fuente", "motivo": "sin_habilitar"} in datos["campos_solo_locales"]
    assert datos["relacion_ecuacion"] == "adaptacion_generica"


def test_las_repeticiones_dan_los_mismos_bytes(tmp_path: Path) -> None:
    resultados = []
    for nombre in ("uno", "dos"):
        estudio = crear_estudio(tmp_path / nombre)
        a = estudio.archivo_ris("a.ris", 1, 2)
        estudio.registrar(estudio.busqueda([a]))
        carpeta = estudio.raiz / "importaciones" / "imp-0001"
        resultados.append(
            (carpeta / "registros.jsonl").read_bytes() + (carpeta / "registros.csv").read_bytes()
        )
    assert resultados[0] == resultados[1]


def test_varias_tandas_suman_los_registros(estudio: Estudio) -> None:
    a = estudio.archivo_ris("tanda1.ris", 1, 2)
    b = estudio.archivo_ris("tanda2.ris", 3)

    resultado, _ = estudio.registrar(estudio.busqueda([a, b]))

    datos = resultado.evento.datos
    assert datos["registros_leidos"] == 3
    assert [x["registros"] for x in datos["archivos"]] == [2, 1]
    jsonl = estudio.raiz / "importaciones" / "imp-0001" / "registros.jsonl"
    lineas = jsonl.read_text(encoding="utf-8").splitlines()
    assert [json.loads(linea)["id"] for linea in lineas] == [
        "imp-0001-00001",
        "imp-0001-00002",
        "imp-0001-00003",
    ]


def test_la_segunda_busqueda_es_imp_0002(estudio: Estudio) -> None:
    estudio.registrar(estudio.busqueda([estudio.archivo_ris("a.ris", 1)]))

    resultado, _ = estudio.registrar(
        estudio.busqueda([estudio.archivo_ris("b.ris", 2)]),
        respuestas=["2026-10-14", "10:00", "", "registrar imp-0002"],
    )

    assert resultado.id_importacion == "imp-0002"
    assert leer_estado_registro(RutasProtocolo.desde(estudio.protocolo)).integro


# --- Reglas I-E ---------------------------------------------------------------------


def test_i_e01_protocolo_en_borrador(tmp_path: Path) -> None:
    estudio = crear_estudio(tmp_path, aprobar=False)
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E01")


def test_i_e01_protocolo_con_cambios_sin_enmienda(estudio: Estudio) -> None:
    texto = estudio.protocolo.read_text(encoding="utf-8")
    estudio.protocolo.write_text(texto + "\n# cambio\n", encoding="utf-8", newline="\n")
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E01")


@pytest.mark.parametrize("fuente", ["wos", "openalex"])
def test_i_e02_fuente_no_declarada_o_sin_tipo_exportacion(estudio: Estudio, fuente: str) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)], fuente=fuente)

    _rechazada(estudio, busqueda, "I-E02")


def test_i_e04_fecha_futura(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E04", respuestas=["2026-10-20", "09:30", "", FRASE])


def test_i_e04_fecha_anterior_a_la_aprobacion(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E04", respuestas=["2026-09-20", "09:30", "", FRASE])


def test_i_e05_archivo_ya_registrado(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    estudio.registrar(estudio.busqueda([a]))

    _rechazada(estudio, estudio.busqueda([a]), "I-E05")


def test_i_e05_archivo_repetido_en_la_misma_busqueda(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    copia = estudio.descargas / "a (1).ris"
    shutil.copyfile(a, copia)

    _rechazada(estudio, estudio.busqueda([a, copia]), "I-E05")


def test_i_e06_identificador_repetido_entre_archivos(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)
    b = estudio.archivo_ris("b.ris", 2, 3)

    _rechazada(estudio, estudio.busqueda([a, b]), "I-E06")


def test_i_e06_identificador_repetido_dentro_de_un_archivo(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 1)

    _rechazada(estudio, estudio.busqueda([a]), "I-E06")


def test_doi_repetido_sin_identificador_no_impide_registrar(estudio: Estudio) -> None:
    sin_eid = "TY  - JOUR\nTI  - Abejas\nPY  - 2024\nDO  - 10.5555/IGUAL\nER  - \n\n"
    a = escribir(estudio.descargas / "a.ris", sin_eid)
    b = escribir(estudio.descargas / "b.ris", sin_eid.replace("Abejas", "Abejas dos"))

    resultado, _ = estudio.registrar(estudio.busqueda([a, b]))

    assert resultado.evento.datos["registros_leidos"] == 2


def test_i_e07_archivo_que_no_es_utf8(estudio: Estudio) -> None:
    a = estudio.descargas / "latin.ris"
    a.write_bytes("TY  - JOUR\nTI  - Abejas ñ\nER  - \n".encode("latin-1"))

    _rechazada(estudio, estudio.busqueda([a], resultados_interfaz=1), "I-E07")


def test_i_e07_archivo_inexistente(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.descargas / "no_existe.ris"], resultados_interfaz=1)

    _rechazada(estudio, busqueda, "I-E07")


def test_i_e07_csv_sin_mapeo_ilegible(estudio: Estudio) -> None:
    csv_ = escribir(estudio.descargas / "x.csv", '"a"\n"b"\n')
    busqueda = estudio.busqueda(
        [csv_],
        formato="csv",
        mapeo=str(estudio.descargas / "no_existe.json"),
        resultados_interfaz=1,
    )

    _rechazada(estudio, busqueda, "I-E07")


def test_formato_csv_exige_mapeo_y_otro_formato_no_lo_admite(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    sin_mapeo = estudio.busqueda([a], formato="csv")
    error = pytest.raises(ErrorRegistro, estudio.registrar, sin_mapeo)
    assert any("mapeo" in m for m in error.value.errores)

    con_mapeo = estudio.busqueda([a], mapeo=str(a))
    error = pytest.raises(ErrorRegistro, estudio.registrar, con_mapeo)
    assert any("mapeo" in m for m in error.value.errores)


def test_i_e08_diferencia_con_la_interfaz_sin_justificar(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)

    _rechazada(estudio, estudio.busqueda([a], resultados_interfaz=5), "I-E08")


def test_i_e08_con_justificacion_se_registra(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)
    busqueda = estudio.busqueda(
        [a], resultados_interfaz=5, justificacion_diferencia="La interfaz cuenta tres duplicados."
    )

    resultado, _ = estudio.registrar(busqueda)

    assert resultado.evento.datos["justificacion_diferencia"] == (
        "La interfaz cuenta tres duplicados."
    )


def test_i_e09_desviacion_sin_justificar(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    ejecutada = estudio.ecuacion_esperada("scopus") + " AND modificada"

    _rechazada(estudio, estudio.busqueda([a], ecuacion_ejecutada=ejecutada), "I-E09")


def test_desviacion_con_justificacion_se_registra(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    ejecutada = estudio.ecuacion_esperada("scopus") + " AND modificada"
    busqueda = estudio.busqueda(
        [a], ecuacion_ejecutada=ejecutada, justificacion_ecuacion="Se acotó por ruido."
    )

    resultado, terminal = estudio.registrar(busqueda)

    datos = resultado.evento.datos
    assert datos["relacion_ecuacion"] == "desviacion"
    assert datos["justificacion_ecuacion"] == "Se acotó por ruido."
    assert datos["ecuacion_ejecutada"]["hash"] != datos["ecuacion_esperada"]["hash"]
    assert "+ AND modificada" in terminal.texto or "+ modificada" in terminal.texto


def test_la_ecuacion_con_otros_espacios_es_identica(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    ejecutada = estudio.ecuacion_esperada("scopus").replace(" ", "  ")

    resultado, _ = estudio.registrar(estudio.busqueda([a], ecuacion_ejecutada=ejecutada))

    assert resultado.evento.datos["relacion_ecuacion"] == "identica"


def test_i_e10_la_comprobacion_de_git_falla(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    def no_ignora(_raiz: Path, _rutas: object) -> list[str]:
        return ["exportaciones_originales/imp-0001/a.ris no está ignorado por Git"]

    _rechazada(estudio, busqueda, "I-E10", comprobador=no_ignora)


@pytest.mark.parametrize("registrado_por", ["claude", "nadie"])
def test_i_e11_el_revisor_debe_ser_humano_declarado(estudio: Estudio, registrado_por: str) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E11", registrado_por=registrado_por)


def test_i_e12_sin_terminal_interactiva(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    error = _rechazada(estudio, busqueda, "I-E12", interactiva=False)
    assert MENSAJE_SIN_TERMINAL in " ".join(error.errores)


@pytest.mark.parametrize(
    ("configuracion", "fragmento"),
    [
        (None, "no existe"),
        ("fuentes: [esto no es un mapa", "YAML"),
        (
            "fuentes:\n  scopus:\n    campos:\n      resumen:\n        base: {tipo: licencia, "
            "detalle: x, fecha: 2026-10-05}\n",
            "resumen",
        ),
        (
            "fuentes:\n  scopus:\n    campos:\n      campo_inventado:\n        base: {tipo: "
            "licencia, detalle: x, fecha: 2026-10-05}\n",
            "campo_inventado",
        ),
    ],
)
def test_i_e13_configuracion_de_publicacion_invalida(
    tmp_path: Path, configuracion: str | None, fragmento: str
) -> None:
    estudio = crear_estudio(tmp_path, configuracion=configuracion)
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    error = _rechazada(estudio, busqueda, "I-E13")
    assert fragmento in " ".join(error.errores)


def test_se_informan_todos_los_problemas_a_la_vez(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)
    busqueda = estudio.busqueda([a], fuente="wos")

    error = _rechazada(estudio, busqueda, "I-E02", registrado_por="claude")

    assert any("I-E11" in mensaje for mensaje in error.errores)


def test_un_archivo_de_busqueda_con_campos_desconocidos_se_rechaza(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)], campo_inventado=1)

    with pytest.raises(ErrorRegistro) as error:
        estudio.registrar(busqueda)

    assert "campo_inventado" in " ".join(error.value.errores)


# --- Fecha y hora -------------------------------------------------------------------


def test_se_puede_corregir_el_desfase(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    resultado, _ = estudio.registrar(busqueda, respuestas=["2026-10-14", "09:30", "+02:00", FRASE])

    datos = resultado.evento.datos
    assert datos["fecha_hora_busqueda"] == "2026-10-14T09:30+02:00"
    assert datos["fecha_hora_busqueda_utc"] == "2026-10-14T07:30Z"


def test_la_terminal_propone_el_desfase_del_sistema(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _, terminal = estudio.registrar(busqueda)

    assert any("[-05:00]" in pregunta for pregunta in terminal.preguntas)


def test_avisa_si_la_fecha_cae_en_otro_horario_de_verano(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])
    terminal = TerminalSimulada(["2026-10-14", "09:30", "", FRASE])
    from datetime import timedelta

    def desfase(momento: Any) -> timedelta:
        return (
            timedelta(hours=-4)
            if momento.year == 2026
            and momento.month == 10
            and (momento.day == 14 and momento.hour == 9)
            else timedelta(hours=-5)
        )

    modulo_registrar.registrar_busqueda(
        busqueda,
        "investigador-1",
        estudio.raiz,
        terminal,
        reloj=reloj_de_registro(),
        desfase_sistema=desfase,
        comprobador=sin_comprobar_git,
    )

    assert "horario de verano" in terminal.texto


@pytest.mark.parametrize(
    "respuestas",
    [
        ["no es fecha", "otra", "2026-10-14", "09:30", "", FRASE],
        ["2026-10-14", "99:99", "9:30", "09:30", "", FRASE],
    ],
)
def test_las_respuestas_no_validas_se_repreguntan(
    estudio: Estudio, respuestas: list[str | None]
) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    resultado, _ = estudio.registrar(busqueda, respuestas=respuestas)

    assert resultado.evento.datos["fecha_hora_busqueda"] == "2026-10-14T09:30-05:00"


def test_demasiados_intentos_no_validos_cancelan(estudio: Estudio) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])
    antes = estudio.archivos()

    with pytest.raises(OperacionCancelada):
        estudio.registrar(busqueda, respuestas=["x", "y", "z"])

    assert estudio.archivos() == antes


# --- Confirmación y atomicidad ------------------------------------------------------


@pytest.mark.parametrize("frase", ["registrar imp-0002", "si", "", None])
def test_otra_frase_cancela_sin_escribir(estudio: Estudio, frase: str | None) -> None:
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])
    antes = estudio.archivos()

    with pytest.raises(OperacionCancelada):
        estudio.registrar(busqueda, respuestas=["2026-10-14", "09:30", "", frase])

    assert estudio.archivos() == antes


def test_un_original_que_cambia_mientras_se_confirma_cancela(estudio: Estudio) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    busqueda = estudio.busqueda([a])
    terminal = TerminalSimulada(["2026-10-14", "09:30", "", FRASE])

    def modificar_el_original() -> None:
        a.write_text(ris(9), encoding="utf-8", newline="\n")

    terminal.al_preguntar = modificar_el_original
    antes = estudio.archivos()

    with pytest.raises(OperacionCancelada, match="cambió"):
        modulo_registrar.registrar_busqueda(
            busqueda,
            "investigador-1",
            estudio.raiz,
            terminal,
            reloj=reloj_de_registro(),
            desfase_sistema=desfase_menos_cinco,
            comprobador=sin_comprobar_git,
        )

    assert estudio.archivos() == antes
    assert not [
        e
        for e in RegistroEncadenado(RutasProtocolo.desde(estudio.protocolo).eventos).leer()
        if e.tipo == "busqueda_registrada"
    ]


def test_un_fallo_antes_del_evento_deja_la_carpeta_huerfana_y_el_reintento_la_sobrescribe(
    estudio: Estudio, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = estudio.archivo_ris("a.ris", 1, 2)
    busqueda = estudio.busqueda([a])
    original = escribir_atomico
    llamadas = {"n": 0}

    def falla_a_la_tercera(ruta: Path | str, contenido: bytes) -> None:
        llamadas["n"] += 1
        if llamadas["n"] == 3:
            raise OSError("disco lleno")
        original(ruta, contenido)

    monkeypatch.setattr(RUTA_ESCRIBIR, falla_a_la_tercera)
    with pytest.raises(OSError, match="disco lleno"):
        estudio.registrar(busqueda)
    eventos = RegistroEncadenado(RutasProtocolo.desde(estudio.protocolo).eventos)
    assert not [e for e in eventos.leer() if e.tipo == "busqueda_registrada"]
    assert (estudio.raiz / "importaciones" / "imp-0001").is_dir()

    monkeypatch.setattr(RUTA_ESCRIBIR, original)
    resultado, _ = estudio.registrar(busqueda)

    assert resultado.id_importacion == "imp-0001"
    assert leer_estado_registro(RutasProtocolo.desde(estudio.protocolo)).integro


def test_un_fallo_despues_del_evento_se_reconoce(
    estudio: Estudio, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = estudio.archivo_ris("a.ris", 1)
    busqueda = estudio.busqueda([a])

    def falla(_rutas: object) -> None:
        raise OSError("sin permiso")

    monkeypatch.setattr("agentresearch.importacion.registrar.escribir_anclaje", falla)
    with pytest.raises(OSError, match="sin permiso"):
        estudio.registrar(busqueda)
    monkeypatch.undo()

    estado = leer_estado_registro(RutasProtocolo.desde(estudio.protocolo))
    assert estado.integro
    assert len(estado.busquedas) == 1
    _rechazada(estudio, estudio.busqueda([a]), "I-E05")


# --- Versión del protocolo vigente y ecuación esperada ------------------------------


def test_la_version_vigente_es_la_de_la_fecha_de_la_busqueda(estudio: Estudio) -> None:
    from agentresearch.protocolo.aprobacion import enmendar

    nueva = estudio.protocolo.read_text(encoding="utf-8").replace(
        "Estudia el secado del fruto de zarambo.", "Estudia el secado del fruto de zarambo maduro."
    )
    estudio.protocolo.write_text(nueva, encoding="utf-8", newline="\n")
    from datetime import UTC, datetime

    from .apoyo import reloj_incremental

    enmendar(
        estudio.protocolo,
        "menor",
        "investigador-1",
        TerminalSimulada(["enmendar 1.1.0"]),
        justificacion="Aclarar el criterio.",
        efecto_esperado="Menos dudas.",
        reloj=reloj_incremental(datetime(2026, 10, 10, 12, 0, tzinfo=UTC)),
    )
    a = estudio.archivo_ris("a.ris", 1)
    b = estudio.archivo_ris("b.ris", 2)

    antes, _ = estudio.registrar(
        estudio.busqueda([a]), respuestas=["2026-10-05", "09:30", "", FRASE]
    )
    despues, _ = estudio.registrar(
        estudio.busqueda([b]), respuestas=["2026-10-14", "09:30", "", "registrar imp-0002"]
    )

    assert antes.evento.datos["version_protocolo"] == "1.0.0"
    assert despues.evento.datos["version_protocolo"] == "1.1.0"


def test_la_ecuacion_esperada_sale_de_ecuaciones_md_o_se_regenera(estudio: Estudio) -> None:
    from agentresearch.protocolo.ecuaciones.servicio import generar

    a = estudio.archivo_ris("a.ris", 1)
    b = estudio.archivo_ris("b.ris", 2)
    regenerada, _ = estudio.registrar(estudio.busqueda([a]))

    generar(estudio.protocolo, escribir=True)
    desde_md, _ = estudio.registrar(
        estudio.busqueda([b]), respuestas=["2026-10-14", "09:30", "", "registrar imp-0002"]
    )

    assert regenerada.evento.datos["ecuacion_esperada"]["origen"] == "regenerada"
    assert desde_md.evento.datos["ecuacion_esperada"]["origen"] == "ecuaciones_md"
    assert (
        regenerada.evento.datos["ecuacion_esperada"]["hash"]
        == desde_md.evento.datos["ecuacion_esperada"]["hash"]
    )


# --- git check-ignore (repositorios temporales) -------------------------------------

requiere_git = pytest.mark.skipif(shutil.which("git") is None, reason="Git no está instalado")


def _git(raiz: Path, *argumentos: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *argumentos],
        cwd=raiz,
        check=True,
        capture_output=True,
    )


@requiere_git
def test_git_acepta_un_destino_ignorado(estudio: Estudio) -> None:
    _git(estudio.raiz, "init", "-q")
    escribir(estudio.raiz / ".gitignore", "exportaciones_originales/\n")
    destino = estudio.raiz / "exportaciones_originales" / "imp-0001" / "a.ris"

    assert comprobar_con_git(estudio.raiz, [destino]) == []


@requiere_git
def test_git_rechaza_un_destino_no_ignorado(estudio: Estudio) -> None:
    _git(estudio.raiz, "init", "-q")
    destino = estudio.raiz / "exportaciones_originales" / "imp-0001" / "a.ris"

    [problema] = comprobar_con_git(estudio.raiz, [destino])

    assert "no está ignorado" in problema
    assert "estudio actualizar" in problema


@requiere_git
def test_git_rechaza_un_archivo_ya_agregado_al_indice(estudio: Estudio) -> None:
    _git(estudio.raiz, "init", "-q")
    escribir(estudio.raiz / ".gitignore", "descargas_internas/\n")
    (estudio.raiz / "descargas_internas").mkdir()
    interno = escribir(estudio.raiz / "descargas_internas" / "a.ris", ris(1))
    _git(estudio.raiz, "add", "-f", "descargas_internas/a.ris")

    [problema] = comprobar_con_git(estudio.raiz, [interno])

    assert "no está ignorado" in problema


@requiere_git
def test_git_rechaza_si_no_es_un_repositorio(tmp_path: Path) -> None:
    raiz = tmp_path / "suelto"
    raiz.mkdir()

    [problema] = comprobar_con_git(raiz, [raiz / "exportaciones_originales" / "a.ris"])

    assert "no se pudo comprobar con Git" in problema


def test_sin_git_instalado_el_comando_se_niega(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sin_git(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", sin_git)

    [problema] = comprobar_con_git(tmp_path, [tmp_path / "a.ris"])

    assert "Git no está instalado" in problema


@requiere_git
def test_el_registro_completo_con_git_real(estudio: Estudio) -> None:
    _git(estudio.raiz, "init", "-q")
    escribir(estudio.raiz / ".gitignore", "exportaciones_originales/\n")
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    resultado, _ = estudio.registrar(busqueda, comprobador=comprobar_con_git)

    assert resultado.id_importacion == "imp-0001"


@requiere_git
def test_el_registro_con_git_real_se_niega_sin_el_gitignore(estudio: Estudio) -> None:
    _git(estudio.raiz, "init", "-q")
    busqueda = estudio.busqueda([estudio.archivo_ris("a.ris", 1)])

    _rechazada(estudio, busqueda, "I-E10", comprobador=comprobar_con_git)
