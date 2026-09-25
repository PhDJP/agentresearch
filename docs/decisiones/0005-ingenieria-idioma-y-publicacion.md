# ADR-0005: Ingeniería, idioma y publicación

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral y Claude (asesor)

## Contexto

El proyecto se desarrolla en Windows con VS Code y Claude Code, y debe poder instalarse y verificarse en otros equipos. El investigador ya tiene Git, cuenta de GitHub y Claude Code instalados.

## Decisión

1. **Entorno.** Python 3.12 gestionado con uv, con `uv.lock` versionado. No se usa el Python de Anaconda para este proyecto.
2. **Calidad.**
   - pytest para pruebas, ruff para estilo y mypy en modo estricto para tipos.
   - Integración continua en GitHub Actions sobre Windows y Ubuntu.
   - Versionado semántico, con un `CHANGELOG.md`.
3. **Repositorios.**
   - Uno para el agente, público desde el inicio, con licencia MIT.
   - Uno por cada estudio: fija la versión exacta del agente y guarda protocolo, búsquedas, registros, decisiones y reportes. Sus datos se publican con CC BY 4.0 y se archivan en Zenodo con DOI.
4. **Idioma.** Todo en español: código, documentación, mensajes y reportes. Los identificadores no llevan tildes ni ñ, para evitar problemas de codificación en Windows.
5. **Ubicación local.** `C:\Users\Felipe\Documents\Agentresearch`.
6. **Derechos de autor.** Los PDF de referencias con derechos de autor quedan en `referencias_locales/`, que Git ignora. Los PDF de texto completo de los estudios tampoco se versionan; se guarda su hash y su DOI.

## Alternativas consideradas

- **Conda o venv con pip:** uv da un bloqueo exacto de dependencias más simple y rápido.
- **Un solo repositorio:** mezclaría la herramienta con la evidencia de cada estudio.
- **Código en inglés:** se prefirió el español por decisión del investigador. Los reportes para revistas en inglés podrán requerir traducción, lo que se evaluará más adelante.
- **Repositorio privado hasta publicar:** se prefirió público para que el historial completo sea evidencia.

## Consecuencias

- Faltan datos del autor para `LICENSE` y `CITATION.cff`: nombre completo y ORCID. Se completan en el hito 0.
- Las dependencias deben tener licencias compatibles con MIT.
