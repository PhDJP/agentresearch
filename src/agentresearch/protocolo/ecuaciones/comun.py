"""Piezas comunes de los traductores de ecuaciones (ADR-0009).

Un traductor recorre los bloques del protocolo (OR dentro de cada bloque, AND
entre bloques) y decide, término por término, cómo escribirlo en su fuente.
Si la fuente no admite un término tal como está (por ejemplo, su
truncamiento), usa las variantes que escribió el investigador; si no las
hay, la fuente queda bloqueada y sin ecuación. Nada se omite en silencio:
cada decisión que cambia la forma del término deja un aviso.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from agentresearch.protocolo.ecuaciones.limites import LimitesTraducidos
from agentresearch.protocolo.modelo import Bloque, Busqueda
from agentresearch.protocolo.terminos import Termino, analizar_termino

TipoAviso = Literal["bloqueante", "advertencia", "nota"]
"""Un aviso bloqueante deja la fuente sin ecuación; los demás no."""


@dataclass(frozen=True, slots=True)
class Aviso:
    """Algo que el investigador debe saber sobre la ecuación de una fuente."""

    tipo: TipoAviso
    mensaje: str
    bloque: str | None = None
    termino: str | None = None

    def __str__(self) -> str:
        donde = ""
        if self.bloque is not None:
            donde = f" [{self.bloque}" + (f", {self.termino}" if self.termino else "") + "]"
        return f"{self.tipo}{donde}: {self.mensaje}"

    def como_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "mensaje": self.mensaje,
            "bloque": self.bloque,
            "termino": self.termino,
        }


@dataclass(frozen=True, slots=True)
class Documentacion:
    """Página oficial contra la que se verificó la sintaxis de una fuente."""

    titulo: str
    url: str
    verificada: str
    """Fecha de la verificación (AAAA-MM-DD)."""


@dataclass(frozen=True, slots=True)
class Ecuacion:
    """La ecuación de una fuente, o por qué no se pudo generar."""

    fuente: str
    nombre: str
    texto: str | None
    """La ecuación lista para usar, o `None` si la fuente quedó bloqueada."""
    campos: str
    """Qué campos del registro cubre (ADR-0009, punto 6)."""
    manual: bool
    """La fuente se consulta a mano en su interfaz y se exporta (Scopus, Web of Science)."""
    avisos: list[Aviso] = field(default_factory=list)
    limites: LimitesTraducidos = field(default_factory=LimitesTraducidos)
    longitud: int | None = None
    """Longitud que se compara con el máximo de la fuente."""
    maximo: int | None = None
    """Máximo conocido de la fuente, o `None` si no hay uno documentado."""
    descripcion_longitud: str = "caracteres de la ecuación"
    documentacion: tuple[Documentacion, ...] = ()

    @property
    def bloqueada(self) -> bool:
        return self.texto is None

    def como_dict(self) -> dict[str, Any]:
        return {
            "fuente": self.fuente,
            "nombre": self.nombre,
            "ecuacion": self.texto,
            "bloqueada": self.bloqueada,
            "campos": self.campos,
            "manual": self.manual,
            "longitud": self.longitud,
            "maximo": self.maximo,
            "avisos": [aviso.como_dict() for aviso in self.avisos],
            "limites": self.limites.como_dict(),
            "documentacion": [
                {"titulo": d.titulo, "url": d.url, "verificada": d.verificada}
                for d in self.documentacion
            ],
        }


@dataclass(frozen=True, slots=True)
class TerminoDeBloque:
    """Un término analizado, con su bloque y sus variantes (si el investigador las dio)."""

    bloque: Bloque
    termino: Termino
    variantes: tuple[Termino, ...] | None

    @property
    def clave(self) -> str:
        return self.termino.original.strip()


def terminos_de(bloque: Bloque) -> Iterator[TerminoDeBloque]:
    """Los términos de un bloque ya analizados. Supone que no hay P-E04 ni P-E11."""
    variantes = {clave.strip(): lista for clave, lista in bloque.variantes.items()}
    for texto in bloque.terminos:
        termino = analizar_termino(texto)
        lista = variantes.get(texto.strip())
        yield TerminoDeBloque(
            bloque,
            termino,
            tuple(analizar_termino(v) for v in lista) if lista else None,
        )


class Traductor:
    """Base de los traductores: une términos con OR y bloques con AND.

    Cada fuente redefine `escribir`, que devuelve la forma del término en su
    sintaxis, o `None` con el motivo si no lo admite tal como está.
    """

    id: str = ""
    nombre: str = ""
    campos: str = ""
    manual: bool = False
    maximo: int | None = None
    documentacion: tuple[Documentacion, ...] = ()

    def escribir(self, termino: Termino) -> str | None:
        """La forma del término en la fuente, o `None` si no lo admite (se usan variantes)."""
        raise NotImplementedError  # pragma: no cover

    def motivo(self, termino: Termino) -> str:
        """Por qué la fuente no admite el término tal como está."""
        raise NotImplementedError  # pragma: no cover

    def avisos_de_termino(self, termino: Termino) -> list[str]:
        """Advertencias no bloqueantes sobre un término que sí se escribió."""
        avisos = []
        if termino.tiene_tilde:
            avisos.append(
                f"{self.nombre} no documenta cómo trata las letras con tilde o fuera de ASCII; "
                "si quiere recuperar también la forma sin tilde, agréguela como término aparte "
                "(ADR-0009, punto 8)"
            )
        return avisos

    def envolver(self, nucleo: str, varios_bloques: bool) -> str:
        """Pone la unión de bloques en el campo de la fuente.

        Por defecto la pone entre paréntesis si hay más de un bloque, para que
        se pueda combinar con límites sin depender de la precedencia.
        """
        return f"({nucleo})" if varios_bloques else nucleo

    def limites(self, busqueda: Busqueda) -> LimitesTraducidos:
        """Periodo, idiomas y tipos de documento: por defecto, solo como texto."""
        return LimitesTraducidos.como_texto(busqueda)

    def medir(self, texto: str) -> int:
        return len(texto)

    def traducir(self, busqueda: Busqueda) -> Ecuacion:
        avisos: list[Aviso] = []
        bloques = [self._bloque(bloque, avisos) for bloque in busqueda.bloques]
        return self._ecuacion(busqueda, bloques, avisos)

    # --- Piezas para las subclases ----------------------------------------------------

    def _bloque(self, bloque: Bloque, avisos: list[Aviso]) -> str | None:
        """El bloque entre paréntesis con sus términos unidos por OR, o `None` si se bloquea."""
        partes: list[str] = []
        bloqueado = False
        for item in terminos_de(bloque):
            formas = self._formas(item, avisos)
            if formas is None:
                bloqueado = True
            else:
                partes += formas
        if bloqueado or not partes:
            return None
        return "(" + " OR ".join(partes) + ")"

    def _formas(self, item: TerminoDeBloque, avisos: list[Aviso]) -> list[str] | None:
        """Las formas de un término: él mismo, o sus variantes si la fuente no lo admite."""
        bloque_id = item.bloque.id
        forma = self.escribir(item.termino)
        if forma is not None:
            avisos.extend(
                Aviso("advertencia", mensaje, bloque_id, item.clave)
                for mensaje in self.avisos_de_termino(item.termino)
            )
            return [forma]
        motivo = self.motivo(item.termino)
        if item.variantes is None:
            avisos.append(
                Aviso(
                    "bloqueante",
                    f"{motivo}. Agregue en busqueda.bloques[{bloque_id}].variantes las "
                    f"variantes de {item.clave!r} que {self.nombre} debe buscar en su lugar",
                    bloque_id,
                    item.clave,
                )
            )
            return None
        formas = []
        for variante in item.variantes:
            forma_variante = self.escribir(variante)
            if forma_variante is None:  # pragma: no cover - una variante sin * siempre se admite
                raise AssertionError(f"{self.nombre} no admite la variante {variante}")
            formas.append(forma_variante)
            avisos.extend(
                Aviso("advertencia", mensaje, bloque_id, str(variante))
                for mensaje in self.avisos_de_termino(variante)
            )
        avisos.append(
            Aviso(
                "nota",
                f"{motivo}; se usan sus variantes: " + ", ".join(str(v) for v in item.variantes),
                bloque_id,
                item.clave,
            )
        )
        return formas

    def _ecuacion(
        self, busqueda: Busqueda, bloques: list[str | None], avisos: list[Aviso]
    ) -> Ecuacion:
        limites = self.limites(busqueda)
        avisos = avisos + [Aviso("advertencia", mensaje) for mensaje in limites.avisos]
        avisos += [Aviso("nota", mensaje) for mensaje in limites.notas]
        if any(bloque is None for bloque in bloques):
            return self._armar(None, avisos, limites)
        nucleo = " AND ".join(bloque for bloque in bloques if bloque is not None)
        texto = self.envolver(nucleo, len(bloques) > 1)
        if limites.sufijo:
            texto += limites.sufijo
        return self._armar(texto, avisos, limites)

    def _armar(
        self, texto: str | None, avisos: list[Aviso], limites: LimitesTraducidos
    ) -> Ecuacion:
        longitud = self.medir(texto) if texto is not None else None
        if longitud is not None and self.maximo is not None and longitud > self.maximo:
            avisos = avisos + [
                Aviso(
                    "advertencia",
                    f"la ecuación mide {longitud} {self._descripcion_longitud()} y supera el "
                    f"máximo conocido de {self.nombre} ({self.maximo}); divida los bloques en "
                    "varias consultas y una los resultados",
                )
            ]
        return Ecuacion(
            fuente=self.id,
            nombre=self.nombre,
            texto=texto,
            campos=self.campos,
            manual=self.manual,
            avisos=avisos,
            limites=limites,
            longitud=longitud,
            maximo=self.maximo,
            descripcion_longitud=self._descripcion_longitud(),
            documentacion=self.documentacion,
        )

    def _descripcion_longitud(self) -> str:
        return "caracteres"


def raiz_corta(termino: Termino, minimo: int) -> bool:
    """Indica si alguna palabra truncada tiene menos de `minimo` letras antes del `*`."""
    return any(p.truncada and len(p.raiz) < minimo for p in termino.palabras)
