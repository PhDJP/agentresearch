# Pasos manuales por base

Información consultada el 2026-09-29 en la documentación pública de cada base. **Todo máximo y toda ruta de menús está por verificar**: las interfaces cambian y los límites dependen de la plataforma y del contrato de la institución. Preséntalos siempre como «según la documentación consultada, por verificar» y pide al investigador que anote lo que ve.

## Qué exportar en cualquier base

- El **registro completo, con resumen**. Sin resumen, cada registro lleva la advertencia L-A04.
- Si la base tiene un máximo por exportación, **tandas** (por ejemplo, por año), cada una en un archivo.
- Guardar los archivos tal como los entrega la base, sin abrirlos ni modificarlos en Excel.

## Scopus

- **Formato:** RIS (`--formato ris`), BibTeX (`--formato bibtex`) o CSV de Scopus (`--formato scopus_csv`). Con el CSV, marcar todos los campos de información bibliográfica y el resumen.
- **Máximo por exportación:** 20 000 elementos en CSV, RIS, BibTeX y texto plano, según el [Scopus Support Center](https://www.elsevier.support/scopus/answer/how-do-i-export-documents-from-scopus) (act. 2026-04-21). Por verificar. BibTeX no incluye «Funding Details» ni «Other Information».
- **Identificador de la fuente:** `scopus`.

## Web of Science

- **Formato:** texto plano de Web of Science (`--formato wos_txt`) con el **registro completo**.
- **Máximo por exportación:** 1 000 registros con el registro completo y 500 con las referencias citadas, según [Clarivate](https://support.clarivate.com/ScientificandAcademicResearch/s/article/Web-of-Science-Limit-on-exporting?language=en_US) (2022-04-20). Por verificar. La opción «Fast 5000» solo trae autor, título y fuente, sin resumen: no sirve para el cribado.
- La exportación de prueba del 2026-10-13 no traía resumen. La opción de la interfaz que lo incluye está por confirmar: pide al investigador que verifique que el archivo lo trae antes de seguir.
- **Identificador de la fuente:** `wos`.

## ACS

- **Rol:** búsquedas complementarias puntuales (ver el paso 7 de `SKILL.md`).
- **Formato:** RIS (`--formato ris`).
- **Máximo por exportación:** no documentado. Según la prueba del investigador, no hay descarga masiva desde los resultados: se descarga por selección o por página y cada descarga es una tanda.
- **Identificador de la fuente:** `acs`. Su ecuación es genérica, sin traductor, con un aviso propio en `ecuaciones.md`: léelo con el investigador.

## Otras bases (por ejemplo, Lens)

Pregunta qué formatos ofrece. El agente lee RIS, BibTeX, el CSV de Scopus, el texto plano de Web of Science y un CSV genérico con un archivo de mapeo de columnas (ver [formatos.md](formatos.md)). La fuente debe estar declarada en el protocolo con `tipo: exportacion`.
