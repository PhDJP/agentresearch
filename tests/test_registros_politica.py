"""Pruebas de la política del paquete y de la configuración de publicación del estudio.

Todo con datos sintéticos: instituciones, revistas y fechas ficticias.
"""

from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import pytest

from agentresearch.registros import RegistroNormalizado, politica
from agentresearch.registros.politica import (
    CAMPOS_HABILITABLES,
    NOMBRE_POLITICA,
    NUNCA_PUBLICABLES_MINIMOS,
    Base,
    ErrorConfiguracionPublicacion,
    ErrorPoliticaDatos,
    PoliticaDatos,
    cargar_configuracion,
    cargar_politica,
    decodificar_configuracion,
    hash_configuracion,
    hash_politica,
    leer_bytes_politica,
)
from agentresearch.trazabilidad import hash_bytes

HOY = datetime(2026, 10, 12, 15, 30, tzinfo=UTC)


def reloj() -> datetime:
    return HOY


BASE_COMPLETA = (
    "{tipo: institucion, detalle: Biblioteca Ficticia, medio: correo, fecha: '2026-09-29'}"
)


def configuracion(texto: str) -> bytes:
    return texto.encode("utf-8")


def problemas_de(texto: str) -> list[str]:
    """Textos de los problemas que lanza la carga de `texto`."""
    with pytest.raises(ErrorConfiguracionPublicacion) as informado:
        decodificar_configuracion(configuracion(texto), reloj=reloj)
    return [str(problema) for problema in informado.value.problemas]


# ---------------------------------------------------- política del paquete


def test_la_politica_se_lee_como_recurso_del_paquete() -> None:
    """El archivo debe estar dentro del paquete, no solo en el repositorio."""
    recurso = files("agentresearch.registros").joinpath(NOMBRE_POLITICA)

    assert recurso.is_file()
    assert leer_bytes_politica() == recurso.read_bytes()
    assert hash_politica() == hash_bytes(recurso.read_bytes())


def test_la_politica_del_paquete_es_valida_y_neutral() -> None:
    politica_cargada = cargar_politica()

    assert politica_cargada.version == 1
    assert NUNCA_PUBLICABLES_MINIMOS <= set(politica_cargada.nunca_publicables)
    assert {"scopus", "wos", "acs", "lens"} <= set(politica_cargada.fuentes)
    for fuente in politica_cargada.fuentes.values():
        assert set(fuente.campos_habilitables) <= set(CAMPOS_HABILITABLES)
        assert not set(fuente.campos_habilitables) & set(politica_cargada.nunca_publicables)


def test_los_campos_habilitables_son_campos_del_registro() -> None:
    assert set(CAMPOS_HABILITABLES) <= set(RegistroNormalizado.model_fields)


def test_el_hash_de_la_politica_cambia_si_cambia_el_archivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = hash_politica()

    monkeypatch.setattr(politica, "leer_bytes_politica", lambda: leer_bytes_politica() + b"\n#")

    assert hash_politica() != original


POLITICA_MINIMA = """
version: 1
nunca_publicables: [resumen, palabras_clave_autor, palabras_clave_indexadas, referencias,
  conteos_citas, afiliaciones, financiacion]
fuentes:
  scopus:
    campos_habilitables: [titulo, doi]
"""


def test_una_politica_minima_valida_se_carga() -> None:
    cargada = cargar_politica(POLITICA_MINIMA.encode())

    assert isinstance(cargada, PoliticaDatos)
    assert cargada.fuentes["scopus"].campos_habilitables == ["titulo", "doi"]


@pytest.mark.parametrize(
    ("viejo", "nuevo", "fragmento"),
    [
        ("[titulo, doi]", "[titulo, resumen]", "resumen"),  # un nunca publicable habilitable
        ("[titulo, doi]", "[titulo, inventado]", "inventado"),
        ("[titulo, doi]", "[titulo, titulo]", "repetidos"),
        ("version: 1", "version: 0", "version"),
        ("referencias,\n  conteos_citas, ", "conteos_citas, ", "referencias"),  # falta uno
        ("fuentes:", "extra: 1\nfuentes:", "extra"),
    ],
)
def test_una_politica_invalida_se_rechaza(viejo: str, nuevo: str, fragmento: str) -> None:
    assert viejo in POLITICA_MINIMA
    contenido = POLITICA_MINIMA.replace(viejo, nuevo).encode()

    with pytest.raises(ErrorPoliticaDatos, match=fragmento):
        cargar_politica(contenido)


def test_una_politica_que_no_es_utf8_o_yaml_se_rechaza() -> None:
    with pytest.raises(ErrorPoliticaDatos, match="UTF-8"):
        cargar_politica("version: 1\n# ñ".encode("latin-1"))
    with pytest.raises(ErrorPoliticaDatos, match="YAML"):
        cargar_politica(b"version: [1\n")


# --------------------------------------------------------------- base


@pytest.mark.parametrize(
    ("datos", "completa"),
    [
        ({"tipo": "institucion", "detalle": "X", "medio": "correo", "fecha": "2026-09-29"}, True),
        ({"tipo": "institucion", "detalle": "X", "medio": None, "fecha": "2026-09-29"}, False),
        ({"tipo": "revista", "detalle": "X", "medio": None, "fecha": "2026-09-29"}, True),
        ({"tipo": "licencia", "detalle": "CC0", "fecha": "2026-09-29"}, True),
        ({"tipo": None, "detalle": "X", "medio": "correo", "fecha": "2026-09-29"}, False),
        ({"tipo": "licencia", "detalle": None, "fecha": "2026-09-29"}, False),
        ({"tipo": "licencia", "detalle": "CC0", "fecha": None}, False),
        ({"tipo": "licencia", "detalle": "   ", "fecha": "2026-09-29"}, False),
        ({}, False),
    ],
)
def test_una_base_esta_completa_con_tipo_detalle_y_fecha(
    datos: dict[str, str | None], completa: bool
) -> None:
    assert Base.model_validate(datos, context={"ahora": HOY}).es_completa is completa


@pytest.mark.parametrize("fecha", ["29/09/2026", "2026-9-29", "20260929", "2026-02-30", "ayer"])
def test_una_fecha_mal_formada_se_rechaza(fecha: str) -> None:
    textos = problemas_de(
        f"fuentes:\n  scopus:\n    campos:\n      titulo:\n        base: {{tipo: licencia, "
        f"detalle: CC0, fecha: '{fecha}'}}\n"
    )

    assert any("fecha" in texto for texto in textos)


def test_la_fecha_futura_usa_el_reloj_inyectado() -> None:
    def con_fecha(fecha: str) -> bytes:
        return configuracion(
            "fuentes:\n  scopus:\n    campos:\n      titulo:\n"
            f"        base: {{tipo: licencia, detalle: CC0, fecha: '{fecha}'}}\n"
        )

    # Hoy (UTC) es 2026-10-12: se admite hasta el día siguiente por las zonas horarias.
    decodificar_configuracion(con_fecha("2026-10-12"), reloj=reloj)
    decodificar_configuracion(con_fecha("2026-10-13"), reloj=reloj)
    with pytest.raises(ErrorConfiguracionPublicacion, match="futura"):
        decodificar_configuracion(con_fecha("2026-10-14"), reloj=reloj)
    # Con otro reloj, el mismo texto deja de ser futuro: no depende de la fecha real.
    posterior = datetime(2026, 10, 20, tzinfo=UTC)
    decodificar_configuracion(con_fecha("2026-10-14"), reloj=lambda: posterior)


def test_una_fecha_de_yaml_sin_comillas_se_acepta() -> None:
    texto = (
        "fuentes:\n  scopus:\n    campos:\n      titulo:\n"
        "        base: {tipo: licencia, detalle: CC0, fecha: 2026-09-29}\n"
    )

    configurada = decodificar_configuracion(configuracion(texto), reloj=reloj)

    assert configurada.fuentes["scopus"].campos["titulo"].base.fecha == "2026-09-29"


def test_el_reloj_debe_tener_zona_horaria() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        decodificar_configuracion(b"fuentes: {}\n", reloj=lambda: datetime(2026, 10, 12))


# ------------------------------------------------------- configuración


def test_una_configuracion_completa_se_carga() -> None:
    texto = f"""
fuentes:
  scopus:
    campos:
      titulo:
        base: {BASE_COMPLETA}
      doi:
        base: {{tipo: institucion, detalle: null, medio: null, fecha: null}}
  fuente-nueva:
    campos:
      anio:
        base: {BASE_COMPLETA}
evidencia_literal:
  resumen:
    estado: no_permitido
respaldo_nube:
  scopus:
    estado: sin_verificar
"""
    configurada = decodificar_configuracion(configuracion(texto), reloj=reloj)

    assert configurada.fuentes["scopus"].campos["titulo"].base.es_completa
    assert not configurada.fuentes["scopus"].campos["doi"].base.es_completa
    assert "anio" in configurada.fuentes["fuente-nueva"].campos
    assert configurada.evidencia_literal["resumen"].estado == "no_permitido"
    assert configurada.respaldo_nube["scopus"].estado == "sin_verificar"


def test_una_configuracion_vacia_de_fuentes_es_valida() -> None:
    configurada = decodificar_configuracion(b"fuentes: {}\n", reloj=reloj)

    assert configurada.fuentes == {}
    assert configurada.evidencia_literal == {}
    assert configurada.respaldo_nube == {}


@pytest.mark.parametrize(
    ("campo", "fragmento"),
    [
        ("resumen", "nunca se publica"),
        ("palabras_clave_autor", "nunca se publica"),
        ("afiliaciones", "nunca se publica"),
        ("inventado", "no es un campo habilitable"),
        ("otros", "no es un campo habilitable"),
        ("hash_completo", "no es un campo habilitable"),
        ("archivo", "no es un campo habilitable"),
    ],
)
def test_un_campo_no_habilitable_se_rechaza_con_su_ubicacion(campo: str, fragmento: str) -> None:
    textos = problemas_de(
        f"fuentes:\n  scopus:\n    campos:\n      {campo}:\n        base: {BASE_COMPLETA}\n"
    )

    assert len(textos) == 1
    assert textos[0].startswith(f"fuentes.scopus.campos.{campo}: ")
    assert fragmento in textos[0]


def test_un_campo_fuera_del_techo_de_una_fuente_conocida_se_rechaza() -> None:
    # La política del paquete no le da `pmid` a ACS.
    textos = problemas_de(
        f"fuentes:\n  acs:\n    campos:\n      pmid:\n        base: {BASE_COMPLETA}\n"
    )

    assert len(textos) == 1
    assert "acs" in textos[0]
    assert "techo" in textos[0]


def test_una_fuente_desconocida_no_tiene_techo_pero_si_nunca_publicables() -> None:
    habilitada = decodificar_configuracion(
        configuracion(
            f"fuentes:\n  base-nueva:\n    campos:\n      pmid:\n        base: {BASE_COMPLETA}\n"
        ),
        reloj=reloj,
    )
    assert "pmid" in habilitada.fuentes["base-nueva"].campos

    textos = problemas_de(
        f"fuentes:\n  base-nueva:\n    campos:\n      resumen:\n        base: {BASE_COMPLETA}\n"
    )
    assert any("nunca se publica" in texto for texto in textos)


def test_varios_problemas_se_informan_a_la_vez() -> None:
    texto = f"""
fuentes:
  scopus:
    campos:
      resumen:
        base: {BASE_COMPLETA}
      inventado:
        base: {BASE_COMPLETA}
      titulo:
        base: {{tipo: licencia, detalle: CC0, fecha: '2999-01-01'}}
  acs:
    campos:
      pmid:
        base: {BASE_COMPLETA}
respaldo_nube:
  scopus:
    estado: permitido
"""
    textos = problemas_de(texto)

    assert len(textos) == 5
    assert any("fuentes.scopus.campos.resumen" in t for t in textos)
    assert any("fuentes.scopus.campos.inventado" in t for t in textos)
    assert any("fuentes.acs.campos.pmid" in t for t in textos)
    assert any("futura" in t for t in textos)
    assert any("permitido" in t and "base completa" in t for t in textos)


# ----------------------------------------- evidencia literal y respaldo


def test_la_evidencia_literal_del_resumen_se_acepta_aunque_el_resumen_no_se_publique() -> None:
    texto = f"""
fuentes: {{}}
evidencia_literal:
  resumen:
    estado: permitido
    base: {BASE_COMPLETA}
"""
    configurada = decodificar_configuracion(configuracion(texto), reloj=reloj)

    assert configurada.evidencia_literal["resumen"].estado == "permitido"


@pytest.mark.parametrize("seccion", ["evidencia_literal", "respaldo_nube"])
@pytest.mark.parametrize(
    "base",
    [
        "",  # sin base
        "base: {tipo: institucion, detalle: X, medio: null, fecha: '2026-09-29'}",  # sin medio
        "base: {tipo: licencia, detalle: null, fecha: '2026-09-29'}",  # sin detalle
    ],
)
def test_permitido_sin_base_completa_se_rechaza(seccion: str, base: str) -> None:
    clave = "resumen" if seccion == "evidencia_literal" else "scopus"
    texto = f"{seccion}:\n  {clave}:\n    estado: permitido\n    {base}\n"

    textos = problemas_de(texto)

    assert any("base completa" in t for t in textos)


def test_una_clave_de_evidencia_literal_no_admitida_se_rechaza() -> None:
    textos = problemas_de("evidencia_literal:\n  titulo:\n    estado: permitido\n")

    assert len(textos) >= 1
    assert any("evidencia_literal" in t for t in textos)


def test_un_estado_desconocido_se_rechaza() -> None:
    textos = problemas_de("respaldo_nube:\n  scopus:\n    estado: quizas\n")

    assert any("respaldo_nube.scopus.estado" in t for t in textos)


def test_una_clave_desconocida_en_la_raiz_se_rechaza() -> None:
    textos = problemas_de("fuentes: {}\notra_seccion: 1\n")

    assert any("otra_seccion" in t for t in textos)


# ----------------------------------------------------------- archivo


def test_un_yaml_mal_formado_informa_la_linea() -> None:
    with pytest.raises(ErrorConfiguracionPublicacion) as informado:
        decodificar_configuracion(b"fuentes:\n  scopus: [1, 2\n", reloj=reloj)

    problema = informado.value.problemas[0]
    assert "YAML" in problema.mensaje
    assert problema.linea is not None


def test_una_clave_repetida_se_rechaza() -> None:
    textos = problemas_de("fuentes: {}\nfuentes: {}\n")

    assert any("repetida" in t for t in textos)


def test_un_archivo_que_no_es_utf8_se_rechaza() -> None:
    with pytest.raises(ErrorConfiguracionPublicacion, match="UTF-8"):
        decodificar_configuracion("fuentes: {} # ñ".encode("latin-1"), reloj=reloj)


@pytest.mark.parametrize("contenido", [b"", b"# solo un comentario\n", b"- a\n- b\n", b"3\n"])
def test_un_archivo_vacio_o_sin_mapa_se_rechaza(contenido: bytes) -> None:
    with pytest.raises(ErrorConfiguracionPublicacion):
        decodificar_configuracion(contenido, reloj=reloj)


def test_un_archivo_inexistente_se_informa(tmp_path: Path) -> None:
    with pytest.raises(ErrorConfiguracionPublicacion, match="no existe"):
        cargar_configuracion(tmp_path / "publicacion_datos.yaml", reloj=reloj)


def test_cargar_y_hash_de_la_configuracion_desde_un_archivo(tmp_path: Path) -> None:
    ruta = tmp_path / "publicacion_datos.yaml"
    ruta.write_bytes(b"fuentes: {}\n")
    primero = hash_configuracion(ruta)

    assert cargar_configuracion(ruta, reloj=reloj).fuentes == {}
    assert primero == hash_bytes(b"fuentes: {}\n")

    ruta.write_bytes(b"fuentes: {}\n# un comentario\n")

    assert hash_configuracion(ruta) != primero
