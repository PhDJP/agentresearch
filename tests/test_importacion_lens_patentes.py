"""Exportación de patentes de Lens en CSV: el mapeo de la skill `/importar` (sintético; ficticio).

Los nombres de columna son los observados en una exportación real (2026-10-20); todos los
valores de las filas son inventados.
"""

import json
import re
from importlib.resources import files
from pathlib import Path

from agentresearch.importacion.mapeo import Mapeo
from agentresearch.importacion.servicio import leer

from .apoyo_importacion import csv_texto, escribir

ENCABEZADO = [
    "#", "Jurisdiction", "Kind", "Display Key", "Lens ID", "Publication Date",
    "Publication Year", "Application Number", "Application Date", "Priority Numbers",
    "Earliest Priority Date", "Title", "Abstract", "Applicants", "Inventors", "Owners", "URL",
    "Document Type", "Has Full Text", "Cites Patent Count", "Cited by Patent Count",
    "Simple Family Size", "Legal Status",
]  # fmt: skip


def _mapeo_de_la_skill(tmp_path: Path) -> Mapeo:
    """El segundo bloque JSON de `formatos.md`: el ejemplo de Lens para patentes."""
    texto = (
        files("agentresearch.estudio")
        .joinpath("plantillas", "claude", "skills", "importar", "formatos.md")
        .read_bytes()
        .decode("utf-8")
    )
    bloques = re.findall(r"```json\n(.*?)\n```", texto, re.DOTALL)
    ruta = tmp_path / "mapeo.json"
    ruta.write_text(json.dumps(json.loads(bloques[-1])), encoding="utf-8")
    return Mapeo.cargar(ruta)


def _fila(numero: int, inventores: str, tipo: str) -> list[str]:
    base = {c: "" for c in ENCABEZADO}
    base.update(
        {
            "#": str(numero),
            "Jurisdiction": "US",
            "Kind": "A1",
            "Lens ID": f"000-000-000-000-{numero:03d}",
            "Publication Year": "2024",
            "Title": f"Método ficticio de secado {numero}",
            "Abstract": "Resumen ficticio de una patente inventada.",
            "Inventors": inventores,
            "Document Type": tipo,
        }
    )
    return [base[c] for c in ENCABEZADO]


def test_el_mapeo_de_la_skill_lee_una_exportacion_de_patentes(tmp_path: Path) -> None:
    texto = csv_texto(
        ENCABEZADO,
        [_fila(1, "Cristal, A; Vidrio, B", "Patent Application"), _fila(2, "", "Granted Patent")],
    )
    ruta = escribir(tmp_path / "lens.csv", texto, bom=True, fin_de_linea="\r\n")

    resultado = leer(ruta, "csv", "lens", _mapeo_de_la_skill(tmp_path))

    primero, segundo = resultado.registros
    assert primero.tipo_id_fuente == "lens_id"
    assert primero.id_fuente == "000-000-000-000-001"
    assert primero.titulo == "Método ficticio de secado 1"
    assert primero.anio == 2024
    assert primero.autores == ("Cristal, A", "Vidrio, B")
    assert primero.tipo_documento == "Patent Application"
    assert segundo.tipo_documento == "Granted Patent"
    assert primero.resumen == "Resumen ficticio de una patente inventada."
    # Lo demás se conserva en `otros`, con el nombre de la columna.
    assert primero.otros["Jurisdiction"] == "US"


def test_una_patente_no_tiene_doi_y_lo_avisa_l_a04(tmp_path: Path) -> None:
    ruta = escribir(tmp_path / "lens.csv", csv_texto(ENCABEZADO, [_fila(1, "A", "Granted Patent")]))

    resultado = leer(ruta, "csv", "lens", _mapeo_de_la_skill(tmp_path))

    avisos = [(h.regla, h.mensaje) for h in resultado.hallazgos]
    assert [regla for regla, _ in avisos] == ["L-A04"]
    assert "«doi»" in avisos[0][1]
