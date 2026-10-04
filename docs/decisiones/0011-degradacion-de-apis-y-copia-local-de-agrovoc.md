# ADR-0011: Degradación ante fuentes de API inestables y copia local de AGROVOC

- Estado: Propuesta
- Fecha: 2026-10-04
- Participantes: investigador doctoral, asesor (Claude en Cowork) y Claude Code

## Contexto

Antes del hito 3 se verificaron las condiciones de las APIs y el investigador
las probó en su equipo (ADR-0003, nota posterior del 2026-10-04). La prueba
mostró que una fuente puede no estar disponible en el equipo de un
investigador por motivos ajenos al agente:

- **Semantic Scholar sin clave:** tiempo de espera agotado y luego 429 en dos
  intentos, porque el grupo compartido de usuarios sin clave estaba saturado.
- **AGROVOC:** el REST respondió 500 en tres intentos y SPARQL respondió 503,
  mientras el sitio web respondía 200. Los servicios de datos de la FAO
  estaban caídos.

Un agente de revisión sistemática no puede resolver esas situaciones
reintentando sin límite, ni sustituyendo una fuente por otra sin avisar. Lo
primero consume cuota y oculta el fallo. Lo segundo cambia la estrategia de
búsqueda del protocolo (regla 5 de CLAUDE.md) y deja un reporte que describe
una búsqueda que no ocurrió (PRISMA-ScR, ítems 7 y 8). Además, el uso de
AGROVOC (proponer sinónimos para la ecuación PCC) debe ser reproducible, y un
servicio en vivo sin número de versión no lo es.

Las opciones se presentaron al investigador con pros, contras y una
recomendación. El investigador y el asesor aprobaron el 2026-10-04 la
recomendación de la degradación (decisión D1) y la copia local de AGROVOC
(decisión D2). Las no elegidas están en «Alternativas consideradas».

## Decisión

### Política de degradación de una API

**Definiciones.**

- **B, reintento con espera.** Volver a hacer la misma consulta, con una espera
  creciente y un número máximo de intentos, y registrar cada intento.
- **A, paso a importación manual.** El investigador exporta, **de la misma
  fuente** y desde su propia interfaz web, los resultados de la misma ecuación
  en un formato que el agente lee (RIS u otro del ADR-0010) y los registra con
  `importar registrar`. Es la misma fuente con otra vía de acceso. No es una
  sustitución.

**La política.**

1. **Orden: primero B y, si persiste, A.** La degradación nunca avanza sola:
   el agente propone cada paso y el investigador lo decide (regla 1).
2. **Qué se reintenta.** Solo los fallos transitorios: tiempo de espera
   agotado, errores 5xx y 429. Un 429 respeta el encabezado `Retry-After` si
   la respuesta lo trae. Los fallos permanentes (401, 403, otros 4xx y una
   respuesta que no cumple el esquema esperado) no se reintentan: se
   registran y se informa al investigador la causa probable (p. ej. clave
   ausente o inválida).
3. **Reintentos acotados.** El número de intentos y las esperas tienen un
   máximo, y los valores por defecto se fijan en el sub-hito 3a y se
   documentan allí. Los reintentos **nunca superan los límites de la fuente**:
   cuentan para el control de tasa y para el presupuesto diario (p. ej. las 500
   consultas diarias de Springer), y el agente no los usa para rebasarlos.
4. **Registro del fallo en la trazabilidad.** Cuando se agotan los reintentos,
   el paquete escribe en `protocolo/eventos.jsonl` el evento `consulta_fallida`
   (nombre provisional) con: la fuente, la consulta exacta y su hash, la fecha
   y hora UTC, la clasificación del fallo (transitorio o permanente) y la lista
   de intentos (número, hora UTC, código HTTP o «tiempo agotado», espera).
   **Nada de eso incluye claves ni el correo del investigador:** el saneo del
   hito 3 se aplica antes de escribir (hoja de ruta, notas del hito 3). Es un
   evento del estudio y no uno por intento, porque la cadena guarda pocos
   eventos (ADR-0010, punto 16); el detalle de los intentos va dentro de él.
5. **Decisión del investigador.** Después de un `consulta_fallida`, el agente
   propone: esperar y reintentar otro día, A, o declarar la limitación. El
   investigador elige en su terminal y la elección se registra en el evento
   `decision_degradacion` (nombre provisional), con la justificación. Si
   persiste el fallo tras reintentar en varias sesiones, el agente propone A;
   el umbral lo fija el 3a y es configurable.
6. **A exige una enmienda si la búsqueda ya empezó.** `importar registrar` solo
   acepta una fuente declarada con `tipo: exportacion` (ADR-0010, punto 11). Si
   el protocolo vigente declara la fuente como `api` y la búsqueda ya empezó,
   cambiar su tipo es una enmienda con fecha y justificación (regla 5), que cita
   el evento `consulta_fallida`. Si la fuente **no ofrece exportación** desde su
   interfaz, A no es posible y se declara la limitación.
7. **Nunca se sustituye una fuente en silencio.**
   - El agente no cambia de fuente por su cuenta ni completa los resultados de
     una con los de otra.
   - Si el investigador decide **reemplazar** una fuente por otra, es una
     enmienda del protocolo con justificación metodológica, como cualquier
     cambio de estrategia (regla 5). No es una vía de degradación automática.
   - Un resultado guardado en la caché solo se reutiliza si la consulta y sus
     parámetros son idénticos, y se registra con su origen («caché») y la fecha
     de la respuesta original. Nunca se presenta como una consulta nueva.
8. **Una búsqueda interrumpida es incompleta.** Si el fallo ocurre a mitad de
   un paginado, la búsqueda se marca como `incompleta`, y no cuenta como
   completa en los conteos del diagrama de flujo. Puede reanudarse dentro del
   mismo registro de búsqueda.
9. **Declaración en el reporte.** El reporte lista cada fuente que tuvo
   fallos, los intentos, la decisión tomada y, si quedó una fuente sin cubrir
   o una búsqueda incompleta, la **limitación**: es una amenaza a la validez
   (ADR-0009, punto 16) y se declara siempre que haya cobertura perdida.
10. **Detección previa.** El diagnóstico de fuentes (hito 3, sub-hito 3a)
    permite saber antes de buscar qué fuentes responden. Su resultado no es un
    registro de la búsqueda del estudio: se guarda solo en el equipo del
    investigador.

### AGROVOC: copia local como vía principal

11. **Decisión.** El agente usa una **copia local descargada de AGROVOC,
    identificada por su versión y su hash**, como vía principal. El servicio
    REST de Skosmos es un **apoyo opcional**, que el investigador pide
    explícitamente.
12. **Por qué.** Es un uso con un fin concreto, la propuesta de sinónimos para
    la ecuación PCC, que el investigador decide (regla 9). Con una copia local
    el resultado depende de un archivo con versión y hash, no de un servicio
    que hoy estuvo caído y que no declara su versión. La FAO publica una
    versión nueva cada mes (abajo).
13. **Lo verificado de la descarga oficial** (consultado el 2026-10-04):

    | Dato | Valor | Estado |
    |---|---|---|
    | Licencia | El contenido en inglés, ruso, francés, español, árabe y chino está bajo CC-BY 4.0 ([fao.org/agrovoc/maintenance](https://www.fao.org/agrovoc/maintenance)) | verificado en la fuente oficial |
    | Titularidad | El copyright del contenido en esos idiomas es de la FAO; el de los demás idiomas, de las instituciones que lo crearon (misma página) | verificado |
    | Discrepancia | La [FAQ de AIMS](https://aims.fao.org/standards/agrovoc/faq) todavía dice CC-BY IGO 3.0; la página de versiones es de 2020 | **por confirmar por el investigador** antes del 3a |
    | Frecuencia | El contenido actualizado se publica una vez al mes (misma página) | verificado |
    | Formatos | *AGROVOC Core* (todos los idiomas): RDF/XML y N-Triples. *AGROVOC LOD*: N-Triples y N-Quads ([fao.org/agrovoc/releases](https://www.fao.org/agrovoc/releases)) | verificado; esa página no da tamaños ni nombres de archivo |
    | Dónde se ofrecen las descargas | El catálogo de la FAO, [data.apps.fao.org](https://data.apps.fao.org/catalog/organization/agrovoc) | enlazado desde la página de versiones; devolvió 403 a la consulta automática y no se pudo leer |
    | Número de versión | No existe: el alias `latestAgrovoc` cambia cada mes y el nombre del archivo no lo lleva | observado |
    | Tamaño medido (solo encabezados, sin descargar) | `https://agrovoc.fao.org/latestAgrovoc/agrovoc_lod.nt.zip`: 96 365 215 bytes; `…/agrovoc_core.nt.zip`: 73 760 195 bytes; ambos con `Last-Modified` 2026-09-07, que coincide con la fecha de modificación que muestra su sitio | medido por Claude Code el 2026-10-04. **No está en una página oficial:** la ruta del LOD salió de un resultado de búsqueda de terceros, y el nombre del Core es una inferencia que respondió 200 |
    | Tamaño descomprimido | no medido | pendiente: se mide al descargar, en el 3e |

    Las versiones en N-Triples tienen un triple por línea, así que se pueden
    leer en flujo con la biblioteca estándar, sin agregar una dependencia. Si se
    usara una biblioteca de RDF, se verifica su licencia y se justifica al
    agregarla (CLAUDE.md).
14. **Qué archivo.** Para proponer sinónimos basta *AGROVOC Core* en N-Triples
    (todos los idiomas, sin los enlaces externos del LOD). El LOD agrega la
    materialización de etiquetas SKOS y el vocabulario Agrontology con
    procedencia, que este uso no necesita. El 3e confirma la elección con el
    archivo real.
15. **Nota de versión.** Cada estudio que use AGROVOC guarda en un archivo
    versionado (ruta provisional `recursos/agrovoc.yaml`): la URL de descarga,
    la fecha de la descarga, el `Last-Modified` observado, el tamaño, el
    **SHA-256 calculado en local**, el formato, la licencia y la atribución que
    exige CC-BY. La propuesta de sinónimos registra la nota de versión que
    usó.
16. **Dónde vive la copia.** En una carpeta del estudio ignorada por Git (ruta
    provisional `recursos_locales/agrovoc/`), con `git check-ignore` como en el
    ADR-0010 (punto 7). No se versiona: es un archivo grande, de terceros y
    regenerable desde la fuente con su hash. Es consistente con el principio
    «local completo, nube mínima y configurable» del ADR-0010.
17. **Actualización.** El estudio fija una versión al empezar a usarla.
    Actualizarla es una decisión del investigador: se baja la versión nueva, se
    escribe una nota nueva y se informa que las propuestas anteriores usaron la
    versión previa. No hay actualización automática.
18. **El apoyo en vivo (REST de Skosmos).** Solo se usa si el investigador lo
    pide, y sus respuestas se registran con su fecha, sin número de versión. No
    reemplaza a la copia local en silencio (punto 7): si falta la copia, el
    agente lo dice y propone descargarla.
    - Reglas verificadas por el asesor en la documentación de Skosmos
      ([api.finto.fi/doc](https://api.finto.fi/doc/)); Claude Code no las
      reverificó. La base es la URL de la instancia más `/rest/v1/`, con los
      métodos globales `/vocabularies`, `/search`, `/label`, `/data` (turtle,
      rdf+xml y json-ld) y `/types`.
    - En `/search` se fija **siempre** `maxhits` (si se omite devuelve todos
      los resultados), se pagina con `offset` y se usa `unique=true`.
    - La ruta exacta de la instancia de AGROVOC se confirma al implementar.
    - Diagnóstico mínimo de disponibilidad: `/vocabularies?lang=en` y
      `/search?query=hemp*&lang=en&maxhits=1`.
19. **Criterio de omisión.** Si antes del 3e la licencia no se confirma, el
    formato o el tamaño no coinciden con lo documentado, o el investigador no
    valida la descarga, AGROVOC se omite de `v0.3.0` con la razón escrita y el
    estudio propone los sinónimos sin tesauro; se declara como limitación.

## Alternativas consideradas

- **Reintentar sin límite (solo B):** absorbe fallos cortos pero consume cuota,
  oculta una caída larga y no resuelve un 429 estructural, como el de Semantic
  Scholar sin clave.
- **Pasar siempre a importación manual (solo A):** siempre es posible exportar
  a mano, pero después de iniciada la búsqueda exige una enmienda, y se pierde
  la automatización por un fallo que puede ser de una hora.
- **Declarar solo la limitación (solo C):** es honesto y lo exige PRISMA-ScR,
  pero no recupera la cobertura perdida. Se conserva como obligación del
  reporte (punto 9), no como política.
- **Sustituir la fuente (D):** mantiene la cobertura, pero cambia la estrategia
  de búsqueda. Solo con enmienda y justificación, nunca como degradación
  automática (punto 7).
- **Un evento por intento fallido:** más detalle, pero llena la cadena de
  eventos del estudio con datos de red; se prefirió un evento por consulta
  fallida con sus intentos dentro.
- **AGROVOC solo en vivo:** sin descargas, pero hoy estuvo caído, no tiene
  versión fija y el resultado no es reproducible.
- **AGROVOC solo con copia local, sin apoyo en vivo:** más simple, pero el
  investigador no podría consultar un concepto reciente sin descargar la
  versión nueva.
- **Versionar la copia de AGROVOC en el repositorio:** la licencia lo permite
  con atribución, pero son entre 74 y 96 MB de datos de terceros regenerables;
  se versiona su nota de versión, no el archivo.
- **AGROVOC LOD en lugar de Core:** trae enlaces externos y procedencia que
  este uso no aprovecha, y pesa más.

## Consecuencias

- Una caída de una fuente no detiene el estudio ni cambia su búsqueda sin que
  el investigador lo decida y quede registrado.
- El reporte puede declarar con exactitud qué fuentes tuvieron fallos, qué se
  hizo y qué cobertura se perdió.
- El hito 3 debe implementar el reintento, el presupuesto diario persistente y
  los eventos `consulta_fallida` y `decision_degradacion` (3a), con pruebas que
  simulen cada tipo de fallo y verifiquen que ni la clave ni el correo
  aparecen en lo guardado.
- Los nombres de los eventos, las rutas de AGROVOC y los valores por defecto
  son provisionales y se fijan en el 3a y el 3e, con su especificación.
- La copia de AGROVOC suma entre 74 y 96 MB por estudio (zip) que el
  investigador debe conservar o volver a descargar; la nota de versión permite
  comprobar que es la misma.
- El reporte de un estudio que use AGROVOC debe incluir la atribución que exige
  CC-BY 4.0.
- Hay que confirmar la discrepancia de licencia (CC-BY 4.0 frente a CC-BY IGO
  3.0) antes del 3e, y la licencia de los idiomas distintos de los seis de la
  FAO si un estudio los usa.

## Verificación de la política contra lo pedido

El asesor pidió que la política cumpla cuatro condiciones, a las que se suma la
regla 1 de CLAUDE.md. Aquí se comprueba dónde se cumple cada una.

| Condición | Dónde se cumple |
|---|---|
| Reintentos con espera | Puntos 2 y 3: solo fallos transitorios, espera creciente con máximo de intentos, respeto de `Retry-After` y de los límites de la fuente |
| Registro del fallo en la trazabilidad | Punto 4: evento `consulta_fallida` en la cadena, con la lista de intentos y sin credenciales; punto 5: la decisión también queda registrada |
| Paso a importación manual (RIS) cuando una API no está disponible | Definición de A y puntos 5 y 6: del mismo origen, con enmienda si la búsqueda ya empezó, y declarada la limitación si la fuente no exporta |
| Nunca sustituir una fuente por otra en silencio | Punto 7 (sin cambio automático, sin completar con otra fuente, sustitución solo por enmienda, caché etiquetada) y punto 18 (AGROVOC en vivo nunca reemplaza la copia en silencio) |
| El investigador decide (regla 1) | Puntos 1 y 5 |

Queda por verificar con la implementación, y no se afirma aquí, que el código
cumpla estos puntos: las pruebas del 3a deben cubrir cada fila de la tabla.
