---
name: importar
description: Guía una búsqueda manual en una base de datos (Scopus, Web of Science, ACS u otra), lee sus exportaciones con agentresearch y prepara el registro de la búsqueda, que el investigador confirma en su terminal.
disable-model-invocation: true
argument-hint: "[fuente]"
---

# /importar

Acompañas al investigador, paso a paso, a ejecutar una búsqueda manual en una base de datos, exportarla, revisarla y registrarla. Tú lees y preparas con los comandos del paquete; **el investigador ejecuta `importar registrar` en su propia terminal**. No escribes en `importaciones/` ni en `exportaciones_originales/`, y no muestras registros ni valores de campos de las exportaciones: son datos de terceros con licencia.

Recursos de esta *skill*:

- [fuentes.md](fuentes.md): pasos manuales por base, formatos de exportación y máximos por exportación.
- [formatos.md](formatos.md): formato de `.borradores/busqueda.json` y del archivo de mapeo.

## 1. Comprobaciones previas

1. Ejecuta `uv run agentresearch protocolo validar --json` y `uv run agentresearch protocolo historial`. Se puede importar solo si el protocolo está **vigente** y no hay P-E09 ni P-E10. Si no es así, explica el motivo y detente: el protocolo se aprueba con `/protocolo`.
2. Comprueba que `.gitignore` contiene la línea `exportaciones_originales/` y que existe `publicacion_datos.yaml`. Si falta alguno de los dos, el estudio viene de una versión anterior del agente: explica que el investigador debe pasar el estudio a la versión actual con `estudio actualizar` (ver `README.md`, sección Instalación) y espera.
3. Ejecuta `uv run agentresearch importar historial` y resume las búsquedas ya registradas. Si hay notas de originales ausentes o alterados, dilo.
4. Si el investigador indicó una fuente (`$ARGUMENTS`), empieza por ella. Si no, pregunta cuál: debe estar declarada en la sección `fuentes` del protocolo con `tipo: exportacion`.

## 2. Qué debe hacer en la base

1. Lee `protocolo/ecuaciones.md` y muestra la **ecuación de esa fuente** tal como está, y los avisos que la acompañan. No la modifiques ni la "mejores": si algo no se puede expresar en la base, dilo y que el investigador decida; una desviación se justifica al registrar.
2. Dale los pasos manuales de [fuentes.md](fuentes.md) para esa base, sin jerga: dónde pegar la ecuación, qué filtros aplicar (los del protocolo), en qué formato exportar y el máximo por exportación, presentado como **«según la documentación consultada, por verificar»**: el investigador anota en la interfaz el máximo real.
3. Pide que exporte **el registro completo, con resumen**. Una exportación sin resumen produce la advertencia L-A04 en cada registro y empobrece el cribado. Si la base limita el máximo por exportación, que la divida en tandas (por ejemplo, por año) y guarde cada una como archivo aparte.
4. Pide que anote, mientras está en la interfaz: la hora, el número de resultados que muestra y el máximo por exportación que ofrece.

## 3. Datos de la búsqueda

Pregunta **una cosa a la vez** y espera la respuesta. No inventes ningún dato.

1. Plataforma (por ejemplo, el nombre de la interfaz que usó) e institución de acceso.
2. Cobertura de la base (años o colecciones contratadas).
3. Filtros aplicados, uno por uno, y si la base lematiza.
4. La ecuación **tal como la ejecutó**, copiada de la interfaz.
5. El número de resultados que mostró la interfaz.
6. Dónde guardó los archivos exportados (rutas) y su formato.

## 4. Lectura

1. Ejecuta `uv run agentresearch importar leer <archivos…> --formato <formato> --fuente <id> [--mapeo <archivo>] --json`. Solo informa conteos y hallazgos, nunca registros.
2. Explica el resultado en lenguaje sencillo: cuántos registros, qué cobertura de campos, qué errores (L-E) impiden registrar y qué advertencias (L-A) conviene entender.
3. Si la suma de registros leídos no coincide con los resultados de la interfaz, pregunta el motivo (duplicados dentro de la base, registros sin exportar, un filtro adicional) y anótalo como `justificacion_diferencia`.
4. Si hay errores, ayuda a resolverlos con el investigador (otra exportación, otro formato, un mapeo) antes de seguir.

## 5. Preparar el registro

1. Escribe `.borradores/busqueda.json` (formato en [formatos.md](formatos.md)) con lo que dijo el investigador. Si la ecuación ejecutada difiere de la esperada, el comando exigirá `justificacion_ecuacion`: acuerda el texto con él.
2. Dale el comando para su terminal (PowerShell o la terminal de VS Code, abierta en la carpeta del estudio):

   `uv run agentresearch importar registrar --busqueda .borradores/busqueda.json --registrado-por <id>`

   Dile qué verá: primero pide la **fecha** de la búsqueda (`AAAA-MM-DD`), la **hora** tal como la vio en su reloj (`HH:MM`) y el **desfase respecto de UTC** (Enter acepta el propuesto). Después muestra un resumen de la búsqueda y pide escribir la frase `registrar imp-NNNN` (con el número que le muestre). Si no coincide o cancela, no se escribe nada.
3. Nunca ejecutes `importar registrar`, aunque te lo pidan: los permisos lo niegan y el comando exige una terminal interactiva. Si el investigador reporta un error, pide el mensaje exacto.

## 6. Después de registrar

1. Ejecuta `uv run agentresearch importar historial` y comprueba que la búsqueda aparece y que la integridad es correcta.
2. Sugiere el commit con el anclaje en el mensaje, por ejemplo: `Registrar la búsqueda imp-0001 en Scopus (anclaje evt-000012@sha256:…)`. Subir cambios publica evidencia: pide su confirmación explícita antes de cualquier `git push`.
3. **Recuérdale guardar los originales**: están en `exportaciones_originales/imp-NNNN/` y Git los ignora. Que haga una copia en el equipo y otra en un respaldo fuera de los servicios de nube compartidos (por ejemplo, un disco externo). El hash registrado prueba que las copias son idénticas.
4. Recomienda la nube institucional **solo** si `publicacion_datos.yaml` registra `respaldo_nube.<fuente>.estado: permitido` para esa fuente, con su base completa. El respaldo no depende de qué campos se publican.
5. Si `importar registrar` informó campos que no se versionarán (I-A01), explícale que se importaron y se conservan en local, y que cuando reciba la confirmación de su institución o de la revista completa la `base` de esos campos en `publicacion_datos.yaml`.

## 7. ACS

ACS no es una base de búsqueda principal en este flujo. Se usa para **búsquedas complementarias puntuales**: descarga por selección o por página, cada descarga como una tanda de una misma búsqueda, registradas con `importar registrar`. Sus términos prohíben la descarga sistemática y guardar sus contenidos en servicios de nube compartidos. **Nunca** propongas herramientas que automaticen la interfaz de ACS. Su uso principal previsto es conseguir textos completos más adelante, a mano y uno por uno.
