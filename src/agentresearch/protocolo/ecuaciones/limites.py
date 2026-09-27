"""Límites de la búsqueda: periodo, idiomas y tipos de documento (ADR-0009, punto 10).

El protocolo guarda idiomas y tipos como texto libre. El paquete reconoce los
códigos ISO 639-1 de `idiomas.valores` y un vocabulario controlado de tipos
(las tablas del ADR-0009, punto 10). No hay sinónimos: un valor fuera del
vocabulario genera un aviso y la instrucción de filtrar en la interfaz, nunca
una conversión en silencio. Un límite se traduce a la sintaxis de la fuente
solo si se reconocen todos sus valores: traducir una parte y dejar otra como
instrucción de la interfaz excluiría, por el AND, los valores no traducidos.
"""

from dataclasses import dataclass
from typing import Any

from agentresearch.protocolo.modelo import Busqueda

IDIOMAS: dict[str, tuple[str, str]] = {
    "de": ("alemán", "German"),
    "en": ("inglés", "English"),
    "es": ("español", "Spanish"),
    "fr": ("francés", "French"),
    "it": ("italiano", "Italian"),
    "ja": ("japonés", "Japanese"),
    "ko": ("coreano", "Korean"),
    "nl": ("neerlandés", "Dutch"),
    "pl": ("polaco", "Polish"),
    "pt": ("portugués", "Portuguese"),
    "ru": ("ruso", "Russian"),
    "tr": ("turco", "Turkish"),
    "zh": ("chino", "Chinese"),
}
"""Código ISO 639-1 → (nombre en español, nombre en inglés, como lo usan las bases)."""


@dataclass(frozen=True, slots=True)
class TipoDocumento:
    """Un tipo del vocabulario controlado y su equivalente en cada fuente manual."""

    nombre: str
    """Nombre legible en español."""
    scopus: str
    """Código de `DOCTYPE` en Scopus (Scopus Search Tips, verificado 2026-09-26)."""
    wos: str
    """Nombre del tipo en el filtro Document Types de Web of Science (verificado 2026-09-26)."""


TIPOS_DOCUMENTO: dict[str, TipoDocumento] = {
    "articulo": TipoDocumento("artículo", "ar", "Article"),
    "revision": TipoDocumento("revisión", "re", "Review"),
    "conferencia": TipoDocumento("artículo de conferencia", "cp", "Proceedings Paper"),
    "capitulo": TipoDocumento("capítulo de libro", "ch", "Book Chapter"),
    "libro": TipoDocumento("libro", "bk", "Book"),
    "editorial": TipoDocumento("editorial", "ed", "Editorial Material"),
    "carta": TipoDocumento("carta", "le", "Letter"),
    "nota": TipoDocumento("nota", "no", "Note"),
}
"""Vocabulario controlado de tipos de documento: valor del protocolo → equivalentes."""


@dataclass(frozen=True, slots=True)
class LimitesTraducidos:
    """Los límites de una fuente: lo que entra en la ecuación y lo que va a la interfaz."""

    sufijo: str = ""
    """Texto que se agrega a la ecuación (p. ej. ` AND PUBYEAR > 1999`)."""
    descripcion: tuple[str, ...] = ()
    """Los límites del protocolo, en texto."""
    instrucciones: tuple[str, ...] = ()
    """Filtros que el investigador aplica en la interfaz de la fuente."""
    avisos: tuple[str, ...] = ()
    notas: tuple[str, ...] = ()
    """Información que no exige nada, como una recomendación de la documentación."""
    pendientes_del_conector: bool = False
    """Los límites se aplicarán con el conector de la fuente (hito 3)."""

    @classmethod
    def como_texto(
        cls, busqueda: Busqueda, pendientes_del_conector: bool = False
    ) -> "LimitesTraducidos":
        return cls(descripcion=describir(busqueda), pendientes_del_conector=pendientes_del_conector)

    def como_dict(self) -> dict[str, Any]:
        return {
            "en_la_ecuacion": self.sufijo.removeprefix(" AND ") if self.sufijo else None,
            "descripcion": list(self.descripcion),
            "instrucciones": list(self.instrucciones),
            "pendientes_del_conector": self.pendientes_del_conector,
        }


def describir(busqueda: Busqueda) -> tuple[str, ...]:
    """Los límites del protocolo en texto legible."""
    return (
        f"Periodo: {_texto_periodo(busqueda.periodo.desde, busqueda.periodo.hasta)}",
        "Idiomas: "
        + (", ".join(_idioma_legible(v) for v in busqueda.idiomas.valores) or "sin restricción"),
        "Tipos de documento: "
        + (", ".join(_tipo_legible(v) for v in busqueda.tipos_documento) or "sin restricción"),
    )


def _texto_periodo(desde: int | None, hasta: int | None) -> str:
    if desde is not None and hasta is not None:
        return f"{desde} a {hasta}, ambos inclusive"
    if desde is not None:
        return f"desde {desde}, inclusive"
    if hasta is not None:
        return f"hasta {hasta}, inclusive"
    return "sin límite"


def _idioma_legible(valor: str) -> str:
    conocido = IDIOMAS.get(valor.strip().lower())
    return f"{valor} ({conocido[0]})" if conocido else f"{valor} (no reconocido)"


def _tipo_legible(valor: str) -> str:
    conocido = TIPOS_DOCUMENTO.get(valor.strip().lower())
    return conocido.nombre if conocido else f"{valor} (no reconocido)"


def _idioma_para_interfaz(valor: str) -> str:
    conocido = IDIOMAS.get(valor.strip().lower())
    return conocido[0] if conocido else valor


def _tipo_para_interfaz(valor: str) -> str:
    conocido = TIPOS_DOCUMENTO.get(valor.strip().lower())
    return conocido.nombre if conocido else valor


def _tipo_para_wos(valor: str) -> str:
    conocido = TIPOS_DOCUMENTO.get(valor.strip().lower())
    return conocido.wos if conocido else valor


def _desconocidos(valores: list[str], vocabulario: dict[str, Any]) -> list[str]:
    return [v for v in valores if v.strip().lower() not in vocabulario]


def _aviso_idiomas(fuente: str, desconocidos: list[str]) -> str:
    return (
        f"idiomas no reconocidos ({', '.join(repr(v) for v in desconocidos)}): el filtro de "
        f"idioma de {fuente} se da como instrucción de la interfaz. Use códigos ISO 639-1 (p. ej. "
        "es, en) para que se traduzca"
    )


def _aviso_tipos(fuente: str, desconocidos: list[str]) -> str:
    return (
        f"tipos de documento no reconocidos ({', '.join(repr(v) for v in desconocidos)}): el "
        f"filtro de tipo de {fuente} se da como instrucción de la interfaz, sin convertirlos. "
        "Tipos del vocabulario controlado (ADR-0009, punto 10): " + ", ".join(TIPOS_DOCUMENTO)
    )


def limites_scopus(busqueda: Busqueda) -> LimitesTraducidos:
    """Periodo con PUBYEAR, idiomas con LANGUAGE y tipos con DOCTYPE (verificado 2026-09-26)."""
    partes: list[str] = []
    instrucciones: list[str] = []
    avisos: list[str] = []
    periodo = busqueda.periodo
    if periodo.desde is not None:
        partes.append(f"PUBYEAR > {periodo.desde - 1}")
    if periodo.hasta is not None:
        partes.append(f"PUBYEAR < {periodo.hasta + 1}")

    idiomas = busqueda.idiomas.valores
    desconocidos = _desconocidos(idiomas, IDIOMAS)
    if idiomas and not desconocidos:
        nombres = [IDIOMAS[v.strip().lower()][1].lower() for v in idiomas]
        partes.append(_unir_o([f"LANGUAGE({nombre})" for nombre in nombres]))
    elif idiomas:
        avisos.append(_aviso_idiomas("Scopus", desconocidos))
        instrucciones.append(
            "Idioma: en los resultados, limite por idioma (Language) a "
            + ", ".join(_idioma_para_interfaz(v) for v in idiomas)
        )

    tipos = busqueda.tipos_documento
    desconocidos = _desconocidos(tipos, TIPOS_DOCUMENTO)
    if tipos and not desconocidos:
        codigos = [TIPOS_DOCUMENTO[v.strip().lower()].scopus for v in tipos]
        partes.append(_unir_o([f"DOCTYPE({codigo})" for codigo in codigos]))
    elif tipos:
        avisos.append(_aviso_tipos("Scopus", desconocidos))
        instrucciones.append(
            "Tipo de documento: en los resultados, limite por tipo (Document type) a "
            + ", ".join(_tipo_para_interfaz(v) for v in tipos)
        )
    return LimitesTraducidos(
        sufijo="".join(f" AND {parte}" for parte in partes),
        descripcion=describir(busqueda),
        instrucciones=tuple(instrucciones),
        avisos=tuple(avisos),
    )


MAXIMO_ANIOS_PY_RECOMENDADO = 5
"""Advanced Search Field Tags (Web of Science): "restrict your search to five years or less"."""


def limites_wos(busqueda: Busqueda) -> LimitesTraducidos:
    """Periodo con PY=(desde-hasta); idiomas y tipos, en la interfaz (verificado 2026-09-26).

    La ayuda de Web of Science documenta `PY=(2008-2010)`, pero no una forma
    abierta ni etiquetas de idioma o tipo para la búsqueda avanzada.
    """
    sufijo = ""
    instrucciones: list[str] = []
    avisos: list[str] = []
    notas: list[str] = []
    periodo = busqueda.periodo
    if periodo.desde is not None and periodo.hasta is not None:
        sufijo = f" AND PY=({periodo.desde}-{periodo.hasta})"
        if periodo.hasta - periodo.desde + 1 > MAXIMO_ANIOS_PY_RECOMENDADO:
            notas.append(
                "la ayuda de Web of Science recomienda intervalos de "
                f"{MAXIMO_ANIOS_PY_RECOMENDADO} años o menos en PY=, porque los más largos "
                "hacen lenta la búsqueda; si ocurre, quite PY= de la ecuación y ajuste los años "
                "de publicación en la interfaz"
            )
    elif periodo.desde is not None or periodo.hasta is not None:
        instrucciones.append(
            "Periodo: ajuste los años de publicación en la interfaz: "
            + _texto_periodo(periodo.desde, periodo.hasta)
            + " (la ayuda solo documenta PY= con un intervalo cerrado)"
        )
    idiomas = busqueda.idiomas.valores
    if idiomas:
        desconocidos = _desconocidos(idiomas, IDIOMAS)
        if desconocidos:
            avisos.append(
                f"idiomas no reconocidos ({', '.join(repr(v) for v in desconocidos)}): van a la "
                "instrucción de la interfaz tal como están escritos. Use códigos ISO 639-1 (p. "
                "ej. es, en) para que salgan con el nombre en inglés que usa la base"
            )
        nombres = [
            IDIOMAS[v.strip().lower()][1] if v.strip().lower() in IDIOMAS else v for v in idiomas
        ]
        instrucciones.append(
            "Idioma: en los resultados, filtre por idioma (Languages) a " + ", ".join(nombres)
        )
    tipos = busqueda.tipos_documento
    if tipos:
        desconocidos = _desconocidos(tipos, TIPOS_DOCUMENTO)
        if desconocidos:
            avisos.append(
                "tipos de documento no reconocidos "
                f"({', '.join(repr(v) for v in desconocidos)}): van a la instrucción de la "
                "interfaz tal como están escritos, sin convertirlos. Tipos del vocabulario "
                "controlado (ADR-0009, punto 10): " + ", ".join(TIPOS_DOCUMENTO)
            )
        instrucciones.append(
            "Tipo de documento: en los resultados, filtre por tipo (Document Types) a "
            + ", ".join(_tipo_para_wos(v) for v in tipos)
            + " (un registro puede tener dos tipos, p. ej. Article y Proceedings Paper)"
        )
    return LimitesTraducidos(
        sufijo=sufijo,
        descripcion=describir(busqueda),
        instrucciones=tuple(instrucciones),
        avisos=tuple(avisos),
        notas=tuple(notas),
    )


def _unir_o(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else "(" + " OR ".join(partes) + ")"
