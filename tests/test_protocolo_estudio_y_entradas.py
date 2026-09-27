"""Pruebas de las rutas del estudio y de la lectura estricta de archivos JSON de entrada."""

from pathlib import Path

import pytest

from agentresearch.protocolo.entradas import ErrorEntrada, cargar_json, leer_json, validar_modelo
from agentresearch.protocolo.estudio import RutasProtocolo, es_ruta_relativa_valida
from agentresearch.protocolo.eventos import PersonaHumana

# --- Rutas -------------------------------------------------------------------------


def test_rutas_del_protocolo_por_convencion(tmp_path: Path) -> None:
    rutas = RutasProtocolo.desde(tmp_path / "estudio" / "protocolo" / "protocolo.yaml")

    assert rutas.estudio == (tmp_path / "estudio").resolve()
    assert rutas.eventos.name == "eventos.jsonl"
    assert rutas.anclaje.name == "anclaje.json"
    assert rutas.relativa(rutas.copia_de_version("1.2.0")) == "protocolo/versiones/1.2.0.yaml"
    assert rutas.relativa(rutas.protocolo) == "protocolo/protocolo.yaml"


def test_resolver_una_ruta_guardada(tmp_path: Path) -> None:
    rutas = RutasProtocolo.desde(tmp_path / "estudio" / "protocolo" / "protocolo.yaml")

    assert rutas.resolver("protocolo/versiones/1.0.0.yaml") == rutas.copia_de_version("1.0.0")
    with pytest.raises(ValueError, match="no válida"):
        rutas.resolver("../fuera.yaml")


@pytest.mark.parametrize(
    ("texto", "valida"),
    [
        ("protocolo/versiones/1.0.0.yaml", True),
        ("protocolo/eventos.jsonl", True),
        ("", False),
        ("/protocolo/eventos.jsonl", False),
        ("C:/estudio/protocolo.yaml", False),
        ("protocolo\\eventos.jsonl", False),
        ("protocolo/../fuera.yaml", False),
        ("./protocolo/eventos.jsonl", False),
        ("protocolo//eventos.jsonl", False),
    ],
)
def test_es_ruta_relativa_valida(texto: str, valida: bool) -> None:
    assert es_ruta_relativa_valida(texto) is valida


# --- Entradas JSON -------------------------------------------------------------------


def test_leer_json_de_un_archivo(tmp_path: Path) -> None:
    ruta = tmp_path / "entrada.json"
    ruta.write_text('{"clave": "valor con tilde: ción"}', encoding="utf-8")

    assert leer_json(ruta) == {"clave": "valor con tilde: ción"}


def test_leer_json_de_un_archivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ErrorEntrada, match="no existe"):
        leer_json(tmp_path / "no_existe.json")


def test_leer_json_de_un_directorio(tmp_path: Path) -> None:
    with pytest.raises(ErrorEntrada, match="no se pudo leer"):
        leer_json(tmp_path)


@pytest.mark.parametrize(
    ("contenido", "fragmento"),
    [
        (b"\xff\xfe", "no está codificado en UTF-8"),
        (b'{"a": 1,}', "no es JSON válido (línea 1"),
        (b'{"a": 1, "a": 2}', "repite la clave 'a'"),
        (b'{"b": {"a": 1, "a": 2}}', "repite la clave 'a'"),
    ],
)
def test_cargar_json_rechaza_entradas_no_validas(contenido: bytes, fragmento: str) -> None:
    with pytest.raises(ErrorEntrada) as error:
        cargar_json(contenido, "entrada.json")

    [mensaje] = error.value.errores
    assert mensaje.startswith("entrada.json ")
    assert fragmento in mensaje


def test_validar_modelo_reporta_todos_los_errores_en_espanol() -> None:
    with pytest.raises(ErrorEntrada) as error:
        validar_modelo(PersonaHumana, {"tipo": "llm", "extra": 1}, "persona")

    assert error.value.errores == [
        "persona: tipo: valor no permitido; se admite 'humano'; valor recibido: 'llm'",
        "persona: id: falta este campo obligatorio",
        "persona: extra: clave no permitida por el esquema",
    ]
    assert str(error.value).startswith("persona: tipo:")


def test_validar_modelo_devuelve_el_modelo() -> None:
    persona = validar_modelo(PersonaHumana, {"tipo": "humano", "id": "investigador-1"}, "p")

    assert persona.id == "investigador-1"
