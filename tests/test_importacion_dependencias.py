"""Las dependencias del lector de BibTeX tienen la versión exacta fijada (ADR-0010, punto 24)."""

from importlib.metadata import version

from bibtexparser.entrypoint import parse_string
from pylatexenc.latex2text import LatexNodes2Text


def test_versiones_fijadas() -> None:
    assert version("bibtexparser") == "2.0.1"
    assert version("pylatexenc") == "2.11"


def test_la_clave_repetida_se_puede_recuperar_de_ignore_error_block() -> None:
    texto = "@article{a,\n title={Uno}\n}\n@article{a,\n title={Dos}\n}\n"
    biblioteca = parse_string(texto)
    assert len(biblioteca.entries) == 1
    bloque = biblioteca.failed_blocks[0]
    assert type(bloque).__name__ == "DuplicateBlockKeyBlock"
    assert not hasattr(bloque, "duplicate_block")
    assert bloque.ignore_error_block is not None


def test_pylatexenc_decodifica_tildes() -> None:
    assert LatexNodes2Text().latex_to_text(r"{\'e}") == "é"
