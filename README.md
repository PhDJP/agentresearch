# Agentresearch

Agente investigador para estudios de mapeo sistemático de la literatura. Combina las guías de Kitchenham y de Petersen con el reporte PRISMA-ScR, y funciona con Claude Code y recursos gratuitos.

> **Estado:** en construcción (hito 0). Todavía no debe usarse en estudios reales.

## Para quién

Para investigadores que quieren hacer un mapeo sistemático riguroso sin pagar APIs de modelos de lenguaje. Basta con:

- una suscripción a Claude Code (plan Pro o superior);
- bases de datos abiertas (OpenAlex, PubMed, Semantic Scholar, Springer Nature, Crossref);
- las exportaciones que su institución permita (Scopus, Web of Science, ScienceDirect, etc.).

## Principios

- El agente propone y el investigador decide.
- Cada decisión queda registrada con su criterio, su evidencia textual y su autor (una persona o un modelo identificado).
- Todo lo determinista lo hace código probado; el modelo de lenguaje interviene solo donde hace falta juicio.
- Los reportes (diagrama de flujo y checklist PRISMA-ScR, declaración de uso de IA) se generan desde los datos, no a mano.

## Cómo funciona

1. El investigador abre su repositorio de estudio en VS Code con Claude Code.
2. El agente lo entrevista para construir el protocolo: preguntas, marco PCC (con equivalencia PICOC), ecuaciones de búsqueda y criterios. Cuando falta información, propone opciones fundamentadas.
3. El paquete `agentresearch` busca en las APIs abiertas, importa las exportaciones manuales (RIS, BibTeX, CSV, WoS), deduplica y guarda todo con su procedencia.
4. El cribado lo hacen de forma independiente el investigador (en una hoja Excel generada por el agente) y Claude (por lotes). Las decisiones se combinan con reglas explícitas y se mide la concordancia.
5. Siguen la bola de nieve, el texto completo, la extracción y la clasificación, el análisis y los mapas, y el reporte final.

Detalle en [docs/arquitectura.md](docs/arquitectura.md).

## Preparación del entorno (Windows)

1. Instalar Git y VS Code con la extensión Claude Code, e iniciar sesión con la cuenta del plan.
2. Instalar uv (gestor de entornos de Python):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. Recomendado: instalar GitHub CLI e iniciar sesión.
   ```powershell
   winget install --id GitHub.cli
   gh auth login
   ```
4. Cuando exista el código: `uv sync` para crear el entorno y `uv run pytest` para correr las pruebas.

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [Hoja de ruta](docs/hoja_de_ruta.md)
- [Reglas metodológicas](docs/metodologia/reglas_metodologicas.md)
- [Referencias](docs/metodologia/referencias.md)
- [Registro de decisiones (ADR)](docs/decisiones/README.md)

## Licencia y cita

El código se publicará con licencia MIT, y los datos y reportes de los estudios con CC BY 4.0. Los archivos `LICENSE` y `CITATION.cff` se agregan en el hito 0.
