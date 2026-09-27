"""Pruebas de la aprobación del protocolo (ADR-0008, puntos 5, 9, 10, 11 y 14)."""

import difflib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo import RutasProtocolo, validar_archivo
from agentresearch.protocolo.aprobacion import ErrorCicloDeVida, OperacionCancelada, aprobar
from agentresearch.protocolo.archivo import leer_bytes_protocolo
from agentresearch.protocolo.terminal import MENSAJE_SIN_TERMINAL
from agentresearch.trazabilidad import (
    RegistroEncadenado,
    escribir_atomico,
    escritura,
    hash_archivo,
    hash_bytes,
)
from agentresearch.trazabilidad import registro as registro_encadenado

from .apoyo import (
    TerminalSimulada,
    agregar_evento,
    aprobar_protocolo,
    decision_propuesta,
    reemplazar_en,
    reloj_incremental,
)


def _archivos_del_ciclo(ruta: Path) -> list[str]:
    """Archivos del directorio del protocolo, aparte del propio protocolo."""
    return sorted(
        p.relative_to(ruta.parent).as_posix()
        for p in ruta.parent.rglob("*")
        if p.is_file() and p != ruta
    )


def _con_advertencias(ruta: Path) -> None:
    """Deja el protocolo con dos advertencias: P-A08 (un revisor humano) y P-A09 (piloto 0)."""
    reemplazar_en(ruta, "    - id: investigador-2\n      tipo: humano\n", "")
    reemplazar_en(ruta, "tamano: 20", "tamano: 0")


# --- Aprobación correcta -------------------------------------------------------------


def test_aprobar_un_borrador_valido(protocolo_de_estudio: Path) -> None:
    original = protocolo_de_estudio.read_bytes()
    terminal = TerminalSimulada(["aprobar 1.0.0"])

    resultado = aprobar(protocolo_de_estudio, "investigador-1", terminal, reloj=reloj_incremental())

    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    validacion = validar_archivo(protocolo_de_estudio)
    assert validacion.estado == "vigente"
    assert validacion.version_protocolo == "1.0.0"
    assert validacion.hallazgos == []
    assert resultado.version_anterior == "0.1.0"
    assert resultado.version_protocolo == "1.0.0"
    assert resultado.hash_protocolo == hash_archivo(protocolo_de_estudio)
    assert rutas.copia_de_version("1.0.0").read_bytes() == protocolo_de_estudio.read_bytes()
    [evento] = RegistroEncadenado(rutas.eventos).leer()
    assert evento == resultado.evento
    assert evento.tipo == "protocolo_aprobado"
    assert evento.fecha_hora_utc == "2026-09-26T12:00:00.000Z"
    assert evento.datos == {
        "version_anterior": "0.1.0",
        "version_protocolo": "1.0.0",
        "hash_revisado": hash_bytes(original),
        "hash_protocolo": resultado.hash_protocolo,
        "ruta_protocolo": "protocolo/protocolo.yaml",
        "ruta_version": "protocolo/versiones/1.0.0.yaml",
        "aprobado_por": {"tipo": "humano", "id": "investigador-1"},
        "advertencias": [],
    }
    assert json.loads(rutas.anclaje.read_text(encoding="utf-8")) == {
        "hash_ultimo": evento.hash,
        "numero_eventos": 1,
        "registro": "protocolo/eventos.jsonl",
    }
    assert str(resultado.anclaje) == f"evt-000001@{evento.hash}"


def test_aprobar_solo_cambia_el_estado_y_la_version(protocolo_de_estudio: Path) -> None:
    original = protocolo_de_estudio.read_text(encoding="utf-8").splitlines()

    aprobar_protocolo(protocolo_de_estudio)

    nuevo = protocolo_de_estudio.read_text(encoding="utf-8").splitlines()
    cambios = [
        linea
        for linea in difflib.unified_diff(original, nuevo, lineterm="", n=0)
        if linea.startswith(("+", "-")) and not linea.startswith(("+++", "---"))
    ]
    assert cambios == [
        "-estado: borrador",
        "+estado: vigente",
        '-  version_protocolo: "0.1.0"',
        '+  version_protocolo: "1.0.0"',
    ]
    assert protocolo_de_estudio.read_bytes().count(b"# ") == "\n".join(original).count("# ")


def test_las_rutas_guardadas_son_relativas_y_usan_barra(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    for archivo in (rutas.eventos, rutas.anclaje):
        contenido = archivo.read_text(encoding="utf-8")
        assert str(rutas.estudio) not in contenido
        assert rutas.estudio.as_posix() not in contenido
        assert "\\\\" not in contenido
        assert b"\r" not in archivo.read_bytes()


def test_el_resumen_muestra_version_hash_y_aprobador(protocolo_de_estudio: Path) -> None:
    terminal = TerminalSimulada(["aprobar 1.0.0"])

    resultado = aprobar(protocolo_de_estudio, "investigador-1", terminal)

    assert "Aprobación del protocolo protocolo/protocolo.yaml" in terminal.texto
    assert "versión: 0.1.0 → 1.0.0 (borrador → vigente)" in terminal.texto
    assert f"hash del protocolo aprobado: {resultado.hash_protocolo}" in terminal.texto
    assert "aprobado por: investigador-1" in terminal.texto
    assert "decisiones confirmadas: ninguna" in terminal.texto
    assert "Advertencias activas: ninguna" in terminal.texto
    assert terminal.preguntas == [
        "Escriba «aprobar 1.0.0» para confirmar, o cualquier otra cosa para cancelar: "
    ]


def test_el_protocolo_se_lee_una_sola_vez(
    protocolo_de_estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lecturas: list[Path] = []

    def _leer(ruta: Path | str) -> bytes:
        lecturas.append(Path(ruta))
        return leer_bytes_protocolo(ruta)

    monkeypatch.setattr("agentresearch.protocolo.validacion.leer_bytes_protocolo", _leer)

    aprobar_protocolo(protocolo_de_estudio)

    assert len(lecturas) == 1


# --- Rechazos (no se escribe nada) --------------------------------------------------


def test_aprobar_con_errores_falla(protocolo_de_estudio: Path) -> None:
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 0")
    original = protocolo_de_estudio.read_bytes()

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar_protocolo(protocolo_de_estudio)

    [mensaje] = error.value.errores
    assert mensaje.startswith("error P-E08 en seleccion.tamano_lote_llm")
    assert protocolo_de_estudio.read_bytes() == original
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


def test_aprobar_un_archivo_ilegible_falla_con_p_e00(protocolo_de_estudio: Path) -> None:
    protocolo_de_estudio.write_text("estado: [\n", encoding="utf-8", newline="\n")

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar_protocolo(protocolo_de_estudio)

    assert error.value.errores[0].startswith("error P-E00")


def test_aprobar_dos_veces_falla(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar_protocolo(protocolo_de_estudio)

    assert error.value.errores == [
        "el protocolo ya está vigente; todo cambio posterior se registra con "
        "`agentresearch protocolo enmendar`"
    ]
    assert len(RegistroEncadenado(protocolo_de_estudio.parent / "eventos.jsonl").leer()) == 1


def test_aprobar_un_borrador_con_version_mayor_falla(protocolo_de_estudio: Path) -> None:
    reemplazar_en(protocolo_de_estudio, 'version_protocolo: "0.1.0"', 'version_protocolo: "2.0.0"')

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar_protocolo(protocolo_de_estudio)

    assert error.value.errores == [
        "un borrador lleva una versión 0.y.z, y este tiene la 2.0.0; la aprobación fija la "
        "versión 1.0.0"
    ]


@pytest.mark.parametrize(
    ("aprobado_por", "fragmento"),
    [
        ("claude", "es un revisor de tipo llm; el LLM propone, pero decide el investigador"),
        ("desconocido", "no es un revisor humano declarado en seleccion.revisores"),
    ],
)
def test_aprobar_exige_un_revisor_humano_declarado(
    protocolo_de_estudio: Path, aprobado_por: str, fragmento: str
) -> None:
    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar(protocolo_de_estudio, aprobado_por, TerminalSimulada(["aprobar 1.0.0"]))

    [mensaje] = error.value.errores
    assert fragmento in mensaje
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


def test_aprobar_con_decisiones_pendientes_falla(protocolo_de_estudio: Path) -> None:
    agregar_evento(protocolo_de_estudio, "decision_propuesta", decision_propuesta("O1"))
    agregar_evento(protocolo_de_estudio, "decision_propuesta", decision_propuesta("O2"))

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar_protocolo(protocolo_de_estudio)

    [mensaje] = error.value.errores
    assert mensaje.startswith("hay decisiones pendientes de confirmar (O1, O2)")


def test_aprobar_sin_terminal_interactiva_falla(protocolo_de_estudio: Path) -> None:
    terminal = TerminalSimulada(["aprobar 1.0.0"], interactiva=False)

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar(protocolo_de_estudio, "investigador-1", terminal)

    assert error.value.errores == [MENSAJE_SIN_TERMINAL]
    assert terminal.preguntas == []
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


def test_sin_terminal_se_informan_antes_los_errores_del_protocolo(
    protocolo_de_estudio: Path,
) -> None:
    reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 0")

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar(protocolo_de_estudio, "investigador-1", TerminalSimulada(interactiva=False))

    assert error.value.errores[0].startswith("error P-E08")


@pytest.mark.parametrize("respuesta", ["aprobar", "APROBAR 1.0.0", "", None])
def test_aprobar_sin_la_frase_exacta_se_cancela(
    protocolo_de_estudio: Path, respuesta: str | None
) -> None:
    original = protocolo_de_estudio.read_bytes()

    with pytest.raises(OperacionCancelada, match="no se escribió «aprobar 1.0.0»"):
        aprobar_protocolo(protocolo_de_estudio, [respuesta])

    assert protocolo_de_estudio.read_bytes() == original
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


def test_la_frase_admite_espacios_alrededor(protocolo_de_estudio: Path) -> None:
    aprobar_protocolo(protocolo_de_estudio, ["  aprobar 1.0.0  "])

    assert validar_archivo(protocolo_de_estudio).estado == "vigente"


def test_si_el_archivo_cambia_mientras_se_confirma_se_cancela(protocolo_de_estudio: Path) -> None:
    def _editar() -> None:
        reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 26")

    terminal = TerminalSimulada(["aprobar 1.0.0"], al_preguntar=_editar)

    with pytest.raises(OperacionCancelada, match="cambió mientras se confirmaba"):
        aprobar(protocolo_de_estudio, "investigador-1", terminal)

    assert b"tamano_lote_llm: 26" in protocolo_de_estudio.read_bytes()
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


# --- Justificación de las advertencias (ADR-0008, punto 10) ------------------------


def _escribir_justificaciones(tmp_path: Path, entradas: list[dict[str, Any]]) -> Path:
    archivo = tmp_path / "justificaciones.json"
    archivo.write_text(
        json.dumps({"justificaciones": entradas}, ensure_ascii=False), encoding="utf-8"
    )
    return archivo


def test_cada_advertencia_queda_justificada_desde_archivo_o_terminal(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    _con_advertencias(protocolo_de_estudio)
    archivo = _escribir_justificaciones(
        tmp_path,
        [
            {
                "id_regla": "P-A08",
                "ubicacion": "seleccion.revisores",
                "justificacion": "Solo hay un investigador; el segundo revisor es el LLM.",
            }
        ],
    )
    terminal = TerminalSimulada(["  El tamaño se fija tras la búsqueda.  ", "aprobar 1.0.0"])

    resultado = aprobar(protocolo_de_estudio, "investigador-1", terminal, archivo)

    advertencias = resultado.evento.datos["advertencias"]
    assert [(a["id_regla"], a["origen"], a["justificacion"]) for a in advertencias] == [
        ("P-A08", "archivo", "Solo hay un investigador; el segundo revisor es el LLM."),
        ("P-A09", "terminal", "El tamaño se fija tras la búsqueda."),
    ]
    assert advertencias[1]["ubicacion"] == "seleccion.piloto.tamano"
    assert advertencias[1]["referencia"].startswith("Ali y Petersen (2014)")
    assert "Advertencias activas: 2, cada una con su justificación" in terminal.texto
    assert "justificación (archivo): Solo hay un investigador" in terminal.texto
    assert terminal.preguntas[0] == "    justificación: "


@pytest.mark.parametrize("respuesta", ["   ", None])
def test_una_advertencia_sin_justificacion_cancela_la_aprobacion(
    protocolo_de_estudio: Path, respuesta: str | None
) -> None:
    _con_advertencias(protocolo_de_estudio)

    with pytest.raises(OperacionCancelada, match="P-A08 necesita una justificación"):
        aprobar_protocolo(protocolo_de_estudio, [respuesta])

    assert _archivos_del_ciclo(protocolo_de_estudio) == []


@pytest.mark.parametrize(
    ("entradas", "fragmento"),
    [
        (
            [{"id_regla": "P-A01", "ubicacion": "criterios", "justificacion": "x"}],
            "P-A01 en criterios no corresponde a ninguna advertencia activa",
        ),
        (
            [{"id_regla": "P-A09", "justificacion": "x"}],
            "P-A09 en (sin ubicación) no corresponde",
        ),
        (
            [
                {"id_regla": "P-A08", "ubicacion": "seleccion.revisores", "justificacion": "x"},
                {"id_regla": "P-A08", "ubicacion": "seleccion.revisores", "justificacion": "y"},
            ],
            "P-A08 en seleccion.revisores está repetida",
        ),
        (
            [{"id_regla": "P-A08", "ubicacion": "seleccion.revisores", "justificacion": " "}],
            "la justificación de P-A08 en seleccion.revisores está vacía",
        ),
        (
            [{"id_regla": "P-A08", "ubicacion": "seleccion.revisores", "texto": "x"}],
            "texto: clave no permitida",
        ),
    ],
)
def test_archivo_de_justificaciones_no_valido(
    protocolo_de_estudio: Path, tmp_path: Path, entradas: list[dict[str, Any]], fragmento: str
) -> None:
    _con_advertencias(protocolo_de_estudio)
    archivo = _escribir_justificaciones(tmp_path, entradas)

    with pytest.raises(ErrorCicloDeVida) as error:
        aprobar(protocolo_de_estudio, "investigador-1", TerminalSimulada(), archivo)

    assert any(fragmento in mensaje for mensaje in error.value.errores), error.value.errores
    assert _archivos_del_ciclo(protocolo_de_estudio) == []


def test_archivo_de_justificaciones_inexistente(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    with pytest.raises(ErrorCicloDeVida, match="no existe"):
        aprobar(protocolo_de_estudio, "investigador-1", TerminalSimulada(), tmp_path / "no.json")


# --- Atomicidad (ADR-0008, puntos 14 y 15) -----------------------------------------


def test_orden_de_escritura_y_sincronizacion(
    protocolo_de_estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operaciones: list[str] = []
    fsync_original = os.fsync
    replace_original = os.replace

    def _fsync(descriptor: int) -> None:
        operaciones.append("fsync")
        fsync_original(descriptor)

    def _replace(origen: str, destino: str) -> None:
        operaciones.append(f"replace {Path(destino).name}")
        replace_original(origen, destino)

    def _directorio(directorio: Path | str) -> None:
        # Solo sincroniza en POSIX; aquí se registra en todos los sistemas.
        operaciones.append(f"directorio {Path(directorio).name}")

    monkeypatch.setattr(os, "fsync", _fsync)
    monkeypatch.setattr(os, "replace", _replace)
    monkeypatch.setattr(escritura, "sincronizar_directorio", _directorio)
    monkeypatch.setattr(registro_encadenado, "sincronizar_directorio", _directorio)

    aprobar_protocolo(protocolo_de_estudio)

    assert operaciones == [
        "fsync",
        "replace 1.0.0.yaml",
        "directorio versiones",
        "fsync",  # el evento, antes de tocar el protocolo
        "directorio protocolo",  # el registro se acaba de crear
        "fsync",
        "replace anclaje.json",
        "directorio protocolo",
        "fsync",
        "replace protocolo.yaml",
        "directorio protocolo",
    ]


def test_un_fallo_antes_del_evento_no_confirma_nada(
    protocolo_de_estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = protocolo_de_estudio.read_bytes()

    def _falla(*_argumentos: object, **_opciones: object) -> None:
        raise OSError("fallo simulado al escribir el evento")

    monkeypatch.setattr(RegistroEncadenado, "agregar", _falla)

    with pytest.raises(OSError, match="simulado"):
        aprobar_protocolo(protocolo_de_estudio)
    monkeypatch.undo()

    assert protocolo_de_estudio.read_bytes() == original
    assert _archivos_del_ciclo(protocolo_de_estudio) == ["versiones/1.0.0.yaml"]
    # En la primera aprobación, la copia huérfana dispara P-E10 (ADR-0008, punto 15).
    [hallazgo] = validar_archivo(protocolo_de_estudio).hallazgos
    assert hallazgo.id_regla == "P-E10"
    with pytest.raises(ErrorCicloDeVida, match="P-E10"):
        aprobar_protocolo(protocolo_de_estudio)


def test_un_fallo_despues_del_evento_se_recupera_con_la_copia(
    protocolo_de_estudio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _escribir(ruta: Path | str, contenido: bytes) -> None:
        if Path(ruta).name == "protocolo.yaml":
            raise OSError("fallo simulado al reemplazar el protocolo")
        escribir_atomico(ruta, contenido)

    monkeypatch.setattr("agentresearch.protocolo.aprobacion.escribir_atomico", _escribir)

    with pytest.raises(OSError, match="simulado"):
        aprobar_protocolo(protocolo_de_estudio)
    monkeypatch.undo()

    [hallazgo] = validar_archivo(protocolo_de_estudio).hallazgos
    assert hallazgo.id_regla == "P-E09"
    assert "se interrumpió antes de actualizar protocolo/protocolo.yaml" in hallazgo.mensaje
    copia = protocolo_de_estudio.parent / "versiones" / "1.0.0.yaml"
    protocolo_de_estudio.write_bytes(copia.read_bytes())
    assert validar_archivo(protocolo_de_estudio).hallazgos == []
