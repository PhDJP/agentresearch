# ADR-0009: Ecuaciones de búsqueda por fuente

- Estado: Propuesta
- Fecha: 2026-09-26
- Participantes: investigador doctoral y Claude Code

## Contexto

El sub-hito 1d de la
[especificación del hito 1](../especificaciones/hito_1_protocolo_y_trazabilidad.md)
traduce los bloques de búsqueda del protocolo (OR dentro de cada bloque, AND
entre bloques) a una ecuación por fuente: OpenAlex, PubMed, Scopus, Web of
Science y una versión genérica. PRISMA-ScR (ítem 8) pide la estrategia de
búsqueda completa de al menos una base, de forma que se pueda repetir, y las
reglas metodológicas (§3) piden ecuaciones por fuente con sus límites.

Cada base interpreta de forma distinta las frases, el truncamiento, los
guiones y los límites. Por eso la especificación exige:

- verificar la sintaxis contra la documentación oficial al implementar, y no
  contra lo que el modelo recuerda;
- que un traductor que no puede expresar algo lo informe y aplique una
  alternativa explícita, en vez de omitirlo en silencio;
- advertir cuando una ecuación supera el máximo conocido de la fuente.

Las opciones de cada decisión se presentaron al investigador, que eligió
(2026-09-26). Las no elegidas están en "Alternativas consideradas".

## Decisión

### Qué es un término (regla P-E11)

1. **Gramática de un término de búsqueda.** Cada elemento de
   `busqueda.bloques[].terminos` tiene una de estas formas:
   - **palabra:** letras (con o sin tilde), dígitos, y guiones o apóstrofos
     internos (`secado`, `by-product`, `post-extraction`);
   - **palabra truncada:** una palabra seguida de `*` (`dehydrat*`,
     `by-product*`);
   - **frase:** una o más palabras entre comillas dobles, cada una
     opcionalmente truncada (`"Zarambus fictus"`, `"hemp seed*"`). Una sola
     palabra entre comillas (`"CBD"`) pide la forma exacta: en Web of
     Science desactiva la lematización, y en PubMed el mapeo automático de
     términos.
2. **Error P-E11, "término de búsqueda no traducible".** Salta con:
   - varias palabras sin comillas, porque cada base las interpretaría
     distinto (AND implícito en Web of Science y Scopus, frase en PubMed);
   - operadores (`AND`, `OR`, `NOT`, `NEAR`, `SAME`, `W/n`, `PRE/n`),
     paréntesis o etiquetas de campo (`[tiab]`, `TS=`, `TITLE-ABS-KEY(`);
   - comodines distintos de `*` (`?`, `$`, `#`), `*` al inicio o en medio de
     una palabra, o `*` después de un guion;
   - comillas vacías o sin cerrar;
   - guiones o apóstrofos al inicio o al final de una palabra.

   El mensaje nombra el bloque y el término. Referencia: PRISMA-ScR, ítem 8;
   Petersen et al. (2015), §5.1.2. Como los demás errores, impide aprobar.
3. **Variantes.** Cada bloque admite un campo opcional nuevo,
   `variantes: {término truncado: [variantes]}`, que escribe el
   investigador. Es un campo opcional, así que no cambia la versión del
   esquema (ADR-0006, punto 16). P-E11 también salta si una clave no es un
   término truncado del mismo bloque, o si una variante no es una palabra o
   una frase válidas sin `*`.

   Un traductor usa las variantes solo donde el truncamiento de ese término
   no se admite (punto 7). Si faltan, esa fuente sale con un **aviso
   bloqueante** y sin ecuación. El paquete nunca inventa variantes (regla 6
   de CLAUDE.md).

### Fuentes que se traducen

4. **Fuentes.** Se traducen las fuentes de `fuentes` cuyo `id` es
   `openalex`, `pubmed`, `scopus` o `wos`, más la genérica siempre. Una
   fuente declarada sin traductor se lista en `ecuaciones.md` con la
   indicación de usar la ecuación genérica.
5. **Estructura común.** Todas las ecuaciones ponen entre paréntesis cada
   bloque y la unión de bloques, aunque la precedencia de la fuente no lo
   exija. Elsevier anuncia que en 2026 cambiará la precedencia de los
   operadores de Scopus, y los paréntesis hacen la ecuación independiente
   de ese cambio.

### Sintaxis verificada (2026-09-26)

6. **Campos que cubre cada ecuación.** La diferencia de alcance entre fuentes
   es una amenaza a la validez que el reporte debe declarar (punto 16).

   | Fuente | Campo | Qué cubre | Fuente de la verificación |
   |---|---|---|---|
   | OpenAlex | `title_and_abstract.search` o `search` (punto 9) | título y resumen; `search` suma el texto completo | [Búsqueda](https://help.openalex.org/api/searching/), [guía](https://help.openalex.org/guides/searching) (act. 2026-09-19) |
   | PubMed | `[tiab]` | título y resumen | [Guía de usuario](https://pubmed.ncbi.nlm.nih.gov/help/) (act. 2026-09-24) |
   | Scopus | `TITLE-ABS-KEY(…)` | título, resumen y palabras clave; `KEY` reúne palabras clave de autor, términos indexados, nombres comerciales y nombres químicos | [Consejos de búsqueda de la API](https://dev.elsevier.com/sc_search_tips.html), [búsqueda avanzada](https://www.elsevier.support/scopus/answer/how-can-i-best-use-the-advanced-search) (act. 2026-08-24) |
   | Web of Science | `TS=(…)` | título, resumen, palabras clave de autor y Keywords Plus | [Campos de búsqueda](https://webofscience.zendesk.com/hc/en-us/articles/26916258216209-Web-of-Science-Core-Collection-Search-Fields), [reglas](https://webofscience.zendesk.com/hc/en-us/articles/25350084904721-Search-Rules), [operadores](https://webofscience.zendesk.com/hc/en-us/articles/20016122409105-Search-Operators) (act. 2025-10-17) |
   | Genérica | ninguno | lo que la base busque por defecto | no aplica |

   Keywords Plus (Web of Science) y los términos indexados (Scopus) los
   asigna la base a partir de otros datos. Un estudio puede aparecer en una
   base por un término que no está en su título ni en su resumen.
7. **Truncamiento, frases y guiones.**

   | Fuente | Frase | Truncamiento | Guion |
   |---|---|---|---|
   | OpenAlex | `"…"` | solo con `search.exact` (sin lematización), al menos 3 letras antes; no al inicio | no documentado; pendiente de la verificación del punto 9 |
   | PubMed | `"…"[tiab]` | al menos 4 letras antes del primer `*`; admitido en frases y tras guion (`breast-feed*`) | busca la frase; si no está en el índice de frases, no devuelve nada |
   | Scopus | `"…"` (aproximada: ignora la puntuación e incluye plurales) | al menos 3 letras; admitido en frases aproximadas; se descarta si va justo después de un guion | se busca como frase aproximada |
   | Web of Science | `"…"` (exacta: desactiva la lematización) | al menos 3 letras antes; en frases, **no documentado** | `TS=hydro-power` recupera `hydro-power` y `hydro power` |
   | Genérica | `"…"` | se deja el `*`, con una nota | se deja el guion |

   - El largo mínimo se cuenta sobre la parte de la palabra que sigue al
     último guion, que es la unidad que indexan Scopus y Web of Science.
   - Si la raíz es más corta que el mínimo de la fuente, se usan las
     variantes del término.
   - **Lo no documentado se trata como no admitido.** Por eso una frase con
     truncamiento en Web of Science usa las variantes.
   - Web of Science no lleva comillas en una palabra suelta, porque las
     comillas desactivan la lematización (`"mouse"` no recupera `mice`).
8. **Tildes.** Ninguna de las cuatro fuentes documenta cómo trata las
   letras con tilde en los campos de tema. Web of Science documenta que no
   se buscan en los nombres de autor. El término se traduce tal como está
   escrito, con un aviso no bloqueante que sugiere agregar la forma sin
   tilde como término aparte si el investigador quiere recuperarla. El
   paquete no la agrega por su cuenta.
9. **OpenAlex.**
   - **Alcance.** Se usa `title_and_abstract.search` si una consulta real
     a la API confirma que existe y que admite booleanos, frases y comodines
     (y su variante `.search.exact`). Si no, se usa `search`, que incluye el
     texto completo, y la diferencia se declara como amenaza a la validez.
     *Pendiente:* la consulta se hace con la clave de `.env`, que el
     investigador está creando. Este punto se completa con el resultado
     antes de aceptar el ADR.
   - **Truncamiento.** `search` lematiza pero no admite comodines;
     `search.exact` admite comodines pero no lematiza, y solo se usa uno por
     solicitud. Se elige así:
     - sin términos truncados: búsqueda lematizada;
     - con términos truncados y **todos** con variantes: búsqueda
       lematizada con las variantes en lugar de los truncamientos. **Pro:**
       conserva la lematización (plurales y otras formas) en todos los
       términos, y la lematización también expande las variantes. **Contra:**
       recupera solo las variantes que escribió el investigador, no todas
       las palabras con esa raíz;
     - con términos truncados y alguno sin variantes: `search.exact` con los
       comodines y un aviso de que se pierde la lematización en toda la
       ecuación. Si alguna raíz tiene menos de 3 letras y no tiene
       variantes, OpenAlex queda bloqueada.
   - **Longitud.** La URL completa admite unos 4 KB. Se avisa cuando la
     ecuación codificada para URL supera ese límite.

### Límites de la búsqueda

10. **Periodo, idiomas y tipos de documento.**
    - **OpenAlex, PubMed y la genérica:** se listan como texto en
      `ecuaciones.md`. Se traducirán en el hito 3, con los conectores.
    - **Scopus y Web of Science,** que se usan por exportación manual, se
      traducen cuando la sintaxis está verificada. Si no, `ecuaciones.md` da
      la instrucción de filtro de la interfaz:

      | Límite | Scopus | Web of Science |
      |---|---|---|
      | Periodo | `PUBYEAR > desde-1` y `PUBYEAR < hasta+1` (`>` y `<` son estrictos: "after", "before") | `PY=(desde-hasta)` si están los dos años; si falta uno, instrucción de la interfaz (periodo) |
      | Idiomas | `LANGUAGE(nombre en inglés)` para los códigos ISO 639-1 conocidos | instrucción de la interfaz: no hay etiqueta de idioma documentada |
      | Tipos de documento | `DOCTYPE(código)` para los tipos conocidos | instrucción de la interfaz: no hay etiqueta de tipo documentada |

    - El protocolo guarda idiomas y tipos como texto libre. El paquete
      reconoce los códigos ISO 639-1 en `idiomas.valores` y un vocabulario
      de tipos en español (`articulo`, `revision`, `conferencia`,
      `capitulo`, `libro`, `editorial`, `carta`, `nota`). Un valor que no
      reconoce se traduce como instrucción de la interfaz, con un aviso.

### Salida

11. **Comando `agentresearch protocolo ecuaciones [ruta] [--escribir] [--json]`.**
    - Sin `--escribir` muestra las ecuaciones; con `--escribir` además
      guarda `protocolo/ecuaciones.md`. No exige terminal.
    - Se niega si hay P-E00, P-E10 o P-E11. Con `--escribir` también se
      niega con P-E09, porque unas ecuaciones de un protocolo con cambios
      sin registrar no corresponden a ninguna versión. Sin `--escribir`,
      avisa del P-E09.
    - Si alguna fuente queda bloqueada, escribe igual el archivo, con la
      sección de esa fuente explicando qué falta, y sale con código 1. En
      `--json`, `"escrito": true` y `"fuentes_bloqueadas": [...]` lo
      distinguen de un rechazo, que tiene `"exito": false` y no escribe.
    - No registra un evento: `ecuaciones.md` se deriva del protocolo de
      forma determinista, y lo versiona Git.
12. **`protocolo/ecuaciones.md`** es determinista: no lleva marca de tiempo,
    y el mismo protocolo con la misma versión del agente produce los mismos
    bytes (UTF-8, LF). Contiene:
    - una cabecera con la ruta, la versión, el estado y el hash del
      protocolo, y la versión del agente. La línea
      `- Hash del protocolo: sha256:<hex>` es la que se compara en el
      punto 14;
    - por cada fuente: la ecuación en un bloque de código, los campos que
      cubre, su longitud frente al máximo conocido, y los avisos;
    - los límites (punto 10);
    - las fuentes declaradas sin traductor.
13. **Pasos para las fuentes manuales.** Junto a las ecuaciones de Scopus y
    Web of Science, `ecuaciones.md` indica al investigador:
    - dónde pegarla: búsqueda avanzada (Scopus) o la búsqueda avanzada con
      etiquetas de campo (Web of Science);
    - qué filtros aplicar en la interfaz (punto 10);
    - en qué formato exportar, según el ADR-0003: CSV en Scopus y el formato
      de etiquetas (.txt) en Web of Science, con todos los campos
      disponibles (resumen y palabras clave incluidos);
    - qué anotar al ejecutarla: la fecha y hora, y el número de resultados
      que mostró la interfaz. El hito 2 lo pedirá al importar la
      exportación (PRISMA-ScR, ítem 7).

### Ecuaciones desactualizadas

14. **Nota de estado, no advertencia.** `validar` e `historial` comparan el
    hash de la cabecera de `ecuaciones.md` con el hash actual del protocolo.
    Si no coinciden, muestran una nota ("ecuaciones desactualizadas") y su
    salida `--json` lleva `"ecuaciones_desactualizadas": true`. No bloquea
    ni exige justificación. Si `ecuaciones.md` no existe, no hay nota.
15. **Flujo.** Aprobar o enmendar cambia el estado o la versión, y con ello
    el hash, así que las ecuaciones quedan desactualizadas justo después.
    El investigador (o `/protocolo` en el 1e) las regenera con
    `protocolo ecuaciones --escribir` después de aprobar o enmendar.

### Amenazas a la validez

16. El reporte (hito 10) debe declarar:
    - que los campos cubiertos difieren entre fuentes (punto 6);
    - que las frases de Web of Science son exactas y no lematizadas,
      mientras que las de Scopus son aproximadas e incluyen plurales;
    - si OpenAlex buscó en el texto completo o sin lematización (punto 9);
    - los términos con tilde cuyo tratamiento no está documentado (punto 8).

## Alternativas consideradas

- **Varias palabras sin comillas:**
  - tratarlas como frase y avisarlo: es más cómodo, pero el paquete
    interpretaría por su cuenta la intención del investigador;
  - dejarlas como las interprete cada base: el mismo término significaría
    cosas distintas en cada fuente.
- **Truncamiento no admitido:**
  - que el paquete no genere ecuación para esa fuente y pida escribir las
    variantes en los términos: obliga a duplicar términos en el bloque,
    también para las fuentes que sí admiten el truncamiento;
  - quitar el `*` y avisar: siempre hay ecuación, pero cambia el alcance de
    la búsqueda sin que el investigador lo decida;
  - generar variantes automáticamente: no hay un vocabulario fiable, y
    violaría la regla 6.
- **OpenAlex con truncamiento:** usar siempre `search.exact`: es más simple,
  pero pierde la lematización aunque el investigador ya haya escrito todas
  las variantes.
- **Tildes:** agregar de forma automática la forma sin tilde: es
  determinista, pero cambia los términos del investigador sin que lo
  decida, y ninguna fuente documenta que haga falta.
- **Límites:**
  - traducirlos para todas las fuentes ya: OpenAlex y PubMed se consultarán
    con los conectores del hito 3, que aplican los límites como parámetros;
  - no traducirlos para ninguna: Scopus y Web of Science se usan por
    exportación manual, y la ecuación completa es lo que el investigador
    pega y lo que el reporte cita.
- **Fuentes:** traducir siempre las cinco, sin mirar `fuentes`: genera
  ecuaciones que el protocolo no declara.
- **Ecuaciones desactualizadas como advertencia P-A10:** con el ADR-0008
  (punto 10), toda enmienda la volvería "nueva" y exigiría justificarla, y
  `--escribir` no puede regenerar antes de enmendar porque P-E09 lo impide.
- **Registrar un evento al escribir `ecuaciones.md`:** duplica lo que ya
  guardan el protocolo versionado y Git, sin aportar evidencia nueva.

## Consecuencias

- El investigador escribe variantes solo para los términos truncados que
  alguna fuente declarada no admite, y el aviso bloqueante le dice cuáles.
- P-E11 puede volver inválido un protocolo que hoy pasa `validar`. No hay
  todavía protocolos aprobados, así que no hace falta una migración.
- `ecuaciones.md` hay que regenerarlo después de aprobar o enmendar. La
  nota de estado lo recuerda, y `/protocolo` (1e) lo automatizará.
- La sintaxis de cada fuente puede cambiar. Cada traductor guarda la URL y
  la fecha de verificación, y los archivos de referencia de las pruebas
  fijan la salida esperada, así que un cambio de sintaxis se corrige en un
  solo lugar y se ve en el diff de las pruebas.
- Quedan fuera del 1d: el traductor de Semantic Scholar (hoja de ruta,
  hito 3), la exclusión con `NOT` y la búsqueda por proximidad.
