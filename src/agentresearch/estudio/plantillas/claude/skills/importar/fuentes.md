# Pasos manuales por base

Información consultada el 2026-09-29 en la documentación pública de cada base. **Todo máximo y toda ruta de menús está por verificar**: las interfaces cambian y los límites dependen de la plataforma y del contrato de la institución. Preséntalos siempre como «según la documentación consultada, por verificar» y pide al investigador que anote lo que ve.

## Qué exportar en cualquier base

- El **registro completo, con resumen**. Sin resumen, cada registro lleva la advertencia L-A04.
- Si la base tiene un máximo por exportación, **tandas** (por ejemplo, por año), cada una en un archivo.
- Guardar los archivos tal como los entrega la base, sin abrirlos ni modificarlos en Excel.

## Scopus

- **Formato:** RIS (`--formato ris`), BibTeX (`--formato bibtex`) o CSV de Scopus (`--formato scopus_csv`).
- **Qué marcar en la ventana de exportación:** en «Abstract & keywords», las casillas **Abstract**, **Author keywords** e **Indexed keywords** vienen **desmarcadas** por defecto (observado el 2026-10-20); sin marcarlas, la exportación no trae resumen ni palabras clave. Pide también la información de citación y bibliográfica (volumen, número, páginas, DOI, tipo de documento, idioma).
- **Máximo por exportación:** 20 000 elementos en CSV, RIS, BibTeX y texto plano, según el [Scopus Support Center](https://www.elsevier.support/scopus/answer/how-do-i-export-documents-from-scopus) (act. 2026-04-21). Por verificar. La ventana de exportación a texto plano mostró el mismo límite el 2026-10-20; para CSV, RIS y BibTeX no se observó. BibTeX no incluye «Funding Details» ni «Other Information».
- **Identificador de la fuente:** `scopus`.

## Web of Science

- **Formato:** texto plano de Web of Science (`--formato wos_txt`).
- **Contenido del registro:** en «Record Content», elige **Full Record** (verificado el 2026-10-20: trae resumen, tipo de documento, idioma y palabras clave). «Author, Title, Source» no trae resumen, y «Author, Title, Source, Abstract» trae el resumen pero no las palabras clave ni el tipo de documento. «Full Record and Cited References» agrega las referencias, que no se necesitan. En la ventana hay que marcar «Records from» y escribir el rango; la opción preseleccionada exporta solo lo marcado en la página.
- **Máximo por exportación:** la ventana de exportación decía «No more than 1000 records at a time» (2026-10-20). La documentación ([Clarivate](https://support.clarivate.com/ScientificandAcademicResearch/s/article/Web-of-Science-Limit-on-exporting?language=en_US), 2022-04-20) da 1 000 con el registro completo y 500 con las referencias citadas. Por verificar. La opción «Fast 5000» solo trae autor, título y fuente, sin resumen: no sirve para el cribado.
- Una exportación del registro 6 al 10 puede traer menos registros de los pedidos: comprueba el número de registros que informa `importar leer` y compáralo con el rango.
- **Identificador de la fuente:** `wos`.

## ACS

- **Rol:** búsquedas complementarias puntuales (ver el paso 7 de `SKILL.md`).
- **Formato:** RIS (`--formato ris`).
- **Máximo por exportación:** no documentado. Según la prueba del investigador (2026-10-20), ACS no permite descargas masivas ni extraer metadatos: **solo descarga individual**, un artículo a la vez. Cada artículo descargado es un archivo; varios archivos de una misma búsqueda se registran como tandas.
- **Qué trae su RIS** (verificado con un registro): volumen, número, páginas, resumen y DOI. Siempre trae tres líneas de cabecera antes del primer registro, y la lectura avisa L-A03: es esperable. Las palabras clave (`KW`), el PMID, el tipo de documento y el idioma no se han visto en ACS.
- **Identificador de la fuente:** `acs`. Su ecuación es genérica, sin traductor, con un aviso propio en `ecuaciones.md`: léelo con el investigador.

## Lens

- **Formato:** CSV con un archivo de mapeo (`--formato csv --mapeo <archivo>`; ejemplo para patentes en [formatos.md](formatos.md)). En la ventana de exportación se elige el formato, el número de documentos y las columnas.
- **Máximo por exportación:** 1 000 documentos sin iniciar sesión; para más hay que iniciar sesión (ventana de exportación, 2026-10-20). Por verificar para otros usos.
- Lens tiene dos índices, **artículos** y **patentes**, con columnas distintas: confirma en cuál se buscó. Su política de atribución pide citar a Lens cuando se usan sus datos.
- **Identificador de la fuente:** `lens`.

## Otras bases

Pregunta qué formatos ofrece. El agente lee RIS, BibTeX, el CSV de Scopus, el texto plano de Web of Science y un CSV genérico con un archivo de mapeo de columnas (ver [formatos.md](formatos.md)). La fuente debe estar declarada en el protocolo con `tipo: exportacion`.
