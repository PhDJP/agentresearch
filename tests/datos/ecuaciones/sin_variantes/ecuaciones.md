# Ecuaciones de búsqueda

Generado por agentresearch a partir del protocolo; no lo edite a mano. Regenérelo con `agentresearch protocolo ecuaciones --escribir` después de aprobar o enmendar el protocolo (ADR-0009).

- Protocolo: protocolo/protocolo.yaml
- Versión del protocolo: 1.0.0 (vigente)
- Hash del protocolo: sha256:0000000000000000000000000000000000000000000000000000000000000000
- Versión del agente: 0.0.0-prueba
- Fuentes bloqueadas: openalex, pubmed, scopus, wos

## Límites del protocolo

- Periodo: desde 2015, inclusive
- Idiomas: en (inglés), español (no reconocido)
- Tipos de documento: artículo, poster (no reconocido)

## OpenAlex

- Campos: título y resumen (title_and_abstract.search)
- Límites: se aplicarán con el conector de OpenAlex (hito 3)
- Sintaxis verificada en: [Search – Querying (OpenAlex Help Center)](https://help.openalex.org/api/searching/) (2026-09-26); [Searching guide (OpenAlex)](https://help.openalex.org/guides/searching) (2026-09-26); [Consultas de verificación a la API de OpenAlex (ADR-0009, punto 9)](https://api.openalex.org/works) (2026-09-27)

**Sin ecuación:** la fuente quedó bloqueada. Resuelva los avisos bloqueantes y vuelva a generar las ecuaciones.

Avisos:

- advertencia [B1]: el bloque B1 usa la búsqueda sin lematizar (search.exact): en este bloque, OpenAlex no buscará plurales ni otras formas de los términos sin *. Motivo: tiene términos truncados sin variantes (by-product*, fru*). Para conservar la lematización en el bloque, escriba sus variantes
- nota [B1, by-product*]: se escribe entre comillas: sin ellas, OpenAlex busca las partes del término con guion unidas por AND, no como frase
- nota [B1, post-extraction]: se escribe entre comillas: sin ellas, OpenAlex busca las partes del término con guion unidas por AND, no como frase
- advertencia [B2]: el bloque B2 usa la búsqueda sin lematizar (search.exact): en este bloque, OpenAlex no buscará plurales ni otras formas de los términos sin *. Motivo: tiene términos truncados sin variantes (dehydrat*, "freeze dr*", "fruto sec*"). Para conservar la lematización en el bloque, escriba sus variantes
- bloqueante [B2, "freeze dr*"]: OpenAlex exige al menos 3 letras antes del *, y '"freeze dr*"' tiene una raíz más corta. Agregue en busqueda.bloques[B2].variantes las variantes de '"freeze dr*"' que OpenAlex debe buscar en su lugar
- advertencia [B2, liofilización]: OpenAlex distingue las letras con tilde de las sin tilde (verificado el 2026-09-27); si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)

## PubMed

- Campos: título y resumen ([tiab])
- Límites: se aplicarán con el conector de PubMed (hito 3)
- Sintaxis verificada en: [PubMed User Guide](https://pubmed.ncbi.nlm.nih.gov/help/) (2026-09-26)

**Sin ecuación:** la fuente quedó bloqueada. Resuelva los avisos bloqueantes y vuelva a generar las ecuaciones.

Avisos:

- advertencia [B1, by-product*]: PubMed busca un término con guion como frase y, si no está en su índice de frases, no devuelve resultados; compruébelo en la interfaz o agregue la forma sin guion como frase aparte
- advertencia [B1, post-extraction]: PubMed busca un término con guion como frase y, si no está en su índice de frases, no devuelve resultados; compruébelo en la interfaz o agregue la forma sin guion como frase aparte
- bloqueante [B1, fru*]: PubMed exige al menos 4 letras antes del *, y 'fru*' tiene una raíz más corta. Agregue en busqueda.bloques[B1].variantes las variantes de 'fru*' que PubMed debe buscar en su lugar
- bloqueante [B2, "freeze dr*"]: PubMed exige al menos 4 letras antes del *, y '"freeze dr*"' tiene una raíz más corta. Agregue en busqueda.bloques[B2].variantes las variantes de '"freeze dr*"' que PubMed debe buscar en su lugar
- bloqueante [B2, "fruto sec*"]: PubMed exige al menos 4 letras antes del *, y '"fruto sec*"' tiene una raíz más corta. Agregue en busqueda.bloques[B2].variantes las variantes de '"fruto sec*"' que PubMed debe buscar en su lugar
- advertencia [B2, liofilización]: PubMed no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)

## Scopus

- Campos: título, resumen y palabras clave (TITLE-ABS-KEY); las palabras clave incluyen las del autor, los términos indexados, los nombres comerciales y los nombres químicos
- Límites: en la ecuación (PUBYEAR > 2014); en la interfaz (ver los pasos)
- Sintaxis verificada en: [Scopus Search Tips (Elsevier Developer Portal)](https://dev.elsevier.com/sc_search_tips.html) (2026-09-26); [How can I best use the Advanced search? (Scopus)](https://www.elsevier.support/scopus/answer/how-can-i-best-use-the-advanced-search) (2026-09-26)

**Sin ecuación:** la fuente quedó bloqueada. Resuelva los avisos bloqueantes y vuelva a generar las ecuaciones.

Avisos:

- nota [B1, by-product*]: se escribe entre comillas: Elsevier solo documenta el guion dentro de una frase aproximada (lo ignora y admite comodines), y lo no documentado se trata como no admitido
- nota [B1, post-extraction]: se escribe entre comillas: Elsevier solo documenta el guion dentro de una frase aproximada (lo ignora y admite comodines), y lo no documentado se trata como no admitido
- bloqueante [B2, "freeze dr*"]: Scopus exige al menos 3 letras antes del *, y '"freeze dr*"' tiene una raíz más corta. Agregue en busqueda.bloques[B2].variantes las variantes de '"freeze dr*"' que Scopus debe buscar en su lugar
- advertencia [B2, liofilización]: Scopus no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)
- advertencia: idiomas no reconocidos ('español'): el filtro de idioma de Scopus se da como instrucción de la interfaz. Use códigos ISO 639-1 (p. ej. es, en) para que se traduzca
- advertencia: tipos de documento no reconocidos ('poster'): el filtro de tipo de Scopus se da como instrucción de la interfaz, sin convertirlos. Tipos del vocabulario controlado (ADR-0009, punto 10): articulo, revision, conferencia, capitulo, libro, editorial, carta, nota

## Web of Science

- Campos: título, resumen, palabras clave de autor y Keywords Plus (TS)
- Límites: en la interfaz (ver los pasos)
- Sintaxis verificada en: [Search Rules (Web of Science)](https://webofscience.zendesk.com/hc/en-us/articles/25350084904721-Search-Rules) (2026-09-26); [Web of Science Core Collection Search Fields](https://webofscience.zendesk.com/hc/en-us/articles/26916258216209-Web-of-Science-Core-Collection-Search-Fields) (2026-09-26); [Search Operators (Web of Science)](https://webofscience.zendesk.com/hc/en-us/articles/20016122409105-Search-Operators) (2026-09-26); [Advanced Search Field Tags (Web of Science)](https://images.webofknowledge.com/images/help/WOS/hs_advanced_fieldtags.html) (2026-09-26)

**Sin ecuación:** la fuente quedó bloqueada. Resuelva los avisos bloqueantes y vuelva a generar las ecuaciones.

Avisos:

- bloqueante [B2, "freeze dr*"]: Web of Science no documenta el truncamiento dentro de una frase entre comillas, y lo no documentado se trata como no admitido. Agregue en busqueda.bloques[B2].variantes las variantes de '"freeze dr*"' que Web of Science debe buscar en su lugar
- bloqueante [B2, "fruto sec*"]: Web of Science no documenta el truncamiento dentro de una frase entre comillas, y lo no documentado se trata como no admitido. Agregue en busqueda.bloques[B2].variantes las variantes de '"fruto sec*"' que Web of Science debe buscar en su lugar
- advertencia [B2, liofilización]: Web of Science no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)
- advertencia: idiomas no reconocidos ('español'): van a la instrucción de la interfaz tal como están escritos. Use códigos ISO 639-1 (p. ej. es, en) para que salgan con el nombre en inglés que usa la base
- advertencia: tipos de documento no reconocidos ('poster'): van a la instrucción de la interfaz tal como están escritos, sin convertirlos. Tipos del vocabulario controlado (ADR-0009, punto 10): articulo, revision, conferencia, capitulo, libro, editorial, carta, nota

## La ecuación genérica

- Campos: los que la base busque por defecto; restrínjalos a título, resumen y palabras clave si la base lo permite
- Límites: aplíquelos con los filtros de la base (ver «Límites del protocolo»)
- Longitud: 164 caracteres, sin máximo documentado

```text
((zarambo OR "Zarambus fictus" OR by-product* OR post-extraction OR fru* OR "zarambina") AND (secado OR dehydrat* OR "freeze dr*" OR "fruto sec*" OR liofilización))
```

Avisos:

- advertencia [B1, by-product*]: cada base trata el * a su manera (largo mínimo de la raíz, frases con truncamiento): compruébelo en la documentación de la base
- advertencia [B1, fru*]: cada base trata el * a su manera (largo mínimo de la raíz, frases con truncamiento): compruébelo en la documentación de la base
- advertencia [B2, dehydrat*]: cada base trata el * a su manera (largo mínimo de la raíz, frases con truncamiento): compruébelo en la documentación de la base
- advertencia [B2, "freeze dr*"]: cada base trata el * a su manera (largo mínimo de la raíz, frases con truncamiento): compruébelo en la documentación de la base
- advertencia [B2, "fruto sec*"]: cada base trata el * a su manera (largo mínimo de la raíz, frases con truncamiento): compruébelo en la documentación de la base
- advertencia [B2, liofilización]: compruebe cómo trata la base las letras con tilde; si hace falta, agregue la forma sin tilde como término aparte

## Fuentes sin traductor

- lens: no tiene traductor propio; use la ecuación genérica y adáptela a la sintaxis de la base.
