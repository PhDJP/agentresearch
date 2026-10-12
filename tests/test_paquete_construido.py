"""Pruebas del paquete construido: los datos que el código lee deben estar en el wheel.

Una prueba normal solo ve el repositorio, donde el archivo siempre existe. Esta
construye el wheel y mira dentro, porque `politica_datos.yaml` y las plantillas
deben viajar con el paquete instalado (ADR-0010, punto 4).

Está marcada `construccion` y queda fuera de la ejecución por defecto de pytest:
`uv build` necesita `uv` y puede necesitar red para obtener el sistema de
construcción. Se ejecuta con `uv run pytest -m construccion --no-cov`, y la
integración continua lo hace en un paso propio.
"""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE = RAIZ / "src" / "agentresearch"
POLITICA = "agentresearch/registros/politica_datos.yaml"


def _archivos_de_datos() -> list[Path]:
    """Archivos del paquete que no son código: plantillas y políticas."""
    return sorted(
        ruta
        for ruta in PAQUETE.rglob("*")
        if ruta.is_file() and ruta.suffix not in {".py", ".pyc"} and "__pycache__" not in ruta.parts
    )


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> zipfile.ZipFile:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv no está instalado: no se puede construir el wheel")
    destino = tmp_path_factory.mktemp("wheel")
    resultado = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(destino)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    ruedas = list(destino.glob("*.whl"))
    assert len(ruedas) == 1
    return zipfile.ZipFile(ruedas[0])


@pytest.mark.construccion
def test_la_politica_de_datos_esta_en_el_wheel(wheel: zipfile.ZipFile) -> None:
    assert POLITICA in wheel.namelist()
    assert wheel.read(POLITICA) == (PAQUETE / "registros" / "politica_datos.yaml").read_bytes()


@pytest.mark.construccion
def test_todos_los_archivos_de_datos_del_paquete_estan_en_el_wheel(wheel: zipfile.ZipFile) -> None:
    contenido = set(wheel.namelist())
    datos = _archivos_de_datos()

    assert datos, "el paquete debe tener archivos de datos"
    faltan = [
        ruta.relative_to(PAQUETE.parent).as_posix()
        for ruta in datos
        if ruta.relative_to(PAQUETE.parent).as_posix() not in contenido
    ]
    assert faltan == []
