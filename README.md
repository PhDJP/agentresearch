# Agentresearch

Agente investigador para estudios de mapeo sistemático de la literatura. Combina las guías de Kitchenham y de Petersen con el reporte PRISMA-ScR, y funciona con Claude Code y recursos gratuitos.

> **Estado:** en construcción. El hito 0 (base técnica, versión 0.0.1) está completo. Las funciones de mapeo se incorporan hito a hito, y cada una se valida en un estudio real (el caso piloto) antes de darse por terminada. Mientras tanto, solo debe usarse lo que aparece en "Disponible hoy". Ver la [hoja de ruta](docs/hoja_de_ruta.md).

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

## Disponible hoy

- CLI: `uv run agentresearch --version`.
- Verificación de un registro encadenado de eventos: `uv run agentresearch registro verificar <archivo.jsonl>`.
- Validación de un protocolo en YAML contra su esquema y las reglas metodológicas (errores P-E00 a P-E08 y advertencias P-A01 a P-A08): `uv run agentresearch protocolo validar [ruta] [--json]`. La plantilla comentada del protocolo viene en el paquete.
- Pruebas, estilo (ruff) y tipos (mypy estricto), verificados en integración continua sobre Windows y Ubuntu.
- Documentación metodológica, de arquitectura y de decisiones (ADR).

## Cómo funcionará (diseño en construcción)

Este es el flujo previsto. Cada paso estará disponible cuando se cierre su hito.

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
4. Clonar el repositorio y ejecutar `uv sync` para crear el entorno.
5. Ejecutar siempre los comandos con `uv run` (por ejemplo `uv run agentresearch --version` o `uv run pytest`). Así se usa el entorno del proyecto con el paquete instalado; ejecutar los archivos de Python directamente no está soportado.

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [Hoja de ruta](docs/hoja_de_ruta.md)
- [Reglas metodológicas](docs/metodologia/reglas_metodologicas.md)
- [Referencias](docs/metodologia/referencias.md)
- [Registro de decisiones (ADR)](docs/decisiones/README.md)

## Licencia y cita

El código se publica con licencia MIT ([LICENSE](LICENSE)), y los datos y reportes de los estudios con CC BY 4.0. Para citar el software, ver [CITATION.cff](CITATION.cff).
