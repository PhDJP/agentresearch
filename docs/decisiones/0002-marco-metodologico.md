# ADR-0002: Marco metodológico: Kitchenham, Petersen y PRISMA-ScR

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral y Claude (asesor)

## Contexto

El agente debe servir para publicaciones doctorales, así que su proceso tiene que ser defendible ante evaluadores. Los documentos de contexto del investigador (ver `docs/metodologia/referencias.md`) muestran que:

- los mapeos sistemáticos combinan varias guías, porque ninguna cubre todo el proceso (Petersen et al., 2015);
- PRISMA-ScR es la guía de reporte aplicable a mapeos (Kitchenham et al., 2023, SEGRESS);
- el área del caso piloto es ciencias agrarias y agroindustriales.

## Decisión

1. **Proceso.** Kitchenham (planificación, ejecución, reporte) con las actualizaciones de Petersen et al. (2015) para el mapeo. El reporte sigue PRISMA-ScR (Tricco et al., 2018).
2. **Marco de la pregunta.** PCC (Población, Concepto, Contexto; JBI), con una equivalencia explícita a PICOC de Kitchenham. Ambas quedan en el protocolo.
3. **Estrategias de identificación.** Las cuatro, configurables por estudio:
   - búsqueda en bases de datos;
   - bola de nieve hacia atrás y hacia adelante (Wohlin, 2014);
   - búsqueda manual;
   - conjunto de validación de artículos conocidos para evaluar la búsqueda.
4. **Revisores.** El número es configurable, con un mínimo de investigador más LLM revisando de forma independiente y ciega. Las decisiones se combinan con las reglas A–F de Petersen et al. (2015). Antes del cribado completo hay un piloto con medición de concordancia (kappa de Cohen). Un segundo humano puede sumarse al piloto y a una muestra.
5. **Evaluación de calidad de los estudios primarios.** Opcional (ítems 12 y 16 de PRISMA-ScR). Si se usa, se registra y se reporta.
6. **Clasificación.**
   - Las facetas son configurables por plantillas de área.
   - En ingeniería de software se usa la tabla de tipos de investigación de Wieringa, en la versión de Petersen et al. (2015).
   - En ciencias agrarias predomina el esquema temático emergente (*keywording*), apoyado en *card sorting* (Christou et al., 2024) y en AGROVOC.
7. **Productos de reporte en la versión 1:**
   - checklist PRISMA-ScR con la ubicación de cada ítem;
   - diagrama de flujo generado desde los datos;
   - declaración de uso de IA, alineada con la declaración conjunta de Cochrane, Campbell, JBI y CEE (2025) y las recomendaciones RAISE;
   - tabla completa de estudios incluidos con su clasificación individual.

## Alternativas consideradas

- **Solo PCC o marco configurable (PICO, SPIDER):** se prefirió PCC con puente a PICOC para cumplir ambas tradiciones sin complicar el protocolo.
- **ROSES, tabla SEGRESS y rúbrica de Petersen como productos de reporte:** no se incluyen en la versión 1. Pueden añadirse con un ADR nuevo si una revista los exige.

## Consecuencias

- Cada fase del agente se corresponde con una fase de Kitchenham y con ítems concretos de PRISMA-ScR (tabla en `docs/metodologia/reglas_metodologicas.md`).
- La tabla de Wieringa es específica de ingeniería de software. Para el caso piloto hay que diseñar facetas propias del área (p. ej. tipo de subproducto, técnica de caracterización, escala), con definiciones y ejemplos, para evitar la baja fiabilidad de clasificación reportada por Wohlin et al. (2013).
