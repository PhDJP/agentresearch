# Especificación del hito 2: registros e importación

- **Estado:** propuesta de Claude Code (2026-09-29), con las decisiones del investigador y del asesor. Se revisa con el asesor antes de programar, y cada sub-hito se revisa antes de implementarlo.
- **Relación con otros documentos:** desarrolla el hito 2 de la [hoja de ruta](../hoja_de_ruta.md) y su nota, y se apoya en el [ADR-0010](../decisiones/0010-registros-importacion-y-datos-de-terceros.md) (propuesta). Si algo aquí contradice un ADR aceptado, prevalece el ADR y se corrige este documento.

## Objetivo

Al terminar el hito 2, un investigador puede:

1. exportar a mano una búsqueda de Scopus, Web of Science u otra base sin API, en uno o varios archivos;
2. comprobar con el agente que los archivos se leen bien y cuántos registros tienen, sin registrar nada;
3. registrar la búsqueda en su terminal, con la ecuación, la fecha y hora, los filtros, la cobertura de su acceso institucional y el número de resultados de la interfaz;
4. obtener registros normalizados con procedencia, de los que se versionan solo los campos que permite la licencia de la fuente;
5. consultar los conteos por fuente que alimentan el diagrama de flujo (PRISMA-ScR, ítem 14).

La aceptación se hace en dos partes: exportaciones reales de prueba, que en el repositorio del agente solo se leen, y las búsquedas reales del estudio de demostración `demo-mucilago-cafe`, que sí se registran (hoja de ruta, «Estrategia de validación»).

## Sub-hitos

Una rama y un PR por sub-hito. Cada uno termina con pruebas en verde y un resumen para la revisión del asesor.

| Sub-hito | Contenido | Esfuerzo sugerido en Claude Code |
|---|---|---|
| 2a | ADR-0010 y esta especificación (PR solo de documentos); después, el módulo `registros` | Alto |
| 2b | Lectores y `importar leer` | Alto |
| 2c | `importar registrar`, evento, hash, conteos por fuente, `importar historial` y el aviso de ACS en `ecuaciones.md` | Alto |
| 2d | Plantillas del estudio: `/importar`, permisos, `CLAUDE.md` y `.gitignore` | Medio |
| 2e | Aceptación y cierre de `v0.2.0` | Medio |

Al cerrar 2e se etiqueta `v0.2.0`.

## Reglas comunes

- Solo se registra con el protocolo vigente, sin P-E09 ni P-E10, y con la fuente declarada en `fuentes` con `tipo: exportacion` (ADR-0010, punto 11).
- Ningún registro se inventa ni se corrige a mano (CLAUDE.md, regla 6). Las únicas transformaciones son las normalizaciones deterministas del punto 22 del ADR-0010.
- Las pruebas usan archivos sintéticos escritos para ellas, con temas ficticios. Nunca contienen datos del caso piloto ni texto copiado de una exportación real.
- Las exportaciones reales de prueba nunca entran a este repositorio: van en `exportaciones_prueba_local/`, que se agrega al `.gitignore` del agente en el 2b.
- Todos los comandos nuevos admiten `--json`, con la forma común del ADR-0008 (punto 26): código 0 si la operación se completa, 1 si se rechaza o se cancela y 2 si los argumentos no son válidos.

## 2a. Módulo `registros`

**Módulo `agentresearch.registros`.** Sin dependencias nuevas.

### Registro normalizado

Un registro es lo que devuelve una fuente para un documento. Esquema pydantic estricto (`extra="forbid"`):

| Campo | Contenido | Publicable |
|---|---|---|
| `id` | `imp-NNNN-NNNNN`: importación y posición en la búsqueda (orden de los archivos declarado y, dentro de cada archivo, orden de lectura) | siempre |
| `id_importacion` | `imp-NNNN` | siempre |
| `fuente` | ID de la fuente en el protocolo (`scopus`, `wos`, `acs`, …) | siempre |
| `formato` | `ris`, `bibtex`, `scopus_csv`, `wos_txt` o `csv` | siempre |
| `archivo` y `posicion` | nombre del archivo original y línea (RIS, WoS, BibTeX) o fila (CSV) donde empieza el registro | siempre |
| `tipo_id_fuente` y `id_fuente` | `eid`, `ut`, `doi`, `pmid`, `lens_id` o `ninguno`, y su valor | según la política |
| `titulo` | texto | según la política |
| `autores` | lista, en el orden de la fuente | según la política |
| `anio` | entero o nulo | según la política |
| `fuente_publicacion` | revista, libro, congreso u oficina de patentes | según la política |
| `volumen`, `numero`, `paginas` | texto o nulo | según la política |
| `doi` | normalizado o nulo | según la política |
| `pmid` | texto o nulo | según la política |
| `tipo_documento`, `idioma` | el texto de la fuente, sin traducir | según la política |
| `resumen`, `palabras_clave_autor`, `palabras_clave_indexadas` | texto o lista | nunca |
| `otros` | `{etiqueta o columna: valor}` para los campos leídos sin campo propio, sin los volátiles | nunca |
| `hash_completo` | SHA-256 del registro completo normalizado (abajo) | siempre |

- **Patentes y tesis.** No se exigen DOI ni `fuente_publicacion` (ADR-0010, punto 22).
- **Normalización.** Espacios recortados y colapsados, Unicode NFC y DOI extraído de cualquier URL o prefijo (`https://doi.org/`, `doi:`, el proxy de la biblioteca), con la forma `10.…` en minúsculas ASCII (DOI Handbook, §2.4). Las tildes de LaTeX se decodifican en el lector de BibTeX (2b).
- **`hash_completo`** se calcula sobre el JSON canónico (ADR-0006, punto 2) de los campos bibliográficos, desde `tipo_id_fuente` hasta `otros`. No incluye `id`, `id_importacion`, `archivo` ni `posicion`, que cambian entre descargas, ni campos volátiles, que nunca entran a `otros`. Así, el mismo registro descargado dos veces tiene el mismo hash (ADR-0010, punto 20).

### Artículo y estudio (provisionales)

- `Articulo` y `Estudio`, con la relación de muchos a muchos `VinculoArticuloEstudio`. Se definen con los campos mínimos (ID y vínculos) y quedan marcados en su docstring como **provisionales**: el hito 4 asocia registros a artículos y el hito 8, artículos a estudios.
- El registro no se fusiona ni se modifica al asociarlo: la deduplicación del hito 4 crea artículos que lo referencian.

### Política de datos

- **`agentresearch/registros/politica_datos.yaml`,** validada con pydantic al cargarla:

  ```yaml
  version: 1
  fuentes:
    por_omision:
      campos:
        titulo: confirmado
        autores: confirmado
        doi: confirmado
        fuente_publicacion: confirmado
    scopus:
      campos:
        titulo: confirmado
        autores: confirmado
        doi: confirmado
        fuente_publicacion: confirmado
        anio: pendiente
        volumen: pendiente
        numero: pendiente
        paginas: pendiente
        tipo_documento: pendiente
        idioma: pendiente
        id_fuente: pendiente     # EID
    # wos (UT), acs (el ID de la fuente es el DOI) y lens con la misma forma
  ```

- `campos_publicables(fuente)` y `tiene_pendientes(fuente)`. Una fuente sin entrada usa `por_omision`. Un campo ausente no se publica.
- `hash_politica()`: el SHA-256 del archivo, que registra cada importación.
- `registro_publicable(registro, politica)`: el registro con solo los campos publicables y los que se publican siempre.

### Archivos

- `escribir_registros_jsonl(registros)`: una línea de JSON canónico por registro publicable, en UTF-8 con LF.
- `escribir_vista_csv(registros)`: `registros.csv` derivado de `registros.jsonl`, con columnas fijas en el orden del esquema, `autores` unidos por `; `, UTF-8 sin BOM y LF. Es determinista: el mismo JSONL da los mismos bytes.

### Pruebas

- Esquema: campos desconocidos rechazados; registro sin DOI ni revista (patente, tesis) aceptado.
- DOI: extracción desde URL, `doi:` y el proxy; minúsculas solo en ASCII; texto sin DOI → nulo.
- `hash_completo`: igual con otro `id`, `archivo` o `posicion`; distinto si cambia un campo bibliográfico.
- Política: un campo `pendiente` se detecta; un campo ausente no se publica; el resumen y las palabras clave nunca se publican aunque la tabla los liste por error (se rechaza al cargar).
- JSONL y CSV: bytes idénticos en ejecuciones repetidas y en Windows y Ubuntu; caracteres no ASCII sin escapar.

## 2b. Lectores y `importar leer`

**Módulo `agentresearch.importacion`.**

**Dependencias nuevas:** `bibtexparser==2.0.1` y `pylatexenc==2.11`, con la versión exacta fijada y justificadas en el commit (ADR-0010, punto 24).

### Interfaz común

`leer(ruta, formato, fuente, mapeo=None) -> ResultadoLectura`, con:

- los registros completos normalizados;
- los hallazgos: ID de regla, severidad, mensaje y número de línea;
- las líneas de cabecera anteriores al primer registro;
- el hash del archivo y el número de registros;
- la cobertura de cada campo: cuántos registros lo tienen.

El formato lo declara el investigador; el lector no lo adivina.

### Formatos

| Formato | Lector | Notas |
|---|---|---|
| `ris` | propio | Etiquetas de dos caracteres, `TY` abre y `ER` cierra. Tolera líneas de cabecera antes del primer `TY` (RIS de ACS) y líneas de continuación. |
| `wos_txt` | propio | Texto plano con etiquetas de Web of Science: `FN` y `VR` de cabecera, `ER` fin de registro, `EF` fin de archivo, continuación con tres espacios. |
| `scopus_csv` | propio, con `csv` | Columnas leídas por nombre; celdas entre comillas con saltos de línea. |
| `csv` | propio, con `csv` | Un archivo de mapeo JSON (`{"columna": "campo"}`) declara qué columna va a cada campo; se valida y su hash queda en el resultado. Cubre Lens. |
| `bibtex` | bibtexparser 2.0.1 | Tildes de LaTeX decodificadas con pylatexenc; `@string` y concatenaciones resueltas por la biblioteca. |

- **Correspondencia de campos.** Cada lector lleva una tabla de etiquetas o columnas a campos del esquema, con la URL de la documentación oficial y la fecha de verificación:
  - Web of Science: la [lista oficial de etiquetas](https://support.clarivate.com/ScientificandAcademicResearch/s/article/Web-of-Science-Core-Collection-List-of-field-tags-in-output?language=en_US) (`TI`, `AU`, `SO`, `PY`, `VL`, `IS`, `BP`, `EP`, `AR`, `DI`, `PM`, `UT`, `DT`, `LA`, …);
  - Scopus: la página oficial de los campos que exporta, que se consulta al implementar;
  - RIS: la especificación RIS y el RIS de ACS observado el 2026-09-29.

  Lo que no se pueda verificar en la documentación se confirma con las exportaciones de prueba del 2e antes de cerrar.
- **Campos volátiles.** Cada tabla declara los campos que se descartan porque cambian en cada descarga y no describen el documento: `Y2` en el RIS de ACS (fecha de descarga), la fecha de generación del archivo en Web of Science, y los que revelen las exportaciones de prueba.
- **Codificación.** UTF-8, con o sin BOM. Cualquier otra se rechaza con la línea del primer byte inválido. Fin de línea LF o CRLF.

### Reglas de lectura

Cada regla tiene un ID estable, que aparece en los mensajes y en las pruebas.

| ID | Severidad | Regla |
|---|---|---|
| L-E01 | error | El archivo no es UTF-8 (con o sin BOM); se informa la línea |
| L-E02 | error | Estructura inválida para el formato: registro sin cierre, etiqueta fuera de un registro, columna obligatoria ausente, fila con más columnas que el encabezado o BibTeX mal formado; se informa la línea |
| L-E03 | error | Identificador de la fuente repetido dentro del archivo; se informan las dos líneas |
| L-A01 | advertencia | Registro sin identificador de la fuente ni DOI: no se podrá detectar si está repetido |
| L-A02 | advertencia | Registro sin título |
| L-A03 | advertencia | Líneas de cabecera antes del primer registro (se muestran) |
| L-A04 | advertencia | Una columna o etiqueta esperada no aparece en el archivo (p. ej. sin resumen): la exportación no incluyó ese campo |

### `agentresearch importar leer ARCHIVO... --formato F --fuente ID [--mapeo mapeo.json] [--json]`

- Lee uno o varios archivos de una misma búsqueda. No necesita un estudio y **no escribe nada**. Claude Code lo puede ejecutar en el estudio (2d), y es el comando de la aceptación en este repositorio (2e).
- Muestra por archivo el hash, el número de registros, los hallazgos con su línea y la cobertura de campos; y en total, la suma de registros y los identificadores repetidos entre archivos.
- Sale con 1 si hay algún error (L-E) o identificadores repetidos entre archivos, y con 0 si solo hay advertencias.

### Pruebas (archivos sintéticos)

- Por formato: un archivo válido; con BOM; con CRLF; con campos faltantes; con caracteres no ASCII.
- Errores con su número de línea: registro sin cierre, etiqueta fuera de registro, columna ausente, UTF-16 o Latin-1, BibTeX mal formado.
- RIS con cabecera de ACS antes del primer `TY`; líneas de continuación en RIS y WoS; celdas con saltos de línea y comillas en CSV.
- BibTeX con tildes de LaTeX (`{\'e}`, `{\"u}`, `\~{n}`), `@string` y concatenación.
- Varias tandas de una misma búsqueda: suma correcta; identificador repetido dentro de un archivo (L-E03) y entre archivos.
- El mismo registro en dos descargas con distinto `Y2`: mismo `hash_completo`.
- CSV genérico con mapeo válido, con columna inexistente y con campo desconocido.
- `importar leer`: salida de texto y `--json`, códigos de salida y que no escribe nada.

## 2c. Registro de búsquedas

### Archivo de la búsqueda

Claude Code lo prepara en `.borradores/` con lo que dice el investigador (`/importar`, 2d). Esquema pydantic estricto:

```json
{
  "fuente": "wos",
  "plataforma": "Web of Science Core Collection (webofscience.com)",
  "institucion_acceso": "Universidad del Cauca",
  "cobertura": "SCI-EXPANDED, SSCI, A&HCI y ESCI, desde 2006",
  "lematizacion": null,
  "filtros": ["Document Types: Article, Review"],
  "ecuacion_ejecutada": "TS=(…) AND …",
  "justificacion_ecuacion": "",
  "resultados_interfaz": 1450,
  "justificacion_diferencia": "",
  "formato": "wos_txt",
  "mapeo": null,
  "archivos": ["C:/Users/…/Descargas/savedrecs.txt", "C:/Users/…/Descargas/savedrecs (1).txt"]
}
```

- `lematizacion` es nulo si la interfaz no ofrece la opción, o su estado tal como se ve (p. ej. «activada»).
- Las rutas de `archivos` son solo para leerlos. Nunca se guardan: el evento guarda el nombre original y la ruta relativa de la copia.
- La fecha y la hora no van en el archivo: las pide la terminal.

### `agentresearch importar registrar --busqueda archivo.json --registrado-por ID [--estudio RUTA] [--json]`

**Orden:**

1. **Valida todo sin escribir** y reporta todos los problemas a la vez:
   - el protocolo y la fuente (I-E01, I-E02);
   - la política de la fuente (I-E03);
   - la lectura de cada archivo, que debe estar sin errores (I-E07);
   - los archivos ya registrados (I-E05) y los identificadores repetidos (I-E06);
   - el revisor (I-E11);
   - que ningún original quede versionado (I-E10).
2. **Exige una terminal interactiva** (I-E12; ADR-0008, punto 11).
3. **Pide la fecha** (`AAAA-MM-DD`) **y la hora** (`HH:MM`) de la búsqueda, por separado.
   - Propone el desfase del computador para esa fecha, calculado con `astimezone()` sobre la fecha sin zona, y el investigador lo confirma o escribe otro (`±HH:MM`).
   - Si ese desfase difiere del actual, avisa que la fecha cae en otro periodo de horario de verano.
   - Rechaza una fecha futura o anterior a la aprobación del protocolo (I-E04).
4. **Determina la versión del protocolo vigente en esa fecha** y la ecuación esperada (ADR-0010, punto 12), la compara con la ejecutada y clasifica la relación: `identica`, `desviacion` o `adaptacion_generica`. Una desviación sin justificación es I-E09. Una diferencia entre los resultados de la interfaz y los registros leídos sin justificación es I-E08.
5. **Muestra el resumen completo:** fuente, plataforma, institución, cobertura, filtros, lematización, fecha y hora local y UTC, versión del protocolo, las dos ecuaciones con su diferencia y su relación, cada archivo con su hash y su número de registros, los totales frente a la interfaz, las justificaciones y los campos que se versionarán según la política.
6. **Pide la frase** `registrar imp-NNNN`. Una respuesta distinta cancela sin escribir.
7. **Escribe**, con el evento como punto de confirmación (ADR-0010, punto 18):
   1. copia los originales a `exportaciones_originales/imp-NNNN/`;
   2. escribe `importaciones/imp-NNNN/importacion.json`, `registros.jsonl` y `registros.csv`, de forma atómica;
   3. registra `busqueda_registrada`;
   4. actualiza `anclaje.json`.
8. **Muestra el anclaje** para el mensaje del commit, y el recordatorio de las copias de los originales (ADR-0010, punto 9).

**Comprobación de versionado (I-E10).** `git check-ignore -q` sobre cada ruta de destino en `exportaciones_originales/imp-NNNN/`, y sobre cada archivo de origen que esté dentro del estudio. Solo se acepta la salida 0. Con 1, 128, sin Git o fuera de un repositorio, el comando se niega y explica el arreglo: ejecutar `estudio actualizar` para recibir el `.gitignore` nuevo o mover el archivo fuera del estudio. Las pruebas usan repositorios temporales creados con `git init` y omiten la prueba si Git no está instalado; la integración continua lo tiene.

### Reglas del registro

| ID | Regla |
|---|---|
| I-E01 | El protocolo no está vigente según el registro, o hay P-E09 o P-E10 |
| I-E02 | La fuente no está declarada en `fuentes` con `tipo: exportacion` |
| I-E03 | La política de la fuente tiene campos pendientes de confirmar (ADR-0010, punto 4) |
| I-E04 | La fecha de la búsqueda es futura o anterior a la aprobación del protocolo |
| I-E05 | Un archivo ya está registrado en el estudio (mismo hash) o aparece dos veces en la búsqueda |
| I-E06 | Un identificador de la fuente se repite dentro de un archivo o entre archivos de la búsqueda |
| I-E07 | Un archivo tiene errores de lectura (L-E) |
| I-E08 | Los registros leídos no coinciden con los resultados de la interfaz y no hay justificación |
| I-E09 | La ecuación de una fuente con traductor se modificó y no hay justificación |
| I-E10 | Un original quedaría versionado, o no se pudo comprobar con Git |
| I-E11 | `--registrado-por` no es un revisor humano declarado en `seleccion.revisores` |
| I-E12 | No hay terminal interactiva |

### Evento `busqueda_registrada`

`datos`, validados con pydantic estricto:

- `id_importacion`, `fuente`, `plataforma`, `institucion_acceso`, `cobertura`, `lematizacion`, `filtros`;
- `fecha_hora_busqueda` (ISO 8601 con desfase) y `fecha_hora_busqueda_utc`;
- `version_protocolo` (la vigente en esa fecha) y `evento_version` (el ID de su aprobación o enmienda);
- `ecuacion_esperada` `{texto, hash, origen: ecuaciones_md | regenerada, version_agente}`, `ecuacion_ejecutada` `{texto, hash}`, `relacion_ecuacion` y `justificacion_ecuacion`;
- `resultados_interfaz`, `registros_leidos` y `justificacion_diferencia`;
- `archivos`: `{nombre_original, formato, hash, registros, copia}`, con `copia` como ruta relativa en `exportaciones_originales/imp-NNNN/`;
- `mapeo`: su hash, si hay;
- `carpeta` (`importaciones/imp-NNNN`), `hash_importacion_json`, `hash_registros_jsonl` y `hash_registros_csv`;
- `politica` `{version, hash}`;
- `registrado_por` (`{tipo: humano, id}`).

**P-E10 se amplía:** el esquema de `busqueda_registrada`, los números de importación consecutivos desde `imp-0001`, y que los tres archivos de cada `importaciones/imp-NNNN/` existan con los hashes registrados. Que falten los originales **no** es P-E10, porque no se versionan: lo informa `importar historial`.

### `agentresearch importar historial [--estudio RUTA] [--json]`

- Lista cada búsqueda: fuente, fecha y hora local y UTC, versión del protocolo, relación de la ecuación, resultados de la interfaz frente a registros leídos, archivos y justificaciones.
- Da los totales por fuente y el total general: los registros identificados en bases de datos del diagrama de flujo (PRISMA-ScR, ítem 14). La deduplicación es del hito 4.
- Comprueba la integridad de `importaciones/` (sale con 1 si falla).
- Informa, como nota y no como error, los originales que faltan en este equipo o cuyo hash no coincide.
- Claude Code lo puede ejecutar.

### Aviso de ACS en `ecuaciones.md`

- El ID de fuente `acs` se reconoce como fuente sin traductor.
- Su entrada en «Fuentes sin traductor» lleva el aviso del ADR-0010 (punto 29): paréntesis siempre; no usar «All»; variantes en lugar de `*` dentro de frases; lematización observada; y la receta opcional por filas (Title, Abstract y Keyword, cada una con la ecuación completa entre paréntesis, unidas con OR) con su limitación frente a `TITLE-ABS-KEY`.
- Un protocolo sin `acs` produce el mismo `ecuaciones.md` que en `v0.1.0` (prueba de bytes idénticos).

### Pruebas

- Cada regla I-E01 a I-E12 con un caso que la dispare, sin escribir nada.
- Registro completo con una terminal simulada:
  - archivos escritos, evento y anclaje;
  - bytes de `registros.jsonl` y `registros.csv` iguales en repeticiones;
  - sin resumen en ningún archivo versionado.
- Fecha y hora:
  - desfase propuesto y corregido;
  - aviso de otro periodo de horario de verano, con el desfase del sistema inyectado;
  - fecha futura y anterior a la aprobación;
  - versión del protocolo vigente en una fecha entre dos enmiendas.
- Ecuación: idéntica; desviación con y sin justificación; adaptación de la genérica; esperada tomada de `ecuaciones.md` y regenerada desde `versiones/`.
- Varias tandas: suma, identificador repetido entre archivos y archivo ya importado.
- `git check-ignore`: destino ignorado; no ignorado; archivo ya agregado al índice; fuera de un repositorio.
- Atomicidad: un fallo antes del evento deja la carpeta huérfana y el reintento la sobrescribe; un fallo después del evento se reconoce.
- P-E10 con `importacion.json` alterado, `registros.csv` eliminado y números no consecutivos.
- `importar historial`: totales por fuente, originales ausentes y `--json`.
- `ecuaciones.md` con y sin `acs`.

## 2d. Plantillas del estudio

Llegan a los estudios existentes con `estudio actualizar` (ADR-0007, punto 20).

- **`.gitignore`:** agrega `exportaciones_originales/`, con un comentario que remite al ADR-0010.
- **`.claude/settings.json`:**
  - `allow`: `importar leer` e `importar historial` (Bash y PowerShell);
  - `deny`: `*agentresearch importar registrar*` (Bash y PowerShell), `Edit(/importaciones/**)` y `Edit(/exportaciones_originales/**)`.

  `importar leer` no coincide con la regla `deny` porque el subcomando es distinto.
- **Skill `/importar`** (`.claude/skills/importar/`, con `disable-model-invocation: true`):
  1. comprueba con `validar` e `historial` que el protocolo esté vigente, sin P-E09 ni P-E10, y que el `.gitignore` ignore `exportaciones_originales/`; si no, explica `estudio actualizar`;
  2. muestra la ecuación de la fuente desde `ecuaciones.md` y los pasos manuales: dónde pegarla, qué filtros aplicar, en qué formato exportar y el máximo por exportación de la base (ADR-0010, punto 25);
  3. pide al investigador, una cosa a la vez: plataforma, institución, cobertura, filtros, lematización, la ecuación tal como la ejecutó, los resultados de la interfaz y dónde guardó los archivos;
  4. ejecuta `importar leer` y explica el resultado; si la suma no coincide con la interfaz, pregunta el motivo para la justificación;
  5. prepara `.borradores/busqueda.json` y da el comando exacto de `importar registrar` para la terminal del investigador (PowerShell o la terminal de VS Code), con lo que verá y la frase que debe escribir;
  6. después, verifica con `importar historial`, sugiere el commit con el anclaje en el mensaje y **recuerda guardar los originales** en el equipo y, si la base está cubierta por la confirmación de la Biblioteca, en la nube institucional; si no, en un respaldo fuera de la nube (ADR-0010, punto 9);
  7. para ACS, explica su rol (ADR-0010, punto 27): búsquedas complementarias puntuales, descarga por selección o por página como tandas, y nunca herramientas que automaticen la interfaz.
- **`CLAUDE.md` del estudio:** la tabla de comandos incluye `importar leer`, `importar registrar` (solo el investigador) e `importar historial`, y la prueba que compara la tabla con la CLI sigue pasando. Se agrega la regla: los originales y los registros completos no se versionan ni se copian a archivos versionados.
- **`README.md` del estudio:** anuncia `importaciones/` y `exportaciones_originales/`.
- **Pruebas:** contenido esperado de las plantillas; reglas de permisos; que `importar registrar` coincide con la regla `deny` y `importar leer` no; `estudio actualizar` lleva el `.gitignore` y la *skill* nuevos a un estudio de `v0.1.0`.

## 2e. Aceptación y cierre de `v0.2.0`

### Antes de empezar

- El investigador completa en el ADR-0010 la confirmación de la Biblioteca (medio, fecha y bases cubiertas) y la comprobación adicional de ACS.
- Se resuelven los campos pendientes de la política (ADR-0010, punto 4). Si alguno no se confirma, sale de la tabla en un commit de este repositorio.

### Parte A: exportaciones reales de prueba (repositorio del agente)

- El investigador exporta una búsqueda de prueba con pocos registros:
  - Scopus en CSV, RIS y BibTeX;
  - Web of Science en texto plano (.txt), en dos tandas si es posible;
  - ACS en RIS, con uno a tres registros;
  - Lens en CSV.

  Las guarda en `exportaciones_prueba_local/`, que Git ignora.
- Claude Code las lee **solo con `importar leer`**: no se registran ni se versionan. Se comprueba que los conteos coinciden con la interfaz y que las correspondencias de campos son correctas, y se corrigen las tablas de los lectores con lo que revelen (columnas, etiquetas y campos volátiles).
- Queda constancia en el ADR-0010, «Aceptación»: formatos, número de registros por archivo, hallazgos y correcciones, sin copiar datos de los registros.

### Parte B: estudio de demostración

1. Se publica una etiqueta candidata `v0.2.0rcN`, con la confirmación escrita del investigador, como en el hito 1 (ADR-0007, punto 8).
2. El estudio pasa a esa etiqueta con `estudio actualizar`: la desviación queda registrada, porque el protocolo está vigente (ADR-0007, punto 20). Al publicar `v0.2.0`, el estudio pasa a ella del mismo modo.
3. Con `/importar`, el investigador registra en su terminal las búsquedas reales de las fuentes de exportación que declara el protocolo, `scopus` y `wos`, con `importar registrar`.
4. Claude Code verifica en solo lectura:
   - `importar historial`: conteos por fuente frente a la interfaz;
   - `protocolo validar`: sin P-E10;
   - `registro verificar` con el anclaje;
   - que ningún archivo versionado contiene resúmenes, y que `git status` no muestra `exportaciones_originales/`.
5. Si conviene agregar ACS al estudio de demostración con una enmienda de su protocolo, se propone con opciones en ese momento (el ADR-0010, punto 27, no la usa como base de búsqueda).

## ADR que el hito 2 debe producir

- **ADR-0010:** registros, importación de búsquedas manuales y datos de terceros. Propuesta en el 2a; se acepta al cerrar el 2e, con su sección «Aceptación».
- **Nota posterior del ADR-0004**, al aceptar el ADR-0010: el alcance de «reproducible» (ADR-0010, punto 3).
- Un ADR nuevo solo si una decisión de implementación lo exige (p. ej. cambiar bibtexparser por un lector propio).

## Criterio de terminado del hito 2

- Sub-hitos 2a a 2e completos, con pruebas.
- Cobertura de al menos 90 % en `registros` e `importacion`, verificada por la integración continua.
- CI en verde en Windows y Ubuntu.
- ADR-0010 aceptado, `arquitectura.md` y `CHANGELOG.md` actualizados.
- Etiqueta `v0.2.0`.
- Exportaciones de prueba leídas con conteos correctos (parte A) y búsquedas del estudio de demostración registradas (parte B).
