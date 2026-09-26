"""Datos compartidos por las pruebas."""

import copy
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

RUTA_PROTOCOLO_SINTETICO = Path(__file__).parent / "datos" / "protocolo_sintetico.yaml"

_datos_sinteticos: dict[str, Any] = YAML(typ="safe").load(
    RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8")
)


@pytest.fixture
def datos_sinteticos() -> dict[str, Any]:
    """Protocolo sintético válido como diccionario de Python, listo para modificar."""
    return copy.deepcopy(_datos_sinteticos)
