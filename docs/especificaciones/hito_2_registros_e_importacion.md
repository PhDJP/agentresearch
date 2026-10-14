# Especificación del hito 2: registros e importación

- **Estado:** propuesta de Claude Code (2026-09-29), con las decisiones del investigador y del asesor. Se revisa con el asesor antes de programar, y cada sub-hito se revisa antes de implementarlo.
- **Revisión del 2026-10-04:** incorpora los ajustes del asesor al ADR-0010 (principio «local completo, nube mínima y configurable»; los campos pendientes ya no bloquean `importar registrar`; regla de la evidencia literal; respaldo separado de la publicación; `adaptacion_generica` solo con datos sintéticos; máximos y términos «por verificar»).
- **Revisión del 2026-10-12:** incorpora la revisión de diseño del 2a: registro en dos tipos, `id_fuente` regido por el campo que repite, techo de `campos_habilitables`, base completa, forma de `evidencia_literal` y `respaldo_nube`, regla I-E13 y versión de la normalización. Los cambios están en el 2a, el 2b, el 2c, el 2d y el criterio de terminado, y en el ADR-0010 (propuesta).
- **Revisión del 2026-10-13:** incorpora la preparación del 2b y las exportaciones reales de prueba. El 2b cambia en: el resolvedor de concatenaciones `#` y la recuperación de la clave BibTeX repetida (la biblioteca no hace ninguna de las dos), el comienzo del registro de Web of Science (`PT`), la regla L-E03 «dentro del archivo o entre archivos», la nueva L-A05, el archivo de mapeo con objeto y tipo de identificador, los campos volátiles (`Export Date:` en `N1` del RIS de Scopus; `DA` de Web of Science «por verificar»), las continuaciones de Web of Science, los perfiles por fuente y los códigos de salida de `importar leer`. El 2c, el 2d y el 2e llevan los ajustes que de ahí se derivan. Los cambios están en el ADR-0010 (puntos 14, 20, 23, 24 y 28).
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
- Las exportaciones reales de prueba nunca entran a este repositorio: van en `exportaciones_prueba_local/`, que ya está en el `.gitignore` del agente (commit `d6b1790`, rama del 2b).
- Todos los comandos nuevos admiten `--json`, con la forma común del ADR-0008 (punto 26): código 0 si la operación se completa, 1 si se rechaza o se cancela y 2 si los argumentos no son válidos.

## 2a. Módulo `registros`

**Módulo `agentresearch.registros`.** Sin dependencias nuevas.

### Registro normalizado

Un registro es lo que devuelve una fuente para un documento. Hay dos tipos, ambos con esquema pydantic estricto (`extra="forbid"`) e inmutables:

- **`RegistroNormalizado`:** todo lo que produce un lector (2b), sin identificadores de importación. Es lo que usa `importar leer`, que no registra nada y por eso no tiene `imp-NNNN`.
- **`Registro`:** un `RegistroNormalizado` con `id` e `id_importacion`, que asigna el registro de la búsqueda (2c).

En la tabla, `id` e `id_importacion` son campos de `Registro`; los demás, de `RegistroNormalizado`.

| Campo | Contenido | Versionable |
|---|---|---|
| `id` | `imp-NNNN-NNNNN`: importación y posición en la búsqueda (orden de los archivos declarado y, dentro de cada archivo, orden de lectura). La posición va de 1 a 99 999; superarla es un error explícito | siempre |
| `id_importacion` | `imp-NNNN` | siempre |
| `fuente` | ID de la fuente en el protocolo (`scopus`, `wos`, `acs`, …) | siempre |
| `formato` | `ris`, `bibtex`, `scopus_csv`, `wos_txt` o `csv` | siempre |
| `archivo` y `posicion` | nombre del archivo original y línea física donde empieza el registro, en todos los formatos (en un CSV con celdas de varias líneas no coincide con el número de fila) | siempre |
| `tipo_id_fuente` y `id_fuente` | `eid`, `ut`, `doi`, `pmid`, `lens_id` o `ninguno`, y su valor | según la configuración del estudio; con tipo `doi` o `pmid`, se rige por `doi` o `pmid` (ver «Regla de versionado») |
| `titulo` | texto | según la configuración del estudio |
| `autores` | lista, en el orden de la fuente | según la configuración del estudio |
| `anio` | entero o nulo | según la configuración del estudio |
| `fuente_publicacion` | revista, libro, congreso u oficina de patentes | según la configuración del estudio |
| `volumen`, `numero`, `paginas` | texto o nulo | según la configuración del estudio |
| `doi` | normalizado o nulo | según la configuración del estudio |
| `pmid` | texto o nulo | según la configuración del estudio |
| `tipo_documento`, `idioma` | el texto de la fuente, sin traducir | según la configuración del estudio |
| `resumen`, `palabras_clave_autor`, `palabras_clave_indexadas` | texto o lista | nunca |
| `otros` | `{etiqueta o columna: valor}` para los campos leídos sin campo propio, sin los volátiles | nunca |
| `hash_completo` | SHA-256 del registro completo normalizado (abajo) | siempre |

- **Patentes y tesis.** No se exigen DOI ni `fuente_publicacion` (ADR-0010, punto 22).
- **Normalización.** Se aplica a todo campo de texto, incluidos `resumen` y los valores de `otros`, en este orden. Las posiciones y el hash de la evidencia literal del hito 5 se calculan sobre el texto ya normalizado.
  1. Unicode NFC.
  2. Cada secuencia de espacios Unicode (incluidos el espacio duro U+00A0 y los saltos de línea) pasa a un solo espacio U+0020, y se recortan los extremos. Los saltos de párrafo del resumen se pierden.
  3. DOI (DOI Handbook, §2.4): se busca la forma `10.<registrante>/<sufijo>` dentro de cualquier URL o prefijo (`https://doi.org/`, `doi:`, el proxy de la biblioteca). El registrante admite subdivisiones (`10.1000.10/`). De una URL se quitan la consulta (`?…`) y el fragmento (`#…`) literales y, después, se decodifican los `%XX`: un `%23` o un `%3F` es parte del DOI y no abre un fragmento ni una consulta. También se quita la barra final de una URL. Se descarta la puntuación final `.`, `,`, `;` o `:`. Cuando el DOI sale de texto libre (hay un prefijo, una URL o texto alrededor, y no solo el DOI), se descarta además un cierre final (`)`, `]`, `>` o comillas) solo si no tiene su apertura dentro del DOI, porque hay DOI reales con paréntesis internos (tipo SICI): un DOI con paréntesis balanceados se conserva. Se compara el número de cierres y de aperturas del propio DOI, y las comillas rectas cuentan por paridad. Se repite hasta que no cambie nada. Solo las letras ASCII A–Z pasan a minúsculas, no los demás caracteres. Un texto sin esa forma da nulo.
  4. Las tildes de LaTeX se decodifican en el lector de BibTeX (2b), antes del paso 1.
  5. Si `tipo_id_fuente` es `doi`, `id_fuente` pasa por el paso 3: así el identificador de ACS no difiere del campo `doi`. Si no contiene un DOI, queda como texto normalizado (paso 2).

  Cambiar cualquiera de estas reglas exige incrementar `VERSION_NORMALIZACION` (abajo).
- **`hash_completo`** se calcula sobre el JSON canónico (ADR-0006, punto 2) de los campos bibliográficos, desde `tipo_id_fuente` hasta `otros`. No incluye `id`, `id_importacion`, `archivo` ni `posicion`, que cambian entre descargas, ni campos volátiles, que nunca entran a `otros` (cada lector declara los suyos, 2b). Tampoco incluye `fuente` ni `formato`, que constan aparte en el registro y en el evento. Así, el mismo registro descargado dos veces tiene el mismo hash (ADR-0010, punto 20).
- **`VERSION_NORMALIZACION`.** Una constante entera, que empieza en 1 y sube con cualquier cambio de las reglas de normalización. No entra al hash. El 2c la guarda en `importacion.json` y en el evento. Si al regenerar un registro su `hash_completo` no coincide, comparar esa versión con la vigente distingue «cambiaron las reglas» de «el original fue alterado» (ADR-0010, puntos 2 y 20).

### Artículo y estudio (provisionales)

- `Articulo` y `Estudio`, con la relación de muchos a muchos `VinculoArticuloEstudio`. Se definen con los campos mínimos (ID y vínculos) y quedan marcados en su docstring como **provisionales**: el hito 4 asocia registros a artículos y el hito 8, artículos a estudios. Sus IDs son `art-NNNNN` y `est-NNNNN`; los registros de un artículo van en `Articulo.ids_registros` (el vínculo registro→artículo es un campo, no una clase aparte).
- El registro no se fusiona ni se modifica al asociarlo: la deduplicación del hito 4 crea artículos que lo referencian.

### Política de datos y configuración de publicación

Principio del ADR-0010: **local completo, nube mínima y configurable**. Todo se importa y se conserva completo en local; lo que se versiona lo decide cada estudio, con la base registrada. Hay dos archivos, ambos validados con pydantic al cargarlos.

- **`agentresearch/registros/politica_datos.yaml` (paquete).** Lista fija `nunca_publicables` (resumen, palabras clave de autor e indexadas, referencias, conteos de citas, afiliaciones y financiación) y, por fuente, los campos que esa fuente puede aportar y que el estudio puede habilitar. **Es neutral:** no atribuye ninguna confirmación a una institución ni trae una base por omisión, porque eso es de cada estudio. Que un campo esté «confirmado» o «pendiente» lo decide la base que el estudio registra en `publicacion_datos.yaml`:

  ```yaml
  version: 1
  nunca_publicables: [resumen, palabras_clave_autor, palabras_clave_indexadas, referencias, conteos_citas, afiliaciones, financiacion]
  fuentes:
    scopus:
      campos_habilitables: [titulo, autores, doi, fuente_publicacion, anio, volumen, numero, paginas, tipo_documento, idioma, id_fuente]   # id_fuente: EID
    # wos (id_fuente: UT), acs (el ID de la fuente es el DOI) y lens con la misma forma
  ```

  `version` es un entero que sube con cada cambio de la tabla y se registra junto con el hash del archivo. `campos_habilitables` es el **techo** de una fuente que el paquete conoce: el estudio no puede habilitar un campo que esa fuente no aporta, y se rechaza al cargar la configuración. Una fuente que el paquete no conoce no tiene techo: el estudio puede habilitar cualquier campo del esquema salvo los `nunca_publicables`, con su base completa (ADR-0010, punto 4).

- **`publicacion_datos.yaml` (estudio, en la raíz, versionado).** Por fuente, los campos que el estudio habilita, cada uno con su `base`:

  ```yaml
  fuentes:
    scopus:
      campos:
        titulo:
          base: {tipo: institucion, detalle: null, medio: null, fecha: null}   # incompleta: el estudio la registra
    # ...
  evidencia_literal:
    resumen: {estado: no_permitido, base: null}   # o permitido, con su base completa (ADR-0010, punto 5)
  respaldo_nube:
    scopus: {estado: sin_verificar, base: null}
  ```

  - `base.tipo` es `institucion`, `revista` o `licencia` (un término de contrato se registra como `licencia`); `detalle`, `medio` y `fecha` completan la base.
  - **Base completa:** `tipo`, `detalle` y `fecha` siempre (la fecha en `AAAA-MM-DD`, no futura: ver «Fecha no futura»); `medio` solo con `tipo: institucion`, porque documenta cómo se obtuvo la confirmación. Con cualquier obligatorio ausente, la base es **incompleta**.
  - **Fecha no futura.** La `fecha` de una base es un día sin hora ni zona, así que se compara con la **fecha UTC del reloj más un día**: un día local puede ir hasta un día por delante de UTC (hasta UTC+14), y rechazarlo sería un falso error. Con la fecha UTC de hoy, `hoy` y `hoy + 1` se aceptan y `hoy + 2` se rechaza. Es una regla de las bases; la fecha y hora de una búsqueda (I-E04, 2c) sí lleva hora y desfase, y se compara con exactitud contra el reloj, sin tolerancia.
    - El reloj es inyectable: `reloj: Callable[[], datetime]` con zona horaria, como `RegistroEncadenado`, para que las pruebas no dependan de la fecha real. `cargar_configuracion` y `decodificar_configuracion` lo reciben; sin él, usan el reloj del sistema.
    - Quien valide una `Base` directamente (sin pasar por la carga) y no pase el reloj en el contexto de validación (`context={"ahora": …}`) también obtiene el reloj del sistema.
  - **`estado`** (en `evidencia_literal` y en cada fuente de `respaldo_nube`) es `sin_verificar`, `permitido` o `no_permitido`, con su `base`. `permitido` exige una base completa. Lo ausente equivale a `sin_verificar` en `respaldo_nube` y a `no_permitido` en `evidencia_literal` (ADR-0010, punto 5). Las claves de `evidencia_literal` son los campos de los que puede salir una cita: `resumen`, `palabras_clave_autor` y `palabras_clave_indexadas`.
  - **Cargarla rechaza**, informando todos los problemas a la vez (`ErrorConfiguracionPublicacion`; en el registro, la regla I-E13):
    - un campo de `nunca_publicables` dentro de `fuentes[*].campos`; la cita de `evidencia_literal` es la única salida permitida de esos campos, y solo como cita breve;
    - un nombre que no es un campo del esquema: un error tipográfico no debe pasar como «no publicado»;
    - un campo fuera del techo de una fuente que el paquete conoce;
    - YAML mal formado, claves repetidas o claves desconocidas.
  - La plantilla del estudio la crea **neutra**: con los campos de metadatos bibliográficos habituales (`titulo`, `autores`, `doi`, `fuente_publicacion`) y su base incompleta (`detalle`, `medio` y `fecha` vacíos), hasta que el investigador registre la suya. Trae `evidencia_literal.resumen` en `no_permitido` y ningún `respaldo_nube` (equivale a `sin_verificar`). Ninguna institución concreta aparece en el paquete ni en la plantilla; el caso de la Universidad del Cauca es un ejemplo documentado en el ADR-0010 (punto 4).
- **Regla de versionado.** `campos_versionables(fuente, politica, config)` devuelve los campos que no son `nunca_publicables`, que el estudio habilita para esa fuente y cuya base está completa. Una fuente sin entrada en `publicacion_datos.yaml` no tiene campos habilitados. Un campo ausente no se versiona.
- **`id_fuente` rige por el campo que repite.** Si `tipo_id_fuente` es `doi` o `pmid` (en ACS, el ID de la fuente es el DOI), `id_fuente` se versiona solo si `doi` o `pmid` está habilitado con base completa: habilitar el identificador no publica un DOI que el estudio no habilitó. Con `eid`, `ut` o `lens_id` rige su propia habilitación, y `tipo_id_fuente` se versiona junto con `id_fuente` (ADR-0010, punto 4).
- **Los campos que no se versionan sí se importan.** El registro completo normalizado se conserva en local (el original y su regeneración verificada por `hash_completo`). Un campo `pendiente` o con base incompleta no se versiona, pero tampoco bloquea el registro de la búsqueda (ADR-0010, punto 4).
- `hash_politica()` y `hash_configuracion()`: los SHA-256 de los **bytes** de ambos archivos, como el protocolo (se verifican con `sha256sum`), que registra cada importación. El `.gitattributes` fija LF, así que el hash no varía entre sistemas. Un cambio de comentarios cambia el hash: es aceptable y queda auditado.
- `registro_versionable(registro, campos)`: el registro con solo los campos versionables y los que se versionan siempre.

### Archivos

- `escribir_registros_jsonl(registros)`: una línea de JSON canónico por registro, solo con los campos versionables, en UTF-8 con LF.
- `escribir_vista_csv(registros)`: `registros.csv` derivado de `registros.jsonl`, con columnas fijas en el orden del esquema, `autores` unidos por `; `, UTF-8 sin BOM y fin de línea LF explícito. Es determinista: el mismo JSONL da los mismos bytes.
  - Sin BOM, Excel de Windows puede mostrar mal las tildes al abrirlo con doble clic; para eso se usa «Datos > Desde texto/CSV» con UTF-8.
  - Las celdas que empiezan por `=`, `+`, `-` o `@` **no se alteran**: la vista es una derivación fiel del JSONL, y Excel podría interpretarlas como fórmulas. Queda documentado aquí y en el docstring.

### Pruebas

- Esquema: campos desconocidos rechazados; registro sin DOI ni revista (patente, tesis) aceptado; `RegistroNormalizado` sin `id`; `Registro` con `id`; posición 99 999 aceptada y 100 000 rechazada con error explícito.
- Normalización de texto: NFC; espacio duro y saltos de línea colapsados; extremos recortados; aplicarla dos veces da el mismo resultado.
- `id_fuente` de tipo `doi`: se normaliza como DOI (`10.1021/ACS.X` y `doi:10.1021/acs.x` dan lo mismo y el mismo `hash_completo`); sin DOI dentro queda como texto normalizado; los demás tipos solo se normalizan como texto.
- DOI (con el prefijo de prueba `10.5555`): extracción desde URL, `doi:` y el proxy; `?consulta`, `#fragmento` y `%2F`; `%23` y `%3F` como parte del DOI (`…/a%23b` da `…/a#b`); barra final de una URL; puntuación final; subdivisión del registrante (`10.1000.10/`); minúsculas solo en ASCII (un carácter no ASCII queda igual); texto sin DOI → nulo; `(doi:10.5555/abc)` da `10.5555/abc`; un DOI con paréntesis balanceados, como `10.5555/(SICI)1097-4571(199806)49:6<517::AID-ASI4>3.0.CO;2-8`, se conserva solo y dentro de texto libre; un cierre sin su apertura al final de texto libre se descarta.
- `hash_completo`: igual con otro `id`, `archivo` o `posicion`; distinto si cambia un campo bibliográfico.
- Política y configuración:
  - un campo `pendiente` o con base incompleta no es versionable, pero el registro completo conserva su valor;
  - un campo ausente de la configuración no se versiona, y una fuente sin entrada no habilita nada;
  - el resumen, las palabras clave y los demás `nunca_publicables` se rechazan al cargar la configuración cuando el estudio los lista en `fuentes[*].campos`;
  - `hash_politica()` y `hash_configuracion()` cambian si cambia el archivo;
  - base completa: falta `tipo`, `detalle` o `fecha` → incompleta; `medio` ausente solo la hace incompleta con `tipo: institucion`; fecha mal formada o futura → error, con un reloj inyectado y sin depender de la fecha real (el día siguiente a la fecha UTC se acepta; dos días después se rechaza);
  - techo: un campo fuera de la lista de una fuente conocida se rechaza; una fuente desconocida admite cualquier campo del esquema salvo `nunca_publicables`; un nombre que no es campo del esquema se rechaza;
  - `id_fuente` de tipo `doi` o `pmid` no se versiona si `doi` o `pmid` no está habilitado, aunque `id_fuente` lo esté; con tipo `eid` rige su propia habilitación;
  - `evidencia_literal` y `respaldo_nube`: `permitido` sin base completa se rechaza; `evidencia_literal.resumen` se acepta, pero `resumen` dentro de `fuentes[*].campos` se rechaza; una clave de `evidencia_literal` distinta de las tres admitidas se rechaza; varios problemas se informan a la vez.
- JSONL y CSV: bytes idénticos en ejecuciones repetidas y en Windows y Ubuntu; caracteres no ASCII sin escapar; fin de línea LF; sin BOM; una celda que empieza por `=` queda sin alterar.
- Paquete (la política debe estar en el paquete instalado, no solo en el repositorio):
  - `politica_datos.yaml` se lee con `importlib.resources` y no con una ruta relativa al repositorio; la prueba falla si el archivo no está dentro del paquete `agentresearch.registros`;
  - prueba marcada `construccion`: construye el wheel con `uv build --wheel` en un directorio temporal y comprueba que `agentresearch/registros/politica_datos.yaml` está en él, con los mismos bytes que el del repositorio. Necesita `uv` y puede necesitar red para obtener el sistema de construcción (`uv_build`), así que se omite si `uv` no está, queda fuera de la ejecución por defecto (`-m "not construccion"` en `addopts`) y la integración continua la ejecuta en un paso propio. Verificado el 2026-10-12: el wheel de `v0.1.0` ya incluye `protocolo/plantillas/protocolo.yaml` y las plantillas del estudio sin configuración adicional.

## 2b. Lectores y `importar leer`

**Módulo `agentresearch.importacion`.**

**Dependencias nuevas:** `bibtexparser==2.0.1` y `pylatexenc==2.11`, con la versión exacta fijada y justificadas en el commit (ADR-0010, punto 24).

El 2b también agrega `importacion` al `--include` del paso de cobertura mínima de la integración continua (el 2a agregó `registros`). La carpeta `exportaciones_prueba_local/` ya está en el `.gitignore` del agente (commit `d6b1790`).

**Revisión del 2026-10-13.** Esta sección incorpora: las cinco contradicciones (C1 a C5) y las ambigüedades (A1 a A10) de la preparación del 2b, con las decisiones del investigador y del asesor; y lo verificado con las exportaciones reales de prueba del 2026-10-13 (abajo, «Verificado con las exportaciones de prueba»).

### Interfaz común

`leer(ruta, formato, fuente, mapeo=None) -> ResultadoLectura`, con:

- los registros completos normalizados (`RegistroNormalizado`, sin `id` ni `id_importacion`: los asigna el 2c);
- los hallazgos: ID de regla, severidad, archivo, número de línea y mensaje;
- las líneas de cabecera anteriores al primer registro;
- el hash del archivo y el número de registros;
- la cobertura de cada campo: cuántos registros lo tienen. Se cuenta sobre el registro ya normalizado: un valor vacío (`pages = {}` en BibTeX, una celda vacía en un CSV) cuenta como ausente.

`leer_busqueda(rutas, formato, fuente, mapeo=None) -> ResultadoBusqueda` agrupa los archivos de una misma búsqueda, en el orden declarado: la lista de `ResultadoLectura`, la suma de registros, los identificadores repetidos entre archivos (con archivo y línea de cada ocurrencia) y la cobertura total. Es la forma del campo `resultado` de `--json` (ADR-0008, punto 26).

- **Los mensajes no contienen datos de los registros.** Citan regla, archivo y línea, nunca un valor de campo: Claude Code ve la salida y los resúmenes tienen licencia (ADR-0010, punto 26).
- El formato lo declara el investigador; el lector no lo adivina.

### Formatos

| Formato | Lector | Notas |
|---|---|---|
| `ris` | propio | Etiquetas de dos caracteres. `TY` abre y `ER` cierra; la línea `ER` puede llevar o no el espacio final (`ER  - ` en ACS, `ER  -` en Scopus). Tolera líneas de cabecera antes del primer `TY` (RIS de ACS), líneas vacías entre registros y al final, y líneas de continuación. |
| `wos_txt` | propio | Texto plano con etiquetas de Web of Science. `FN` y `VR` de cabecera; el registro **abre con `PT` y cierra con `ER`**, seguido de una línea vacía; `EF` cierra el archivo. Las líneas que empiezan con tres espacios continúan la etiqueta anterior (ver «Continuaciones de Web of Science»). |
| `scopus_csv` | propio, con `csv` | Columnas leídas por nombre; campos entre comillas dobles y separados por comas; celdas entre comillas con saltos de línea (no observados en la prueba). |
| `csv` | propio, con `csv` | Un archivo de mapeo JSON declara qué columna va a cada campo (ver «Archivo de mapeo»); se valida y su hash queda en el resultado. Cubre Lens. |
| `bibtex` | bibtexparser 2.0.1 | Tildes de LaTeX decodificadas con pylatexenc. La biblioteca resuelve `@string`, pero **no** las concatenaciones con `#`: un resolvedor propio mínimo las resuelve (cadenas entre `{}` o `""`, nombres de `@string` y números unidos por `#`, con espacios o saltos opcionales). La entrada de **clave repetida** no queda en `entries`: la biblioteca la deja en `failed_blocks` como `DuplicateBlockKeyBlock`, y el lector la recupera desde su atributo `ignore_error_block` (no existe `duplicate_block` en la 2.0.1). Una prueba confirma el nombre del atributo con la versión fijada. |

- **Una clave BibTeX repetida no es un identificador de la fuente:** la entrada se recupera y se cuenta, y no dispara L-E03.
- **`--mapeo`** solo se admite con `csv` y es obligatorio con él; con otro formato, o sin él con `csv`, el analizador de argumentos rechaza la invocación (código 2).

### Archivo de mapeo

JSON de un solo nivel `{"columna": destino}`, donde `destino` es:

- un nombre de campo del esquema (`"titulo"`, `"doi"`, `"anio"`…), o
- un objeto `{"campo": "autores", "separador": "; "}`, que es obligatorio para los campos de lista (`autores`, `palabras_clave_autor`, `palabras_clave_indexadas`) y no se admite en los demás, o
- `"id_fuente:TIPO"`, con `TIPO` en `eid`, `ut`, `doi`, `pmid` o `lens_id`: la columna es el identificador de la fuente y `tipo_id_fuente` toma ese valor.

```json
{
  "Titulo": "titulo",
  "Autores": {"campo": "autores", "separador": "; "},
  "Identificador": "id_fuente:lens_id",
  "DOI": "doi"
}
```

Los nombres de columna son del ejemplo; los de Lens se confirman en el 2e. Las columnas sin destino van a `otros` con el nombre de la columna. Si la celda de una columna `id_fuente:TIPO` está vacía, el registro queda con `tipo_id_fuente: ninguno`. Es L-E02 (con el nombre del archivo de mapeo): una columna del mapeo que no está en el encabezado, un campo que no es del esquema, un campo de lista sin separador, un separador en un campo que no es de lista, o dos columnas con el mismo destino. Un archivo de mapeo que no se puede leer o no es JSON no es un error de lectura de una exportación: el comando lo informa en `errores` y sale con 1, sin leer el CSV (ver los códigos de salida).

### Correspondencia de campos

Cada lector lleva una tabla de etiquetas o columnas a campos del esquema: una **tabla base** por formato y un **perfil por ID de fuente** (`scopus`, `wos`, `acs`, `lens`) para lo que difiere de la base. Lo que no se mapea va a `otros` con la etiqueta o la columna de origen, sin traducir.

- **Campos repetidos de `otros`** (una etiqueta que aparece varias veces en un registro) se unen con `"; "`, fijo. Entra al `hash_completo`.
- **`anio`:** el primer grupo de cuatro dígitos del valor. Si no se obtiene, `anio` queda nulo y el valor crudo va a `otros`.
- **`paginas`:** `inicio-fin`, o solo el inicio. El número de artículo (`AR` en Web of Science, `C7` en el RIS de Scopus, `Art. No.` en el CSV de Scopus) va a `otros`.
- **`KW` del RIS** va a `otros` hasta que el 2e verifique si la fuente distingue palabras clave de autor e indexadas. En el RIS de Scopus no las distingue (ver abajo).
- **Documentación de cada fila:** la tabla del lector lleva la URL oficial y la fecha de verificación, y una columna «verificado con» (`oficial`, `exportación 2026-10-13` o `por verificar`).
  - Web of Science: la [lista oficial de etiquetas](https://support.clarivate.com/ScientificandAcademicResearch/s/article/Web-of-Science-Core-Collection-List-of-field-tags-in-output?language=en_US) (`TI`, `AU`, `SO`, `PY`, `VL`, `IS`, `BP`, `EP`, `AR`, `DI`, `PM`, `UT`, `DT`, `LA`, …); no se pudo leer en la preparación del 2b (la sede respondió 403), así que lo que no aparece en las exportaciones de prueba queda «por verificar».
  - Scopus: la [página oficial de los campos que exporta](https://www.elsevier.support/scopus/answer/what-fields-are-used-when-exporting-documents-from-scopus) (act. 2025-11-07).
  - RIS: la especificación RIS (reconstrucción secundaria en [gris](https://gris.readthedocs.io/en/stable/specification.html), porque la original no tiene sede mantenida) y las exportaciones de ACS y Scopus.

Perfiles observados el 2026-10-13 (una sola exportación por fuente, de 1 a 5 registros: son una verificación, no una especificación cerrada; el 2e los completa):

| Destino | Scopus CSV | Scopus RIS | Scopus BibTeX | WoS | ACS RIS |
|---|---|---|---|---|---|
| `titulo` | `Title` | `TI` | `title` | `TI` | `T1` |
| `autores` | `Authors` (`"; "`) | `AU`, uno por línea | `author` (` and `) | `AU`, uno por línea | `AU`, uno por línea |
| `anio` | `Year` | `PY` | `year` | `PY` | `PY` |
| `fuente_publicacion` | `Source title` | `T2` | `journal` | `SO` | `JO` |
| `volumen`, `numero` | `Volume`, `Issue` | `VL`, `IS` | `volume`, `number` | `VL`, `IS` | `VL`, `IS` (no aparecieron en el registro observado) |
| `paginas` | `Page start`, `Page end` (vacíos en la prueba) | no hay `SP`/`EP` | `pages` (vacío) | `BP`, `EP` | `SP`, `EP` (no aparecieron) |
| `doi` | `DOI` | `DO` | `doi` | `DI` | `DO` |
| `pmid` | `PubMed ID` | `C2` (perfil `scopus`) | `pmid` | `PM` (por verificar) | — |
| `tipo_documento` | `Document Type` | `M3` (perfil `scopus`; `TY` es `JOUR` también en una revisión) | `type` (el tipo de entrada es `@article` también en una revisión) | `DT` (por verificar) | — |
| `idioma` | `Language of Original Document` | `LA` | `language` | `LA` (por verificar) | — |
| `resumen` | `Abstract` | `AB` | `abstract` | `AB` (por verificar) | `AB` |
| `palabras_clave_autor` | `Author Keywords` (`"; "`) | — (`KW` mezcla ambas: `otros`) | `author_keywords` (`"; "`) | `DE` (por verificar) | — |
| `palabras_clave_indexadas` | `Index Keywords` (`"; "`) | — | `keywords` (`"; "`) | `ID` (por verificar) | — |
| `tipo_id_fuente`, `id_fuente` | `eid`, `EID` | ver «Decisiones abiertas», H1 | `ninguno` (la exportación no trae EID, dato oficial confirmado) | `ut`, `UT` (`WOS:` + 15 dígitos, tal cual) | `doi`, `DO` |
| volátiles (se descartan) | `Cited by` (H2) | línea `Export Date:` de `N1`; `Cited By:` (H2) | `Cited by:` de `note` (H2) | `DA` (por verificar) | `Y2` |

En la tabla, los campos nunca publicables (`Affiliations` o `AD`, `References`, `Funding Details`…) se leen igual: van a `otros` y se conservan en local.

### Continuaciones de Web of Science

Una línea con tres espacios iniciales continúa la etiqueta anterior. Qué significa depende de la etiqueta:

- **Listas (`AU`, `AF`):** cada línea es un elemento (un autor por línea). Se observó en los tres registros de la prueba.
- **Texto (`TI`; se espera lo mismo en `SO` y `AB`, por verificar):** las líneas son un texto cortado a unos 74 caracteres (longitud máxima observada: 75); se unen con un espacio.
- **Listas con `"; "` (`OI`, `RI`; se espera lo mismo en `DE` e `ID`, por verificar):** el corte puede caer dentro de un elemento (observado en `OI` y `RI`); las líneas se unen con un espacio y el valor se separa por `"; "`.

La tabla del lector declara el tipo de cada etiqueta (`lista_por_linea`, `texto` o `lista_con_separador`). Una etiqueta no declarada se trata como `texto`.

### Campos volátiles

Cada tabla declara los campos que se descartan porque cambian en cada descarga y no describen el documento. Un volátil nunca entra a `otros`, así que no entra al `hash_completo`. Un volátil puede ser una etiqueta o **una línea con prefijo dentro de una etiqueta repetible**:

| Fuente y formato | Volátil | Estado |
|---|---|---|
| ACS, RIS | `Y2`: fecha de descarga, `MM/DD/AAAA` (verificado: coincide con la fecha UTC del nombre del archivo) | verificado 2026-10-13 |
| Scopus, RIS | la línea de `N1` que empieza con `Export Date:` (una por registro, `DD Mes AAAA`). El resto de las líneas de `N1` va a `otros` | verificado 2026-10-13 |
| Web of Science, texto plano | `DA` (fecha de generación del informe) | **por verificar:** no aparece en la exportación de prueba; el archivo no trae ninguna fecha de generación, ni por registro ni de cabecera |
| Scopus, `Cited by`, `Cited By:` de `N1` y `Cited by:` de `note` | conteo de citas, que cambia con la fecha | pendiente de decisión (H2) |

### Codificación

UTF-8, con o sin BOM. Cualquier otra se rechaza con la línea del primer byte inválido. Fin de línea LF o CRLF.

### Verificado con las exportaciones de prueba (2026-10-13)

Exportaciones reales de una búsqueda de prueba, guardadas en `exportaciones_prueba_local/` y leídas solo para comprobar estructura. Sin datos de los registros.

| Archivo | Formato | BOM | Fin de línea | Registros | Estructura |
|---|---|---|---|---|---|
| Scopus CSV | `scopus_csv` | sí | LF | 5 | 45 columnas; 1 línea física por registro; ninguna celda con salto de línea (máximo 23 411 caracteres por celda) |
| Scopus RIS | `ris` | no | LF | 5 | sin cabecera; línea vacía tras cada `ER`; etiquetas `AB AD AU C2 C7 DB DO ER IS J2 KW LA M3 N1 PB PY SN T2 TI TY UR VL`; sin líneas de continuación |
| Scopus BibTeX | `bibtex` | no | LF | 5 | 5 `@article`; claves únicas; todos los valores entre `{}`; sin `#`, `@string` ni secuencias LaTeX; UTF-8 directo (letras griegas, espacio duro, `±`) |
| Web of Science | `wos_txt` | sí | LF | 3 | `FN`, `VR`; registros de `PT` a `ER` con una línea vacía después; `EF` al final y sin salto de línea final; `PT` vale `J` |
| ACS | `ris` | no | CRLF | 1 | cabecera de 3 líneas y una vacía; `TY` a `ER`; tres líneas vacías al final |

- **Conteos.** Scopus: 5 registros en cada uno de los tres formatos, que corresponden a los «primeros 5» de 466 resultados anotados. ACS: 1 registro de 3 946 resultados, el seleccionado. Web of Science: el archivo trae **3 registros**, y la nota del investigador dice «Resultado: 3 articulos» y «Articulos seleccionados 1»; la cuenta coincide con los resultados, no con la selección: ver «Por confirmar».
- **Scopus: el mismo documento en tres formatos.** El orden, el DOI, el título, el año, la fuente, el volumen, el número, el PMID y el idioma son idénticos. Difieren:
  - los autores: el CSV da `Apellido I.`; el RIS, `Apellido, I.`; el BibTeX, el nombre completo `Apellido, Nombre`;
  - en un registro de 13 autores, el RIS trae 12: falta el único nombre de una sola palabra (el BibTeX y el CSV sí lo traen). La causa no está verificada; no se corrige (regla 6);
  - el resumen del BibTeX conserva marcas `<sub>…</sub>` que el CSV y el RIS no traen. Un mismo documento leído de otro formato **no** da el mismo `hash_completo`, y no es un objetivo que lo dé: el hash identifica lo leído de un archivo (ADR-0010, punto 20);
  - el BibTeX no trae el número de artículo (`pages` vacío) ni el EID; el RIS lo trae en `C7` y en una línea `EID:` de `N1`.
- **`KW` del RIS de Scopus mezcla** palabras clave de autor e indexadas: en los cinco registros, la cuenta de `KW` es la suma de ambas columnas del CSV. Por eso va a `otros` y no a `palabras_clave_autor`.
- **Web of Science sin resumen.** Las etiquetas presentes son `AF AR AU BP DI EA EF EI EP ER FN IS OI PD PT PY RI SN SO TI UT VL VR`. Faltan `AB`, `DT`, `LA`, `DE`, `ID`, `C1`, `CR` y otras que trae el registro completo: la exportación se hizo con un contenido de registro reducido, no con el completo. Con ella, L-A04 avisa del resumen, y para el cribado no sirve.

### Reglas de lectura

Cada regla tiene un ID estable, que aparece en los mensajes y en las pruebas.

| ID | Severidad | Regla |
|---|---|---|
| L-E01 | error | El archivo no es UTF-8 (con o sin BOM); se informa la línea |
| L-E02 | error | Estructura inválida para el formato: registro sin cierre, etiqueta fuera de un registro, columna obligatoria ausente, fila con más o con menos columnas que el encabezado, BibTeX mal formado, o un mapeo inválido (ver «Archivo de mapeo»); se informa la línea |
| L-E03 | error | Identificador de la fuente (`tipo_id_fuente` e `id_fuente`) repetido **dentro del archivo o entre archivos de la búsqueda**; se informan las dos ubicaciones (archivo y línea) |
| L-A01 | advertencia | Registro sin identificador de la fuente ni DOI: no se podrá detectar si está repetido |
| L-A02 | advertencia | Registro sin título |
| L-A03 | advertencia | Líneas de cabecera antes del primer registro (se muestran) |
| L-A04 | advertencia | Un campo esperado (`titulo`, `autores`, `anio`, `doi` y `resumen`) no aparece en el archivo: en un CSV, la columna que el perfil le asigna no está en el encabezado; en un formato con etiquetas, la etiqueta no aparece en ningún registro. La exportación no incluyó ese campo |
| L-A05 | advertencia | El mismo DOI en dos o más registros que **no tienen identificador de la fuente**, dentro del archivo o entre archivos; se informan las ubicaciones. Puede ser un documento repetido o dos registros que comparten el DOI: la deduplicación es del hito 4 |

- **Identidad para L-E03:** el par `(tipo_id_fuente, id_fuente)`. El DOI **no** hace de identidad para el error: un DOI repetido entre registros sin identificador de la fuente (p. ej. el BibTeX de Scopus, que no trae EID) es la advertencia L-A05. Un registro con identificador de la fuente se compara solo por él.
- **Lo que no es regla de lectura:** una clave BibTeX repetida (se recupera sin hallazgo) y las diferencias entre formatos de una misma fuente.

### `agentresearch importar leer ARCHIVO... --formato F --fuente ID [--mapeo mapeo.json] [--json]`

- Lee uno o varios archivos de una misma búsqueda. No necesita un estudio y **no escribe nada**. Claude Code lo puede ejecutar en el estudio (2d), y es el comando de la aceptación en este repositorio (2e).
- Muestra por archivo el hash, el número de registros, los hallazgos con su línea y la cobertura de campos; y en total, la suma de registros y los identificadores repetidos entre archivos.
- **Códigos de salida** (ADR-0008, punto 26):

| Código | Cuándo | Qué se leyó |
|---|---|---|
| 0 | La lectura se completó y solo hay advertencias (L-A) o ninguna | todo |
| 1 | Algún archivo tiene un error de lectura (L-E01 a L-E03, incluidos un identificador repetido entre archivos y un mapeo con contenido inválido), no se pudo abrir (no existe, es una carpeta o no hay permiso) o el archivo de mapeo no se pudo leer | los archivos que se pudieron leer; el resultado se muestra completo y lo que no se pudo abrir va en `errores` |
| 2 | **El analizador de argumentos rechazó la invocación y no se ejecutó nada** (ADR-0008, punto 26): falta algún `ARCHIVO`, `--formato` o `--fuente`; `--formato` no es uno de los cinco admitidos; `--fuente` vacía; `--mapeo` con un formato que no es `csv`, o ausente con `csv`; una opción desconocida | nada |

  El 2 solo lo emite el analizador de argumentos, antes de abrir ningún archivo: es un error de uso del comando. Todo lo que se descubre al leer, incluido un archivo que no existe, es 1.
- `--json` devuelve la forma común del ADR-0008 (punto 26): `{"comando": "importar leer", "exito": bool, "errores": [], "version_agente": "…", "resultado": ResultadoBusqueda}`; `exito` es verdadero solo con código 0. Con código 2, argparse escribe su mensaje en el flujo de error y no hay JSON.

### Decisiones abiertas tras las exportaciones reales

Quedan para la revisión del asesor; el 2b no las implementa hasta que se resuelvan.

| ID | Pregunta | Opciones | Recomendación |
|---|---|---|---|
| H1 | El RIS de Scopus no tiene etiqueta de EID: lo trae una línea `EID:` dentro de `N1`, igual al del CSV en los 5 registros | (a) el perfil `scopus` toma `EID:` de `N1` como `id_fuente` (`eid`); (b) queda en `otros` y el registro se identifica por su DOI | (a): es determinista, está verificado contra el CSV, y deja a `L-E03` y al hito 4 con el identificador de la fuente. Es la única lectura de un valor dentro de una nota |
| H2 | `Cited by` (CSV), `Cited By:` (línea de `N1`) y `Cited by:` (campo `note` del BibTeX) cambian con la fecha de descarga, y `hash_completo` incluye `otros` | (a) volátil: se descarta, y el mismo registro descargado en fechas distintas conserva el mismo hash (ADR-0010, punto 20); (b) se conserva y el hash cambia entre descargas de fechas distintas | (a), con `Export Date:`. El conteo de citas es `nunca_publicable` y no lo usa ningún hito del protocolo. En BibTeX, `note` mezcla el conteo con el estado de acceso abierto: habría que descartar solo el fragmento `Cited by: n`, y se decide al implementarlo |

### Pruebas (archivos sintéticos)

Todos los archivos son sintéticos, con temas ficticios. Las exportaciones reales de prueba nunca se copian a una prueba.

- Por formato: un archivo válido; con BOM; con CRLF; con campos faltantes; con caracteres no ASCII.
- Errores con su número de línea: registro sin cierre, etiqueta fuera de registro, columna ausente, fila con más y con menos columnas que el encabezado, UTF-16 o Latin-1, BibTeX mal formado.
- RIS con cabecera de ACS antes del primer `TY`; `ER` con y sin espacio final; líneas vacías entre registros y al final; líneas de continuación; celdas con saltos de línea y comillas en CSV.
- Web of Science: registro de `PT` a `ER`; `FN` y `VR` de cabecera; archivo sin `EF` y sin salto final; `AU` con un autor por línea, `TI` con líneas unidas con espacio y `OI` cortado dentro de un elemento.
- BibTeX con tildes de LaTeX (`{\'e}`, `{\"u}`, `\~{n}`), `@string` y concatenación con `#` (entre cadenas, con `@string` y con número); valor vacío `{}` (campo ausente); clave repetida recuperada y contada, sin L-E03.
- Varias tandas de una misma búsqueda: suma correcta; identificador repetido dentro de un archivo (L-E03) y entre archivos; DOI repetido sin identificador de la fuente (L-A05); un registro con identificador de la fuente y el mismo DOI que otro no dispara L-A05.
- El mismo registro en dos descargas con distinto `Y2` (ACS) y con distinta línea `Export Date:` de `N1` (Scopus): mismo `hash_completo`.
- `otros`: un campo repetido se une con `"; "`; los volátiles no están en `otros`.
- CSV genérico con mapeo válido (campo, objeto con separador, `id_fuente:lens_id`); con columna inexistente, campo desconocido, lista sin separador, separador en un campo escalar y dos columnas al mismo destino (L-E02); archivo de mapeo ilegible o no JSON (código 1, con el error en `errores` y sin leer el CSV).
- `importar leer`: salida de texto y `--json`; los tres códigos de salida, con un caso por cada causa de la tabla (el 2, con las invocaciones que rechaza el analizador, y el 1, con un archivo inexistente y con otro leído en la misma invocación); que no escribe nada; y que ningún mensaje contiene un valor de campo.

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
   - la configuración de publicación, que debe existir y ser válida (I-E13); un campo sin base completa no impide registrar y se informa como advertencia I-A01 (abajo);
   - la lectura de cada archivo, que debe estar sin errores (I-E07);
   - los archivos ya registrados (I-E05) y los identificadores repetidos (I-E06);
   - el revisor (I-E11);
   - que ningún original quede versionado (I-E10).
2. **Exige una terminal interactiva** (I-E12; ADR-0008, punto 11).
3. **Pide la fecha** (`AAAA-MM-DD`) **y la hora** (`HH:MM`) de la búsqueda, por separado.
   - Propone el desfase del computador para esa fecha, calculado con `astimezone()` sobre la fecha sin zona, y el investigador lo confirma o escribe otro (`±HH:MM`).
   - Si ese desfase difiere del actual, avisa que la fecha cae en otro periodo de horario de verano.
   - Rechaza una fecha futura o anterior a la aprobación del protocolo (I-E04); la fecha de hoy sale de un reloj inyectable, no de `datetime.now()` directo.
4. **Determina la versión del protocolo vigente en esa fecha** y la ecuación esperada (ADR-0010, punto 12), la compara con la ejecutada y clasifica la relación: `identica`, `desviacion` o `adaptacion_generica`. Una desviación sin justificación es I-E09. Una diferencia entre los resultados de la interfaz y los registros leídos sin justificación es I-E08.
5. **Muestra el resumen completo:** fuente, plataforma, institución, cobertura, filtros, lematización, fecha y hora local y UTC, versión del protocolo, las dos ecuaciones con su diferencia y su relación, cada archivo con su hash y su número de registros, los totales frente a la interfaz, las justificaciones, y los campos que se versionarán y los que quedarán solo en local (con el motivo: sin habilitar, base incompleta o nunca publicable).
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
| I-E03 | Retirada (2026-10-04): los campos pendientes ya no bloquean el registro; ver I-A01. El número no se reutiliza |
| I-E04 | La fecha de la búsqueda es futura o anterior a la aprobación del protocolo |
| I-E05 | Un archivo ya está registrado en el estudio (mismo hash) o aparece dos veces en la búsqueda |
| I-E06 | Un identificador de la fuente se repite dentro de un archivo o entre archivos de la búsqueda (es la L-E03 del 2b). Un DOI repetido en registros sin identificador de la fuente es la advertencia L-A05 y no impide registrar |
| I-E07 | Un archivo tiene errores de lectura (L-E) |
| I-E08 | Los registros leídos no coinciden con los resultados de la interfaz y no hay justificación |
| I-E09 | La ecuación de una fuente con traductor se modificó y no hay justificación |
| I-E10 | Un original quedaría versionado, o no se pudo comprobar con Git |
| I-E11 | `--registrado-por` no es un revisor humano declarado en `seleccion.revisores` |
| I-E12 | No hay terminal interactiva |
| I-E13 | `publicacion_datos.yaml` no existe, no se puede leer o no cumple el esquema: un campo `nunca_publicables` en `fuentes`, un campo desconocido o fuera del techo de la fuente, o una base mal formada |

Advertencia (no impide registrar):

| ID | Regla |
|---|---|
| I-A01 | Hay campos que no se versionarán: porque el estudio no los habilita o porque su base está incompleta. Se listan; se importan y se conservan en local |

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
- `politica` `{version, hash}` y `configuracion_publicacion` `{hash}`;
- `version_normalizacion` (la constante `VERSION_NORMALIZACION` del agente con que se normalizó; también va en `importacion.json`);
- `campos_versionados` y `campos_solo_locales` (con el motivo de cada uno);
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

- Cada regla I-E01 a I-E13 (salvo la I-E03, retirada) con un caso que la dispare, sin escribir nada. La I-E13, con el archivo ausente, mal formado, con `resumen` en `fuentes[*].campos` y con un campo desconocido.
- Campos pendientes: una búsqueda con campos `pendiente` o con base incompleta **se registra**, informa I-A01, versiona solo los campos con base completa y conserva los demás en local; los campos `nunca_publicables` no aparecen en ningún archivo versionado, y una configuración que los liste en `fuentes` se rechaza al cargarla (I-E13).
- Registro completo con una terminal simulada:
  - archivos escritos, evento y anclaje;
  - bytes de `registros.jsonl` y `registros.csv` iguales en repeticiones;
  - sin resumen en ningún archivo versionado.
- Fecha y hora:
  - desfase propuesto y corregido;
  - aviso de otro periodo de horario de verano, con el desfase del sistema inyectado;
  - fecha futura y anterior a la aprobación;
  - versión del protocolo vigente en una fecha entre dos enmiendas.
- Ecuación: idéntica; desviación con y sin justificación; adaptación de la genérica; esperada tomada de `ecuaciones.md` y regenerada desde `versiones/`. **La ruta `adaptacion_generica` solo se prueba con datos sintéticos hasta tener datos reales** (ADR-0010, punto 12): el estudio de demostración no usa ACS y su exportación de prueba solo se lee.
- `id_fuente` de tipo `doi` con `doi` sin habilitar: no se versiona y se informa como solo local.
- Varias tandas: suma, identificador repetido entre archivos y archivo ya importado.
- `git check-ignore`: destino ignorado; no ignorado; archivo ya agregado al índice; fuera de un repositorio.
- Atomicidad: un fallo antes del evento deja la carpeta huérfana y el reintento la sobrescribe; un fallo después del evento se reconoce.
- P-E10 con `importacion.json` alterado, `registros.csv` eliminado y números no consecutivos.
- `importar historial`: totales por fuente, originales ausentes y `--json`.
- `ecuaciones.md` con y sin `acs`.

## 2d. Plantillas del estudio

Llegan a los estudios existentes con `estudio actualizar` (ADR-0007, punto 20).

- **`.gitignore`:** agrega `exportaciones_originales/`, con un comentario que remite al ADR-0010.
- **`publicacion_datos.yaml`:** se crea en la raíz del estudio, neutra: con los campos de metadatos habituales y su base incompleta, con `evidencia_literal.resumen` en `no_permitido` y sin `respaldo_nube`, sin nombrar ninguna institución. Es un archivo del estudio: `estudio actualizar` lo crea si no existe y **nunca lo sobrescribe**.
- **`.claude/settings.json`:**
  - `allow`: `importar leer` e `importar historial` (Bash y PowerShell);
  - `deny`: `*agentresearch importar registrar*` (Bash y PowerShell), `Edit(/importaciones/**)` y `Edit(/exportaciones_originales/**)`.

  `importar leer` no coincide con la regla `deny` porque el subcomando es distinto.
- **Skill `/importar`** (`.claude/skills/importar/`, con `disable-model-invocation: true`):
  1. comprueba con `validar` e `historial` que el protocolo esté vigente, sin P-E09 ni P-E10, y que el `.gitignore` ignore `exportaciones_originales/`; si no, explica `estudio actualizar`;
  2. muestra la ecuación de la fuente desde `ecuaciones.md` y los pasos manuales: dónde pegarla, qué filtros aplicar, en qué formato exportar y el máximo por exportación de la base, presentado como «según la documentación consultada, por verificar» (ADR-0010, punto 25), y **el contenido del registro: el completo, con resumen**. La exportación de prueba de Web of Science del 2026-10-13 no traía resumen, lo que habría producido L-A04 en cada registro; la opción de la interfaz que lo incluye se confirma en el 2e;
  3. pide al investigador, una cosa a la vez: plataforma, institución, cobertura, filtros, lematización, la ecuación tal como la ejecutó, los resultados de la interfaz y dónde guardó los archivos;
  4. ejecuta `importar leer` y explica el resultado; si la suma no coincide con la interfaz, pregunta el motivo para la justificación;
  5. prepara `.borradores/busqueda.json` y da el comando exacto de `importar registrar` para la terminal del investigador (PowerShell o la terminal de VS Code), con lo que verá y la frase que debe escribir;
  6. después, verifica con `importar historial`, sugiere el commit con el anclaje en el mensaje y **recuerda guardar los originales** en el equipo y en un respaldo fuera de los servicios de nube compartidos; recomienda la nube institucional solo si `publicacion_datos.yaml` registra `respaldo_nube.<fuente>.estado: permitido` para esa fuente, con su base completa. El respaldo no depende de qué campos se publican (ADR-0010, punto 9);
  7. para ACS, explica su rol (ADR-0010, punto 27): búsquedas complementarias puntuales, descarga por selección o por página como tandas, y nunca herramientas que automaticen la interfaz.
- **`CLAUDE.md` del estudio:** la tabla de comandos incluye `importar leer`, `importar registrar` (solo el investigador) e `importar historial`, y la prueba que compara la tabla con la CLI sigue pasando. Se agrega la regla: los originales y los registros completos no se versionan ni se copian a archivos versionados.
- **`README.md` del estudio:** anuncia `importaciones/` y `exportaciones_originales/`.
- **Pruebas:** contenido esperado de las plantillas; reglas de permisos; que `importar registrar` coincide con la regla `deny` y `importar leer` no; `estudio actualizar` lleva el `.gitignore`, la *skill* y `publicacion_datos.yaml` nuevos a un estudio de `v0.1.0`, y no sobrescribe un `publicacion_datos.yaml` que el estudio ya modificó.

## 2e. Aceptación y cierre de `v0.2.0`

### Antes de empezar

- El investigador completa la comprobación adicional de ACS (ADR-0010, punto 28).
- La confirmación de la Biblioteca (medio, fecha y bases cubiertas) y los campos pendientes de la política **no bloquean** el 2e (ADR-0010, punto 4). Mientras la base de un campo esté incompleta, ese campo se importa en local y no se versiona. Cuando el investigador reciba la confirmación, completa la base en `publicacion_datos.yaml` del estudio.

### Parte A: exportaciones reales de prueba (repositorio del agente)

- El investigador exporta una búsqueda de prueba con pocos registros:
  - Scopus en CSV, RIS y BibTeX;
  - Web of Science en texto plano (.txt), en dos tandas si es posible;
  - ACS en RIS, con uno a tres registros;
  - Lens en CSV.

  Las guarda en `exportaciones_prueba_local/`, que Git ignora.
- Claude Code las lee **solo con `importar leer`**: no se registran ni se versionan. Se comprueba que los conteos coinciden con la interfaz y que las correspondencias de campos son correctas, y se corrigen las tablas de los lectores con lo que revelen (columnas, etiquetas y campos volátiles).
- El investigador anota el máximo por exportación que ofrece cada interfaz, para verificar los de Scopus y Web of Science, que el ADR-0010 (punto 25) deja «por verificar».
- Queda constancia en el ADR-0010, «Aceptación»: formatos, número de registros por archivo, máximos observados, hallazgos y correcciones, sin copiar datos de los registros.
- **Estado tras la verificación estructural del 2026-10-13** (2b, «Verificado con las exportaciones de prueba»). Ya hay Scopus en los tres formatos (5 registros), Web of Science (3, sin resumen) y ACS (1). El 2e debe cerrar lo que esa prueba no pudo verificar:
  - **Web of Science:** repetir la exportación con el contenido de registro completo, para ver `AB`, `DT`, `LA`, `DE`, `ID` y `PM`, y en dos tandas, para probar L-E03 y I-E05 entre archivos; y confirmar el número de registros exportados frente a la selección (la nota decía «seleccionados 1» y el archivo trae 3);
  - **ACS:** un registro con volumen y número, y con palabras clave (`KW`), para fijar `VL`, `IS`, `SP`, `EP` y `KW`; y la respuesta a la comprobación adicional del punto 28 del ADR-0010 (la nota del investigador dice «No permite exportación de metadatos» para más de un artículo: confirmar su alcance);
  - **Lens:** el CSV, que no se pudo exportar, con los nombres de columna reales para el mapeo;
  - **Scopus:** un CSV con celdas de varias líneas y comillas internas, si la búsqueda las produce; y una exportación con un registro sin autores o con un autor de una sola palabra, para ver qué hace cada formato;
  - **BibTeX y RIS:** una exportación con tildes de LaTeX, clave repetida, `#` o líneas de continuación, si alguna base las produce (en la de Scopus del 2026-10-13 no aparecieron: las pruebas sintéticas cubren esos casos);
  - **Máximos por exportación:** no se anotaron el 2026-10-13; siguen «por verificar».

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
- **Notas posteriores del ADR-0003 y del ADR-0004** (hechas el 2026-10-04): «reproducible desde respuestas crudas guardadas» ya no aplica a campos restringidos; la reproducción se apoya en la copia local y en los hashes registrados (ADR-0010, punto 3). Si al aceptar el ADR-0010 cambia ese punto, se agrega otra nota posterior.
- Un ADR nuevo solo si una decisión de implementación lo exige (p. ej. cambiar bibtexparser por un lector propio).

## Criterio de terminado del hito 2

- Sub-hitos 2a a 2e completos, con pruebas.
- Cobertura de al menos 90 % en `registros` e `importacion`, verificada por la integración continua (el `--include` del paso de cobertura de `ci.yml` se amplía a `registros` en el 2a y a `importacion` en el 2b).
- CI en verde en Windows y Ubuntu.
- ADR-0010 aceptado, `arquitectura.md` y `CHANGELOG.md` actualizados.
- Etiqueta `v0.2.0`.
- Exportaciones de prueba leídas con conteos correctos (parte A) y búsquedas del estudio de demostración registradas (parte B).
