# Guía de las secciones del protocolo

Para cada sección: para qué sirve, qué guía la exige, qué preguntar y qué reglas del paquete la vigilan. Las referencias de esta guía son las del proyecto agentresearch y se pueden citar en las opciones:

- Kitchenham, B. y Charters, S. (2007). *Guidelines for performing systematic literature reviews in software engineering* (EBSE-2007-01).
- Petersen, K., Feldt, R., Mujtaba, S. y Mattsson, M. (2008). Systematic mapping studies in software engineering. *EASE 2008*.
- Petersen, K., Vakkalanka, S. y Kuzniarz, L. (2015). Guidelines for conducting systematic mapping studies in software engineering: An update. *Information and Software Technology*, 64, 1-18.
- Tricco, A. C. et al. (2018). PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and explanation. *Annals of Internal Medicine*, 169(7), 467-473.
- Peters, M. D. J. et al. (JBI). Guía para revisiones de alcance (*scoping reviews*) del JBI Manual for Evidence Synthesis.
- Wohlin, C. (2014). Guidelines for snowballing in systematic literature studies and a replication in software engineering. *EASE 2014*.
- Wohlin, C. et al. (2013). On the reliability of mapping studies in software engineering. *Journal of Systems and Software*, 86(10), 2594-2610.
- Landis, J. R. y Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159-174.

Si citas otra referencia, debe ser una que puedas verificar; si no, dilo.

## `metadatos`

- **Para qué:** identificar el protocolo, sus autores y dónde se registra. **Guía:** PRISMA-ScR, ítems 5 (protocolo y registro) y 22 (financiación).
- **Preguntar:** título; autores con ORCID y rol; si se registrará el protocolo (p. ej. OSF) y dónde; financiación.
- **No cambies** `version_protocolo`: la asigna el paquete al aprobar y al enmendar.

## `justificacion`, `objetivos` y `pregunta_general`

- **Para qué:** por qué hace falta este mapeo y por qué un enfoque de alcance y no una revisión sistemática; qué se busca conocer. **Guía:** PRISMA-ScR, ítems 3 y 4; Petersen et al. (2015).
- **Preguntar:** qué vacío motiva el estudio; si ya existen revisiones sobre el tema; qué decisiones o investigaciones informará el mapa.
- Cada una es una sección aparte para `protocolo escribir`.

## `preguntas`

- **Para qué:** las preguntas específicas, con ID (`PI1`, `PI2`…). Las descriptivas dicen qué datos (`DE`) o facetas (`F`) las responden (`responde_con`); las analíticas, de qué cruces se derivan (`derivada_de`). **Guía:** PRISMA-ScR, ítem 4; Petersen et al. (2015), tabla 3.
- **Preguntar:** qué quiere saber el investigador que un conteo o un mapa pueda responder. Los IDs de `DE` y `F` se crean después en `extraccion`: acuerda nombres provisionales y regresa si cambian.
- **Reglas:** P-E01 (IDs), P-E02 (referencias existentes), P-E03 (cada pregunta tiene con qué responderse).

## `marco`

- **Para qué:** población, concepto y contexto (PCC, del JBI), con su equivalencia PICOC (Kitchenham). **Guía:** Peters et al. (JBI); Kitchenham y Charters (2007); Petersen et al. (2015), §5.1.2.
- **Preguntar:** qué es la población y el concepto, con sus términos; qué contexto interesa.
- **Advertir:** el contexto no debería restringir la búsqueda en un mapeo (P-A02). Si el investigador quiere que restrinja, registra la decisión.
- **Reglas:** P-E04 (población y concepto no vacíos), P-A02.

## `fuentes`

- **Para qué:** las bases que se consultan, con su cobertura y sus límites. **Guía:** PRISMA-ScR, ítem 7.
- **Preguntar:** qué bases usa la disciplina; cuáles tiene disponibles el investigador (Scopus y Web of Science se usan por exportación manual; OpenAlex y PubMed, por API).
- **Nota:** el paquete traduce ecuaciones para las fuentes con ID `openalex`, `pubmed`, `scopus` y `wos`; las demás usan la ecuación genérica. `tipo` es `api` o `exportacion`.

## `estrategias`

- **Para qué:** cómo se identifican los estudios: bases de datos, bola de nieve (hacia atrás y hacia adelante), búsqueda manual, el conjunto de validación y el criterio de parada. **Guía:** Petersen et al. (2015), §5.1.2 y tabla 10; Wohlin (2014).
- **Preguntar:** si hará bola de nieve y en qué direcciones; de 5 a 10 artículos clave que el investigador conozca por vías distintas de las bases (con DOI o título, y cómo los conoce); el criterio de parada (`umbral_nuevos` o `presupuesto_tiempo`) y su justificación.
- **Nunca** propongas artículos del conjunto de validación de memoria: los aporta el investigador.
- **Reglas:** P-A03 (una sola estrategia activa), P-A04 (conjunto de validación inactivo o con menos de 5 artículos).

## `busqueda`

- **Para qué:** los bloques de términos (OR dentro de cada bloque, AND entre bloques), el periodo, los idiomas y los tipos de documento. **Guía:** PRISMA-ScR, ítems 6 y 8; ADR-0009 de agentresearch.
- **Preguntar:** los términos de cada bloque; si hay truncados, sus variantes (ver SKILL.md); periodo e idiomas, cada uno con su justificación.
- **Forma de un término:** una palabra (con guiones o apóstrofos internos), una palabra truncada (`secad*`) o una frase entre comillas (`"secado solar"`). Varias palabras sin comillas, operadores o comodines distintos de `*` al final son P-E11.
- **Advertir:** acrónimos cortos sueltos (P-A07), y periodo o idioma restringidos sin justificación (P-A05). Idiomas en ISO 639-1 (`en`, `es`…).
- Al cerrar, ejecuta `protocolo ecuaciones` y revisa los avisos de cada fuente con el investigador.

## `criterios`

- **Para qué:** criterios de inclusión (`CI`) y de exclusión (`CE`), con su fase (`titulo_resumen`, `texto_completo` o `ambas`), su tipo y ejemplos de lo que cumple y lo que no. **Guía:** PRISMA-ScR, ítem 6; Petersen et al. (2015), §5.1.2.
- **Preguntar:** un criterio a la vez, con un ejemplo que sí y uno que no.
- **Advertir:** en un mapeo, exigir evaluación empírica suele ser inapropiado (P-A01).
- **Reglas:** P-E01, P-E05 (fase declarada), P-A01.

## `seleccion`

- **Para qué:** revisores (al menos un humano), la regla para combinar sus decisiones (letras A a F de la tabla 6), el piloto de concordancia y el tamaño del lote del LLM. **Guía:** PRISMA-ScR, ítem 9; Petersen et al. (2015), tabla 6; Landis y Koch (1977) para el umbral de kappa.
- **Preguntar:** quiénes revisan y con qué ID; qué casos avanzan a texto completo; tamaño del piloto y umbral de kappa.
- **Reglas:** P-E06 (la regla contiene A y no F), P-E07 (al menos un humano), P-E08, P-A08 (un solo revisor humano), P-A09 (piloto sin tamaño).
- El `id` de un revisor humano es el que el investigador usará en `--aprobado-por` y `--confirmado-por`.

## `extraccion`

- **Para qué:** el formulario de extracción (`DE`, ligado a las preguntas) y las facetas de clasificación (`F`), cada categoría con definición, regla y ejemplos. **Guía:** PRISMA-ScR, ítems 10 y 11; Petersen et al. (2015); Wohlin et al. (2013).
- **Preguntar:** qué dato responde cada pregunta; qué facetas son existentes (de un esquema publicado) y cuáles emergentes (por *keywording*).
- **Reglas:** P-E02, P-E03, P-A06 (categoría sin definición, regla o ejemplos).

## `calidad`

- **Para qué:** la evaluación de calidad, opcional en los mapeos. **Guía:** PRISMA-ScR, ítem 12; Petersen et al. (2015).
- **Preguntar:** si se hará y con qué preguntas. Si no se hace, que quede explícito.

## `analisis`

- **Para qué:** el plan de síntesis y los cruces de facetas o datos que alimentan los mapas. **Guía:** PRISMA-ScR, ítem 13; Petersen et al. (2015), §5.1.4.
- **Preguntar:** qué conteos y mapas responden cada pregunta analítica.
- **Reglas:** P-E02 (cruces con IDs existentes); cada cruce tiene al menos dos IDs.
