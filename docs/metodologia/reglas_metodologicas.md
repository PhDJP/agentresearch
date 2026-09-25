# Reglas metodológicas del agente

Este documento es la fuente de verdad metodológica para implementar el agente. Las tablas se transcribieron y tradujeron de los originales, con su ubicación indicada. Ante cualquier duda, verificar contra el PDF en `referencias_locales/` (no versionado) y registrar la corrección en un commit `docs:`.

Referencias completas en [referencias.md](referencias.md).

## 1. Fases del proceso y correspondencia con PRISMA-ScR

| Fase (Kitchenham) | Actividad del agente | Módulo del paquete | Ítems PRISMA-ScR |
|---|---|---|---|
| Planificación | Justificación, preguntas, protocolo (PCC/PICOC, fuentes, ecuaciones, criterios, reglas de decisión, formulario de extracción) | `protocolo` | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 |
| Ejecución: identificación | Búsqueda en APIs, importación de exportaciones, búsqueda manual, bola de nieve, evaluación con conjunto de validación | `fuentes`, `importacion`, `bola_de_nieve` | 7, 8 |
| Ejecución: selección | Deduplicación, cribado por título y resumen, cribado de texto completo, conciliación | `deduplicacion`, `cribado`, `texto_completo` | 9, 14 |
| Ejecución: extracción | Extracción (*charting*), clasificación, evaluación de calidad opcional | `extraccion`, `calidad` | 10, 11, 12, 15, 16, 17 |
| Ejecución: análisis | Conteos por faceta, series temporales, mapas de burbujas y de calor | `analisis` | 13, 18 |
| Reporte | Diagrama de flujo, checklist, tabla de estudios, declaración de IA, amenazas a la validez | `reporte` | 1, 2, 14, 15, 19, 20, 21, 22 |

Los ítems 19 a 21 (discusión) los redacta el investigador; el agente le entrega los datos que los sustentan.

## 2. Protocolo: contenido mínimo

- Título, autores y versión del protocolo.
- Justificación y objetivos.
- Preguntas de investigación con ID (`PI1`, `PI2`, …) y, para cada una, qué datos de extracción la responden.
- Marco PCC con su equivalencia PICOC (tabla abajo).
- Fuentes con fechas de cobertura, ecuaciones de búsqueda por fuente y límites aplicados.
- Criterios de inclusión (`CI1`, …) y de exclusión (`CE1`, …). Cada criterio indica en qué fase se aplica (título y resumen, o texto completo) y trae ejemplos.
- Número de revisores, regla de combinación A–F y umbral de concordancia del piloto.
- Estrategias de identificación activas y criterio de parada.
- Formulario de extracción y esquema de clasificación (facetas, categorías, definiciones, ejemplos).
- Si se hace, evaluación de calidad con sus preguntas.
- Registro de enmiendas: fecha, cambio, justificación y efecto esperado.

### Equivalencia PCC ↔ PICOC

| PCC (JBI) | PICOC (Kitchenham) | Nota |
|---|---|---|
| Población | Population | Quién o qué se estudia (en el piloto: subproductos de la producción de CBD) |
| Concepto | Intervention y, si aplica, Outcome | El fenómeno de interés (en el piloto: la caracterización) |
| Contexto | Context | Ámbito, sector o condiciones |
| — | Comparison | Normalmente no aplica en mapeos |

Petersen et al. (2015, §5.1.2) recomiendan construir la búsqueda sobre todo con Población e Intervención. Comparación, resultado y contexto pueden restringir demasiado y dejar fuera artículos del área. Si la ecuación usa términos de contexto de forma restrictiva, el agente debe advertirlo.

### Tipos de criterio (Petersen et al., 2015, §5.1.2)

Los criterios pueden referirse a:

- (a) la relevancia temática;
- (b) el lugar de publicación;
- (c) el periodo;
- (d) requisitos de evaluación empírica;
- (e) el idioma.

En mapeos se debe evitar (d), para no perder tendencias recientes que aún no tienen evaluación.

## 3. Identificación de estudios

### Desarrollo de la búsqueda (Petersen et al., 2015, tabla 5 y §5.1.2)

Estrategias para construir las ecuaciones:

- PICO(C) o PCC;
- consultar a expertos o bibliotecarios;
- mejorar la búsqueda de forma iterativa;
- tomar palabras clave de artículos conocidos;
- usar tesauros, normas y enciclopedias. En el piloto se usa AGROVOC.

### Evaluación de la búsqueda

- **Conjunto de validación:** artículos conocidos, por ejemplo unos 10 aportados por un experto, que la búsqueda debe recuperar. El agente reporta la sensibilidad (recuperados / total del conjunto) y lista los no recuperados.
- **Otras estrategias posibles:** evaluación del resultado por un experto, revisión de las páginas de autores clave y *test–retest*.
- **Criterio de parada** (Petticrew y Roberts, citado en Petersen et al., 2015): detener la búsqueda cuando una estrategia complementaria añade menos de N artículos nuevos incluidos, o cuando se agota un presupuesto de tiempo definido. N y el presupuesto se fijan en el protocolo.

### Bola de nieve (Wohlin, 2014, §3)

1. **Conjunto inicial.** Toda búsqueda para formarlo produce un conjunto inicial *tentativo*. El conjunto inicial real está formado solo por los artículos que finalmente se incluyen. Un buen conjunto inicial:
   - cubre las distintas comunidades o grupos de artículos que podrían no citarse entre sí;
   - no es demasiado pequeño, y su tamaño depende de la amplitud del área;
   - es diverso en editoriales, años y autores;
   - se formula con las palabras clave de las preguntas y sus sinónimos.

   Una opción es partir de artículos seminales muy citados.
2. **Hacia atrás (referencias).**
   - Primero se descartan las referencias que no cumplen los criterios básicos (idioma, año, tipo de publicación) y las ya examinadas.
   - Después se evalúan el título, el lugar de publicación, los autores y el contexto en que se cita.
   - Si sigue siendo candidata, se lee el resumen y luego las partes relevantes del artículo hasta poder decidir.
3. **Hacia adelante (citas).** Se examinan los artículos que citan al artículo analizado, en este orden hasta poder decidir: la información de la fuente, el resumen, el lugar donde lo cita y, si hace falta, el texto completo.
4. **Inclusión definitiva antes de seguir.** Un artículo solo se usa para continuar la bola de nieve después de decidir su inclusión con el texto completo. Si no, se corre el riesgo de tener que deshacer inclusiones derivadas de él.
5. **Una iteración a la vez.** Los artículos nuevos de una iteración pasan a la siguiente, para mantener la trazabilidad.
6. **Fin.** El ciclo termina cuando una iteración no produce artículos nuevos. Opcionalmente se contacta a los autores más activos; si aportan artículos nuevos, el ciclo se reinicia.

El agente registra el origen de cada candidato: dirección (atrás o adelante), artículo de origen e iteración.

## 4. Selección

### Proceso (Ali y Petersen, 2014, figura 17 en Petersen et al., 2015)

1. Especificar los criterios en el protocolo.
2. Revisar los criterios entre los revisores.
3. Aplicar los criterios "en voz alta" (*think-aloud*) sobre uno o pocos registros para alinear la comprensión. En el agente, Claude y el investigador explican su razonamiento sobre los mismos registros de ejemplo, y las diferencias llevan a precisar los criterios.
4. Pilotear sobre un subconjunto y calcular la concordancia. Si no es aceptable, analizar los desacuerdos, actualizar los criterios y repetir. El umbral va en el protocolo; se sugiere kappa ≥ 0,61, nivel "sustancial" según Landis y Koch (1977).
5. Hacer la selección por título y resumen. Cada revisor marca **incluir**, **dudoso** o **excluir**.
6. Calcular la concordancia y aplicar las reglas de decisión.

En caso de duda, el registro pasa a lectura de texto completo (Petersen et al., 2015, §3.3).

### Reglas de decisión para dos revisores (Petersen et al., 2015, tabla 6, p. 12)

| R1 \ R2 | Incluir | Dudoso | Excluir |
|---|---|---|---|
| **Incluir** | A | B | D |
| **Dudoso** | B | C | E |
| **Excluir** | D | E | F |

- **Estrategia más inclusiva:** avanzan A, B, C, D y E, y solo se excluye F. En el estudio de Ali y Petersen encontró todos los estudios relevantes, con un 25 % más de sobrecarga que la estrategia A+B+C+D, que encontró el 94 %.
- **Por defecto en el agente:** la estrategia más inclusiva. El protocolo puede elegir otra combinación, con justificación.

### Texto completo

Cada exclusión en texto completo registra el criterio y el motivo, porque PRISMA-ScR (ítem 14) exige reportar los motivos de exclusión en cada etapa.

## 5. Extracción y clasificación

### Extracción (*charting*)

- El formulario vincula cada dato con una pregunta de investigación (ejemplo en Petersen et al., 2015, tabla 3).
- Un segundo revisor verifica la extracción contra el texto del artículo (Petersen et al., 2015, §3.4).
- El reporte describe el proceso y define cada variable (PRISMA-ScR, ítems 10 y 11).

### Facetas independientes del tema

Petersen et al. (2015, §5.1.3) recomiendan tres facetas:

- el lugar de publicación (tipo y nombre);
- el tipo de investigación;
- el método de investigación.

### Tipo de investigación: plantilla para ingeniería de software (Wieringa et al., 2006; Petersen et al., 2015, tabla 7, p. 13)

V = verdadero, F = falso, — = irrelevante o no aplica.

| Condición | R1 Evaluación | R2 Propuesta de solución | R3 Experiencia | R4 Validación | R5 Filosófico | R6 Opinión |
|---|---|---|---|---|---|---|
| Usado en la práctica | V | — | V | F | F | F |
| Solución novedosa | — | V | F | — | F | F |
| Evaluación empírica | V | F | F | V | F | F |
| Marco conceptual | — | — | — | — | V | F |
| Opinión sobre algo | F | F | F | F | F | V |
| Experiencia de los autores | — | — | V | — | F | F |

- La confusión más frecuente es entre validación y evaluación. En ambas hay evaluación empírica, pero la validación ocurre en laboratorio y la evaluación en un contexto real. Que la solución sea novedosa no es el criterio para distinguirlas.
- Una solución usada en la práctica pero sin evaluación empírica sigue siendo una propuesta de solución.

### Métodos de investigación (Petersen et al., 2015, figura 19)

- **Investigación de evaluación:** caso de estudio industrial, experimento controlado con profesionales, encuesta a profesionales, investigación-acción, etnografía.
- **Investigación de validación:** simulación, experimentos de laboratorio (con máquinas o personas), prototipado, análisis matemático y prueba de propiedades, caso de estudio académico (p. ej. con estudiantes).

Esta plantilla es de ingeniería de software. En ciencias agrarias, la distinción entre validación y evaluación podría equivaler a escala de laboratorio frente a escala piloto o industrial, pero debe definirse con el investigador.

### Facetas del tema

- **Preferir un esquema existente** cuando lo haya, porque favorece la comparación entre estudios.
- **Si no lo hay, un esquema emergente por *keywording*,** en un proceso similar a la codificación abierta:
  1. identificar palabras clave y conceptos en los resúmenes (o en la introducción y las conclusiones si el resumen no es claro);
  2. agruparlos en categorías y fusionarlas o renombrarlas;
  3. asignar cada artículo a sus categorías y contar.
- ***Card sorting*** (Christou et al., 2024) como técnica para construir el esquema de codificación.
- **Fiabilidad.** Wohlin et al. (2013) encontraron que dos mapeos independientes del mismo tema coincidieron solo en el 33 % de las clasificaciones de tipo de investigación. Por eso:
  - cada categoría lleva definición, regla de asignación y ejemplos;
  - se mide la concordancia en un piloto;
  - se permiten varias categorías cuando no son disjuntas.

Facetas candidatas para el caso piloto (propuesta, por definir con el investigador): tipo de subproducto, técnica de caracterización, propiedad o compuesto caracterizado, aplicación o valorización propuesta, escala del estudio y origen de la biomasa.

### Artículos y estudios (Kitchenham et al., 2011)

- Un artículo puede reportar varios estudios, y un estudio puede aparecer en varios artículos. El modelo de datos vincula ambos.
- El mapeo debe publicar todas las referencias con su clasificación individual. Si no, pierde valor para investigaciones posteriores.

## 6. Evaluación de calidad (opcional)

- PRISMA-ScR la deja opcional (ítems 12 y 16).
- Petersen et al. (2015) sugieren requisitos poco exigentes, por ejemplo verificar que haya información suficiente para la extracción.
- Si se hace, el protocolo define las preguntas, y el reporte explica el método y cómo se usaron los resultados.

## 7. Visualización (Petersen et al., 2015, §5.1.4)

- Gráficos de barras para frecuencias.
- Líneas para tendencias en el tiempo.
- Burbujas y mapas de calor para combinar dos facetas, por ejemplo tema por tipo de investigación.

## 8. Amenazas a la validez

Tipos (Petersen y Gencel, citado en Petersen et al., 2015, §3.6 y §5.1.5):

- **Validez descriptiva:** formularios de extracción mal diseñados.
- **Validez teórica:** sesgo de publicación, sesgo del investigador en la selección y la extracción, y calidad de la muestra frente a la población.
- **Generalizabilidad:** interna y externa.
- **Validez interpretativa:** sesgo en la interpretación de los datos.
- **Repetibilidad.**

Amenazas propias del uso de LLM, que el agente debe documentar:

- **No determinismo:** se mide la estabilidad sobre una muestra.
- **Cambio de versión del modelo:** se fija y registra el identificador exacto.
- **Sensibilidad al prompt:** los prompts están versionados.
- **Sesgo de automatización del revisor humano:** se mitiga con la revisión ciega.

## 9. Reporte

Estructura sugerida (Petersen et al., 2015, §5.3):

1. Introducción.
2. Trabajo relacionado: estudios secundarios y terciarios previos.
3. Método: preguntas, búsqueda, selección, extracción, análisis y clasificación, y validez.
4. Resultados, organizados por pregunta.
5. Discusión y conclusiones.
6. Apéndice con los estudios incluidos y los excluidos dudosos.

### Checklist PRISMA-ScR (Tricco et al., 2018): qué produce el agente

| Ítem | Sección | Qué exige (resumen) | Artefacto del agente |
|---|---|---|---|
| 1 | Título | Identificar el reporte como revisión de alcance o mapeo | Recordatorio en la plantilla del reporte |
| 2 | Resumen estructurado | Antecedentes, objetivos, elegibilidad, fuentes, *charting*, resultados y conclusiones | Borrador con cifras del estudio |
| 3 | Justificación | Por qué el enfoque de alcance o mapeo | Texto del protocolo |
| 4 | Objetivos | Preguntas con sus elementos (PCC) | Protocolo |
| 5 | Protocolo y registro | Si existe protocolo y dónde consultarlo | Enlace al protocolo versionado y DOI |
| 6 | Criterios de elegibilidad | Características, con justificación | Protocolo (criterios con IDs) |
| 7 | Fuentes | Bases, fechas de cobertura y fecha de la última búsqueda | Registro de búsquedas |
| 8 | Búsqueda | Estrategia completa de al menos una base, repetible | Ecuaciones exactas por fuente y sus límites |
| 9 | Selección | Proceso de cribado y elegibilidad | Descripción del proceso, reglas A–F y revisores |
| 10 | *Charting* | Método de extracción, calibración, independencia | Formulario y registro del piloto |
| 11 | Ítems de datos | Definición de cada variable | Diccionario de datos del formulario |
| 12 | Evaluación crítica (opcional) | Justificación y método | Módulo de calidad, si se usa |
| 13 | Síntesis | Cómo se resumen los datos | Plan de análisis del protocolo |
| 14 | Selección (resultados) | Números por etapa, motivos de exclusión, diagrama de flujo | Diagrama de flujo generado desde los datos |
| 15 | Características de las fuentes | Datos de cada fuente con su cita | Tabla completa de estudios |
| 16 | Evaluación crítica (resultados) | Si se hizo | Tabla de calidad |
| 17 | Resultados individuales | Datos extraídos de cada fuente | Tabla de extracción por estudio |
| 18 | Síntesis de resultados | Resumen en relación con las preguntas | Tablas y mapas por pregunta |
| 19 | Resumen de la evidencia | Conceptos, temas y tipos de evidencia | Datos de apoyo; redacta el investigador |
| 20 | Limitaciones | Limitaciones del proceso | Lista de amenazas y desviaciones del protocolo |
| 21 | Conclusiones | Interpretación e implicaciones | Redacta el investigador |
| 22 | Financiación | De las fuentes y del estudio | Campo del protocolo |

## 10. Declaración de uso de IA

El agente genera una sección que declara:

- herramienta y modelo exactos, con sus versiones;
- fases en que intervino el LLM y en qué rol (propuesta, revisor independiente, apoyo a la redacción);
- versiones de los prompts (hash);
- supervisión humana: quién tomó cada decisión final;
- concordancia entre el LLM y los revisores humanos;
- estabilidad medida sobre una muestra;
- limitaciones conocidas.

El marco es la declaración conjunta de Cochrane, Campbell, JBI y CEE (2025): los investigadores siguen siendo responsables de todo uso de IA y deben poder justificarlo como metodológicamente sólido.
