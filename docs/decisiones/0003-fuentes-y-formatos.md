# ADR-0003: Fuentes de información y formatos de importación

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral y Claude (asesor)

## Contexto

El agente debe usar recursos gratuitos, y el investigador tiene acceso institucional a bases de suscripción (Scopus, ScienceDirect, Web of Science, IEEE, etc.) solo por su interfaz web. El caso piloto es del área agraria y agroindustrial. Las condiciones de acceso de cada API se verificaron el 2026-09-25; deben volver a verificarse al implementar cada conector.

## Decisión

### APIs en la versión 1

| Fuente | Uso | Acceso (verificado 2026-09-25) |
|--------|-----|--------------------------------|
| OpenAlex | Búsqueda multidisciplinaria, citas para bola de nieve | Clave gratuita obligatoria; 1 USD de uso diario gratis (unas 1.000 búsquedas o 10.000 consultas con filtro al día); datos CC0 |
| Semantic Scholar | Búsqueda, referencias y citas para bola de nieve | Clave gratuita; 1 solicitud por segundo garantizada |
| PubMed (NCBI E-utilities) | Literatura biomédica y de salud | Gratuito; clave opcional que aumenta el límite (confirmar límites al implementar) |
| Springer Nature Open Access API | Metadatos y texto de artículos de acceso abierto | Clave gratuita (confirmar cuotas al implementar) |
| Crossref | Completar metadatos por DOI y apoyar la deduplicación | Gratuito, sin clave |
| AGROVOC (FAO) | Tesauro agrícola multilingüe para proponer sinónimos en la ecuación PCC | Gratuito; SPARQL y API REST (Skosmos) |

### Importación de exportaciones manuales

RIS, BibTeX, CSV de Scopus, Web of Science en formato de etiquetas (.txt) y CSV genérico con mapeo de columnas configurable, que cubre, por ejemplo, las exportaciones de Lens.

### Texto completo

El cribado se hace por título y resumen. En la fase de texto completo, el agente trabaja con los PDF que el investigador descarga con su acceso institucional. En la versión 1 no se descargan automáticamente versiones de acceso abierto.

### Reglas para todas las fuentes

- Cada búsqueda guarda la consulta exacta, la fuente, la fecha y hora, los parámetros, la respuesta cruda y el número de resultados.
- Cada archivo importado guarda su hash SHA-256.
- Las claves de API viven en `.env` y nunca se versionan.

## Alternativas consideradas

- **API de Elsevier (Scopus y ScienceDirect):** se deja para una fase posterior como conector opcional, porque depende de la red institucional y de sus términos.
- **AGRIS (FAO) y Lens:** no se encontró una API pública de AGRIS, y la API de Lens solo ofrece una prueba de 14 días. Se usan mediante exportación manual.
- **CORE y Europe PMC:** no se incluyen en la versión 1; pueden añadirse después.

## Consecuencias

- Los conectores comparten una interfaz común, una caché de respuestas crudas y un control de tasa, de modo que agregar una fuente nueva no altera el resto.
- Como las fuentes cambian con el tiempo, la búsqueda es reproducible a partir de las respuestas crudas guardadas, no volviendo a consultar la API.

## Nota posterior (2026-09-29): ACS Publications y alcance del acceso institucional

Decidido por el investigador con el asesor al planificar el hito 2. El
ADR-0010 lo formaliza.

1. **ACS Publications se agrega a las fuentes por exportación manual,**
   junto a Scopus y Web of Science. El investigador entra con el acceso
   institucional de la Universidad del Cauca. Es la plataforma de una sola
   editorial, la American Chemical Society: según la descripción de la
   biblioteca, más de 90 revistas y unos 2,2 millones de artículos desde
   1879, en química y áreas afines (alimentos, agricultura, materiales,
   energía). Se solapa con Scopus y Web of Science, así que el protocolo
   que la declare debe justificarla (PRISMA-ScR, ítem 7).
2. **Interfaz observada (capturas del investigador, 2026-09-29).** La
   búsqueda avanzada es un constructor de consultas por filas: en cada fila
   se elige un campo («Filter by», con «All» por defecto), se escribe el
   término y se marca o no «Exact Match». Las filas se combinan con
   «Match» (AND por defecto). Hay filtros adicionales y búsqueda por cita.
   No hay un cuadro para pegar una ecuación completa con etiquetas de
   campo, como en Scopus o Web of Science.
3. **Por verificar en la ayuda oficial de ACS antes de implementar.** La
   página de ayuda rechazó la consulta automática, y las guías de
   bibliotecas no son fuente oficial. Hay que confirmar:
   - los campos de «Filter by», y si «All» incluye el texto completo. Si lo
     incluye, el alcance difiere del título y resumen de las demás fuentes,
     y es una amenaza a la validez (ADR-0009, punto 16);
   - los operadores, los paréntesis dentro de una fila, las frases, el
     truncamiento y la lematización;
   - cómo se combinan las filas, y si se puede expresar
     `(bloque 1) AND (bloque 2)` sobre título y resumen;
   - los formatos de «Download Citations» (las guías citan RIS con la
     opción «Citation and abstract») y el máximo de registros por descarga.
4. **Ecuación.** Mientras no haya un traductor para ACS, `ecuaciones.md` la
   lista como fuente sin traductor, con la ecuación genérica (ADR-0009,
   punto 4). El ADR-0010 decide, según lo que se verifique, si se agrega un
   traductor o instrucciones para el constructor por filas.
5. **El alcance depende del contrato de la institución.** En Scopus, Web of
   Science y ACS, lo que el investigador puede buscar y exportar depende
   del contrato de su universidad; por ejemplo, las ediciones y los años de
   Web of Science Core Collection que muestra «Editions». Por eso cada
   búsqueda manual registra la plataforma, la institución de acceso y la
   cobertura disponible, además de la ecuación, la fecha y hora y el número
   de resultados (hoja de ruta, nota del hito 2). El acceso al texto
   completo también depende del contrato (hoja de ruta, nota del hito 7).
6. **Términos de uso.** El agente nunca automatiza estas interfaces con las
   credenciales institucionales: el investigador busca y exporta a mano.
   Las exportaciones se tratan según la política de datos de terceros del
   ADR-0010.

## Nota posterior (2026-10-04): reproducibilidad y respuestas crudas

Pedida por el asesor al revisar el ADR-0010 (propuesta). No cambia la decisión
de las fuentes; precisa una consecuencia.

- La consecuencia «la búsqueda es reproducible a partir de las respuestas
  crudas guardadas, no volviendo a consultar la API» **ya no aplica a los
  campos restringidos.** Las respuestas crudas completas de una API contienen
  datos de terceros (por ejemplo, los resúmenes) que no se publican, y el
  repositorio de un estudio se publica.
- Las respuestas crudas completas se guardan **solo en el equipo del
  investigador**, en una carpeta ignorada por Git. En el repositorio van su
  hash y los campos que el estudio habilite, con la base de esa habilitación.
- **La reproducción se apoya en la copia local y en los hashes registrados:**
  quien tenga la copia local verifica que es la misma comprobando su hash, y un
  tercero sin ella reproduce solo lo que depende de campos versionados.
- Lo mismo vale para las exportaciones manuales. El detalle está en el
  ADR-0010 (puntos 1 a 4); esta nota no lo repite.

## Nota posterior (2026-10-04): condiciones de acceso verificadas y prueba en vivo

Resultado de volver a verificar las APIs antes del hito 3, con tres orígenes
que se distinguen en cada dato: **O**, leído en la página oficial por Claude
Code el 2026-10-04; **A**, verificado por el asesor en la documentación
oficial; **I**, prueba en vivo del investigador en su equipo el 2026-10-04.
Las cifras son las que dicen esas fuentes: no se agregó ninguna otra.

### Corrección de la fila de OpenAlex

La fila de OpenAlex de la tabla de arriba **ya no es correcta**: la clave no es
obligatoria. Según la ayuda oficial
([help.openalex.org/api/authentication](https://help.openalex.org/api/authentication),
actualizada el 2026-08-19 según el asesor):

- la clave es **opcional pero recomendada** y gratuita: sin ella se hacen
  consultas básicas, y con ella el presupuesto diario se multiplica por 10
  (O, A);
- el máximo es de 100 solicitudes por segundo, y exceder ese ritmo o el
  presupuesto diario devuelve 429 (O, A);
- `per_page` admite como máximo 100, y el paginado básico llega a 10 000
  resultados; más allá se usa el paginado por cursor (O, A);
- la página **no expresa el presupuesto en dólares ni en solicitudes**. La
  afirmación «1 USD de uso diario» y sus equivalencias de la tabla original no
  tienen respaldo en la página actual;
- los encabezados de la respuesta son `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, `X-RateLimit-Credits-Used` y `X-RateLimit-Reset`
  (segundos hasta la medianoche UTC) (O).

### Verificado, por fuente

| Fuente | Qué dice la documentación oficial | Origen |
|---|---|---|
| NCBI E-utilities | 3 solicitudes por segundo sin clave y 10 con clave; trabajos grandes en fin de semana o entre las 21:00 y las 05:00, hora del Este; enviar `tool` y `email`. Guía [NBK25497](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | A. Claude Code no pudo reconsultarla: la página devolvió un reCAPTCHA |
| Semantic Scholar | La clave es opcional y gratuita. Sin clave se comparte un grupo común («1000 requests per second shared among all unauthenticated users», con posible limitación adicional en uso intenso); con clave, el límite introductorio es 1 solicitud por segundo. Exige aceptar su licencia de la API ([semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)) | O, A |
| Crossref | Sin clave. Grupo público y grupo *polite*, que exige el parámetro `mailto`; al exceder se devuelve 429 ([documentación de acceso](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/)). **No se registran cifras de límites**: la lectura no dio el intervalo. La documentación consultada no dice nada sobre los derechos de los resúmenes | O |
| Springer Nature OA | Plan Basic: 500 consultas al día, con control de tasa de 100 por minuto y una sola clave por cuenta; el Premium sube a 10 000 y 300 ([página del producto](https://datasolutions.springernature.com/products/open-access/)) (O). Tamaño máximo de página `p` = 20, el inicio se pasa con `s`, una clave por usuario, la clave viaja en la URL, y la licencia Creative Commons de cada artículo rige el uso de su contenido (A) | O y A, como se indica |
| AGROVOC | Contenido en inglés, ruso, francés, español, árabe y chino bajo CC-BY 4.0; el de otros idiomas pertenece a las instituciones que lo crearon; una versión nueva cada mes ([fao.org/agrovoc/maintenance](https://www.fao.org/agrovoc/maintenance)) (O). API de Skosmos documentada en api.finto.fi/doc (A); ver el ADR-0011 | O y A, como se indica |

### No verificado

- **Springer:** el acuerdo de uso de la API lo leyó el investigador; Claude Code
  **no lo verificó** y no lo cita. Tampoco verificó el tamaño de página ni la
  licencia por artículo, que son del asesor. El límite diario de 500 sale del
  texto de la página del producto: la respuesta de la API no trae encabezados
  de límite (I).
- **Licencia de AGROVOC:** la fuente oficial vigente dice CC-BY 4.0, pero la
  [FAQ de AIMS](https://aims.fao.org/standards/agrovoc/faq) todavía dice
  «CC-BY IGO 3.0», y la página de versiones es de 2020 y cita la versión
  2022-04. Se toma la primera como vigente y se deja la discrepancia a
  confirmar por el investigador **antes del sub-hito 3a** (hoja de ruta).
- **Crossref:** los intervalos de sus límites y los derechos de sus
  resúmenes.
- **OpenAlex:** la unidad del presupuesto. El diagnóstico de fuentes (hito 3,
  sub-hito 3a) debe medirla.
- **NCBI:** Claude Code no reverificó las cifras (arriba).

### Prueba en vivo del investigador (I, 2026-10-04, su equipo)

| Fuente | Sin clave | Con clave |
|---|---|---|
| OpenAlex | 200 | 200; `X-RateLimit-Remaining: 9990` tras una consulta de búsqueda (unidad no confirmada) |
| Crossref | 200 | no aplica |
| PubMed (NCBI) | 200 | 200; 9123 resultados en una consulta de prueba |
| Semantic Scholar | tiempo de espera agotado y luego 429, en dos intentos: el grupo compartido sin clave estaba saturado | sin clave aún |
| Springer Nature OA | no probado | 200; total 301 en una consulta de prueba; sin encabezados de límite en la respuesta |
| AGROVOC | REST con error 500 en tres intentos; SPARQL con 503; el sitio web con 200 (los servicios de datos de la FAO estaban caídos) | no aplica |

Los números de resultados (9123 y 301) vienen de consultas de prueba del
investigador, con fecha, y no de una fuente oficial. Estas observaciones son
las que motivan el ADR-0011 (degradación ante fuentes inestables).
