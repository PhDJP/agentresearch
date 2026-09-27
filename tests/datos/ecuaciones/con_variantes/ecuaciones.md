# Ecuaciones de búsqueda

Generado por agentresearch a partir del protocolo; no lo edite a mano. Regenérelo con `agentresearch protocolo ecuaciones --escribir` después de aprobar o enmendar el protocolo (ADR-0009).

- Protocolo: protocolo/protocolo.yaml
- Versión del protocolo: 1.0.0 (vigente)
- Hash del protocolo: sha256:0000000000000000000000000000000000000000000000000000000000000000
- Versión del agente: 0.0.0-prueba
- Fuentes bloqueadas: ninguna

## Límites del protocolo

- Periodo: 2010 a 2025, ambos inclusive
- Idiomas: en (inglés), es (español)
- Tipos de documento: artículo, revisión

## OpenAlex

- Campos: título y resumen (title_and_abstract.search)
- Límites: se aplicarán con el conector de OpenAlex (hito 3)
- Longitud: 351 caracteres de URL codificada, de un máximo de 4096
- Sintaxis verificada en: [Search – Querying (OpenAlex Help Center)](https://help.openalex.org/api/searching/) (2026-09-26); [Searching guide (OpenAlex)](https://help.openalex.org/guides/searching) (2026-09-26)

```text
title_and_abstract.search:((zarambo OR "Zarambus fictus" OR by-product OR by-products OR post-extraction OR fruit OR fruits OR "zarambina") AND (secado OR dehydration OR dehydrated OR "freeze drying" OR "freeze dried" OR "fruto seco" OR "frutos secos" OR liofilización))
```

Avisos:

- nota [B1, by-product*]: la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos truncados tienen variantes; se usan sus variantes: by-product, by-products
- nota [B1, fru*]: la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos truncados tienen variantes; se usan sus variantes: fruit, fruits
- nota [B2, dehydrat*]: la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos truncados tienen variantes; se usan sus variantes: dehydration, dehydrated
- nota [B2, "freeze dr*"]: la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos truncados tienen variantes; se usan sus variantes: "freeze drying", "freeze dried"
- nota [B2, "fruto sec*"]: la búsqueda lematizada de OpenAlex no admite comodines, y todos los términos truncados tienen variantes; se usan sus variantes: "fruto seco", "frutos secos"
- advertencia [B2, liofilización]: OpenAlex no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)

## PubMed

- Campos: título y resumen ([tiab])
- Límites: se aplicarán con el conector de PubMed (hito 3)
- Longitud: 298 caracteres, sin máximo documentado
- Sintaxis verificada en: [PubMed User Guide](https://pubmed.ncbi.nlm.nih.gov/help/) (2026-09-26)

```text
((zarambo[tiab] OR "Zarambus fictus"[tiab] OR by-product*[tiab] OR post-extraction[tiab] OR fruit[tiab] OR fruits[tiab] OR "zarambina"[tiab]) AND (secado[tiab] OR dehydrat*[tiab] OR "freeze drying"[tiab] OR "freeze dried"[tiab] OR "fruto seco"[tiab] OR "frutos secos"[tiab] OR liofilización[tiab]))
```

Avisos:

- advertencia [B1, by-product*]: PubMed busca un término con guion como frase y, si no está en su índice de frases, no devuelve resultados; compruébelo en la interfaz o agregue la forma sin guion como frase aparte
- advertencia [B1, post-extraction]: PubMed busca un término con guion como frase y, si no está en su índice de frases, no devuelve resultados; compruébelo en la interfaz o agregue la forma sin guion como frase aparte
- nota [B1, fru*]: PubMed exige al menos 4 letras antes del *, y 'fru*' tiene una raíz más corta; se usan sus variantes: fruit, fruits
- nota [B2, "freeze dr*"]: PubMed exige al menos 4 letras antes del *, y '"freeze dr*"' tiene una raíz más corta; se usan sus variantes: "freeze drying", "freeze dried"
- nota [B2, "fruto sec*"]: PubMed exige al menos 4 letras antes del *, y '"fruto sec*"' tiene una raíz más corta; se usan sus variantes: "fruto seco", "frutos secos"
- advertencia [B2, liofilización]: PubMed no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)

## Scopus

- Campos: título, resumen y palabras clave (TITLE-ABS-KEY); las palabras clave incluyen las del autor, los términos indexados, los nombres comerciales y los nombres químicos
- Límites: en la ecuación (PUBYEAR > 2009 AND PUBYEAR < 2026 AND (LANGUAGE(english) OR LANGUAGE(spanish)) AND (DOCTYPE(ar) OR DOCTYPE(re)))
- Longitud: 314 caracteres, sin máximo documentado
- Sintaxis verificada en: [Scopus Search Tips (Elsevier Developer Portal)](https://dev.elsevier.com/sc_search_tips.html) (2026-09-26); [How can I best use the Advanced search? (Scopus)](https://www.elsevier.support/scopus/answer/how-can-i-best-use-the-advanced-search) (2026-09-26)

```text
TITLE-ABS-KEY((zarambo OR "Zarambus fictus" OR by-product* OR post-extraction OR fru* OR "zarambina") AND (secado OR dehydrat* OR "freeze drying" OR "freeze dried" OR "fruto sec*" OR liofilización)) AND PUBYEAR > 2009 AND PUBYEAR < 2026 AND (LANGUAGE(english) OR LANGUAGE(spanish)) AND (DOCTYPE(ar) OR DOCTYPE(re))
```

Avisos:

- nota [B2, "freeze dr*"]: Scopus exige al menos 3 letras antes del *, y '"freeze dr*"' tiene una raíz más corta; se usan sus variantes: "freeze drying", "freeze dried"
- advertencia [B2, liofilización]: Scopus no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)

Pasos para ejecutarla:

1. Abra la búsqueda avanzada de documentos de Scopus y pegue la ecuación completa.
2. No hace falta aplicar filtros en la interfaz: los límites están en la ecuación.
3. Exporte todos los resultados en CSV, con todos los campos disponibles (incluidos el resumen y las palabras clave). Es el formato que importará el hito 2 (ADR-0003).
4. Anote la fecha y la hora de la búsqueda y el número de resultados que mostró la interfaz: el hito 2 los pedirá al importar la exportación (PRISMA-ScR, ítem 7).

## Web of Science

- Campos: título, resumen, palabras clave de autor y Keywords Plus (TS)
- Límites: en la ecuación (PY=(2010-2025)); en la interfaz (ver los pasos)
- Longitud: 225 caracteres, sin máximo documentado
- Sintaxis verificada en: [Search Rules (Web of Science)](https://webofscience.zendesk.com/hc/en-us/articles/25350084904721-Search-Rules) (2026-09-26); [Web of Science Core Collection Search Fields](https://webofscience.zendesk.com/hc/en-us/articles/26916258216209-Web-of-Science-Core-Collection-Search-Fields) (2026-09-26); [Search Operators (Web of Science)](https://webofscience.zendesk.com/hc/en-us/articles/20016122409105-Search-Operators) (2026-09-26); [Advanced Search Field Tags (Web of Science)](https://images.webofknowledge.com/images/help/WOS/hs_advanced_fieldtags.html) (2026-09-26)

```text
TS=((zarambo OR "Zarambus fictus" OR by-product* OR post-extraction OR fru* OR "zarambina") AND (secado OR dehydrat* OR "freeze drying" OR "freeze dried" OR "fruto seco" OR "frutos secos" OR liofilización)) AND PY=(2010-2025)
```

Avisos:

- nota [B2, "freeze dr*"]: Web of Science no documenta el truncamiento dentro de una frase entre comillas, y lo no documentado se trata como no admitido; se usan sus variantes: "freeze drying", "freeze dried"
- nota [B2, "fruto sec*"]: Web of Science no documenta el truncamiento dentro de una frase entre comillas, y lo no documentado se trata como no admitido; se usan sus variantes: "fruto seco", "frutos secos"
- advertencia [B2, liofilización]: Web of Science no documenta cómo trata las letras con tilde o fuera de ASCII; si quiere recuperar también la forma sin tilde, agréguela como término aparte (ADR-0009, punto 8)
- nota: la ayuda de Web of Science recomienda intervalos de 5 años o menos en PY=, porque los más largos hacen lenta la búsqueda; si ocurre, quite PY= de la ecuación y ajuste los años de publicación en la interfaz

Pasos para ejecutarla:

1. Abra la búsqueda avanzada de la Web of Science Core Collection y pegue la ecuación completa en el cuadro que admite etiquetas de campo (TS=).
2. Aplique en la interfaz estos filtros:
   - Idioma: en los resultados, filtre por idioma (Languages) a English, Spanish.
   - Tipo de documento: en los resultados, filtre por tipo (Document Types) a Article, Review (un registro puede tener dos tipos, p. ej. Article y Proceedings Paper).
3. Exporte todos los resultados como texto plano con etiquetas (.txt), con el registro completo. Es el formato que importará el hito 2 (ADR-0003).
4. Anote la fecha y la hora de la búsqueda y el número de resultados que mostró la interfaz: el hito 2 los pedirá al importar la exportación (PRISMA-ScR, ítem 7).

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
