# Especificación del hito 3: conectores de APIs

- **Estado:** propuesta de Claude Code (2026-10-04), con las decisiones del investigador y del asesor sobre fuentes, degradación, AGROVOC y diagnóstico. Se revisa con el asesor antes de programar, y cada sub-hito se revisa antes de implementarlo.
- **Relación con otros documentos:** desarrolla el hito 3 de la [hoja de ruta](../hoja_de_ruta.md) y sus notas. Se apoya en el [ADR-0003](../decisiones/0003-fuentes-y-formatos.md) (con su nota posterior del 2026-10-04, que corrige las condiciones de acceso), en el [ADR-0010](../decisiones/0010-registros-importacion-y-datos-de-terceros.md) (propuesta; datos de terceros) y en el [ADR-0011](../decisiones/0011-degradacion-de-apis-y-copia-local-de-agrovoc.md) (propuesta; degradación y AGROVOC). Si algo aquí contradice un ADR aceptado, prevalece el ADR y se corrige este documento.
- **Nombres provisionales:** los nombres de eventos, carpetas y archivos de esta especificación se fijan al implementar cada sub-hito.

## Objetivo

Al terminar el hito 3, un investigador puede:

1. consultar con el agente las fuentes de API que declara su protocolo, con control de tasa y de presupuesto diario, y con las respuestas crudas completas guardadas en su equipo;
2. saber antes de buscar qué fuentes responden, con qué código y con qué límites, sin que el agente muestre ni guarde sus claves;
3. ante una fuente caída, ver el fallo registrado y decidir qué hacer, sin que el agente cambie de fuente en silencio;
4. obtener registros normalizados (ADR-0010) de cada API, con procedencia, y versionar solo lo que su configuración de publicación habilita.

La aceptación se hace con el estudio de demostración `demo-mucilago-cafe`: su búsqueda en las APIs que declara su protocolo, con respuestas crudas guardadas sin credenciales, más pruebas simuladas (hoja de ruta, «Estrategia de validación»).

## Prerrequisitos

### Del investigador (antes del sub-hito 3a)

- Leer y verificar contra la fuente oficial los **límites y términos de Springer Nature** (el acuerdo de uso de la API; Claude Code no lo verificó) y la **licencia de AGROVOC**, que tiene una discrepancia entre CC-BY 4.0 y CC-BY IGO 3.0 (ADR-0011, punto 13).
- Clave de Semantic Scholar (pendiente) y aceptar su licencia de la API. La clave de NCBI es opcional. Reintentar AGROVOC más adelante. Probar OpenAlex con clave de nuevo si hace falta (ya respondió 200 el 2026-10-04).
- Tener `.env` en el estudio con las claves y el correo que Crossref y NCBI piden. Nada de eso va en el código ni en lo versionado.

### Del agente (primera parte del 3a)

- El **diagnóstico de fuentes** (abajo): todo conector posterior se escribe sabiendo cómo responde de verdad su fuente en el equipo del investigador.

## Reglas comunes

- **Claves y correo.** Viven solo en `.env`, que nunca se versiona ni se muestra. El `.env.ejemplo` versionado solo lleva los nombres de las variables. El correo del investigador (`mailto` de Crossref; `email` de NCBI) se trata como una credencial.
- **Saneo.** Antes de guardar o mostrar cualquier cosa, los conectores quitan `api_key`, `mailto`, `email` y cualquier otra credencial de las URL, los parámetros, los encabezados (incluido `User-Agent`), los mensajes de error, los registros de ejecución y los eventos de la cadena. Una prueba verifica que ni la clave ni el correo aparecen en nada de lo que se guarda (hoja de ruta, notas del hito 3).
- **Respuestas crudas.** Las respuestas completas quedan **solo en el equipo del investigador**, en una carpeta ignorada por Git comprobada con `git check-ignore` (ADR-0010, punto 7), con su hash. En el repositorio van el hash, el conteo y los campos que el estudio habilite en `publicacion_datos.yaml` con su base (ADR-0010, puntos 4 y 5). **Los resúmenes de Crossref no se versionan.**
- **Límites.** Cada conector respeta el ritmo por segundo y el presupuesto diario de su fuente. Los reintentos cuentan para ambos (ADR-0011, punto 3).
- **Degradación.** Se aplica la política del ADR-0011: reintentos con espera, fallo registrado en la cadena y paso a importación manual por decisión del investigador. Nunca se sustituye una fuente en silencio.
- **Los límites de la búsqueda** (periodo, idiomas y tipos de documento) se aplican como parámetros en OpenAlex y PubMed, que `ecuaciones.md` solo lista como texto (ADR-0009, punto 10).
- **Pruebas sin red.** Las llamadas a APIs se simulan; las pruebas en vivo van marcadas aparte y no se ejecutan en la integración continua.
- **Ninguna interfaz se automatiza con credenciales institucionales** (ADR-0003, nota posterior del 2026-09-29).
- Todos los comandos nuevos admiten `--json`, con la forma común del ADR-0008 (punto 26).

## Sub-hitos

Una rama y un PR por sub-hito. Cada uno termina con pruebas en verde y un resumen para la revisión del asesor. Se ordenan por **utilidad** (qué desbloquea) y **riesgo** (qué puede salir mal), poniendo primero lo que todo lo demás necesita y lo ya probado en vivo.

| Sub-hito | Contenido | Utilidad | Riesgo | Esfuerzo sugerido |
|---|---|---|---|---|
| 3a | Interfaz común, caché local de respuestas crudas, control de tasa y de presupuesto, claves en `.env` con saneo, degradación (ADR-0011) y diagnóstico de fuentes | desbloquea todo | alto: es la base y concentra el saneo de credenciales | Alto |
| 3b | OpenAlex y Crossref | fuente principal de búsqueda y de metadatos por DOI; alimenta los hitos 4 y 6 | bajo: respondieron 200 sin clave y OpenAlex con clave | Medio |
| 3c | PubMed | segunda fuente de búsqueda, de la que ya hay prueba con clave | bajo | Medio |
| 3d | Semantic Scholar | bola de nieve (hito 6) | medio: exige clave y su licencia, y sin clave el grupo compartido estaba saturado | Medio |
| 3e | Springer Nature OA y AGROVOC | texto completo abierto y sinónimos de la ecuación PCC | medio a alto: cuota diaria baja en Springer y servicios de AGROVOC caídos | Alto |

Al cerrar el 3e se etiqueta `v0.3.0`. Una fuente cuya verificación falla se omite según su criterio (abajo) y no impide cerrar el hito, salvo el 3a y el 3b, que son el mínimo.

## 3a. Base común y diagnóstico de fuentes

**Módulo `agentresearch.fuentes`.** Sin dependencias nuevas salvo que el 3a justifique una (CLAUDE.md).

### Interfaz común

- Una clase base de conector con `buscar`, `obtener` y `diagnosticar`, y un resultado que lleva la consulta saneada, los parámetros, la fecha y hora UTC, el código HTTP, los encabezados de límite, el hash de la respuesta cruda y su ruta local.
- Cada conector declara sus límites (por segundo, por minuto y diario) como datos y la forma en que se autentica.

### Caché local de respuestas crudas

- Carpeta del estudio ignorada por Git, una respuesta por archivo, con su hash.
- Una consulta idéntica con parámetros idénticos puede reutilizar la caché y el resultado lo declara («caché», con la fecha de la respuesta original); nunca la presenta como consulta nueva (ADR-0011, punto 7).
- **Para Springer la caché es obligatoria** (propuesta; 3e).

### Control de tasa y presupuesto

- Ritmo por segundo y por minuto por fuente.
- **Presupuesto diario persistente:** un contador por fuente y por día (UTC o el que use la fuente) que sobrevive entre ejecuciones, para fuentes con tope diario (Springer: 500). Si el contador no basta para la búsqueda estimada, el conector informa y no consume el resto sin que el investigador lo decida.
- Los encabezados de límite que devuelva la fuente (p. ej. `X-RateLimit-Remaining` de OpenAlex) se guardan con la respuesta, porque no contienen credenciales. Si una fuente no los devuelve (Springer), el presupuesto se cuenta localmente.

### Claves en `.env`, con saneo

- Lectura de `.env` con las variables declaradas en `.env.ejemplo`; la ausencia de una clave opcional no es un error.
- Saneo central (reglas comunes), con una prueba que busque la clave y el correo de prueba en todo lo guardado, incluidos los eventos, los mensajes de error y las excepciones.

### Degradación

- Reintentos, `consulta_fallida` y `decision_degradacion` según el ADR-0011 (puntos 2 a 8), con valores por defecto de intentos, esperas y umbral de persistencia que se fijan y documentan aquí.

### `agentresearch fuentes diagnosticar [--fuente ID]... [--json] [--estudio RUTA]`

**Qué hace.** Una consulta mínima, de un resultado como máximo, a cada fuente configurada, para saber cómo responde en el equipo del investigador.

- **Fuentes:** las declaradas con `tipo: api` en el protocolo del estudio, más AGROVOC. AGROVOC, con la copia local como vía principal (ADR-0011), se diagnostica así: si la copia local existe y coincide con su nota de versión (sin red) y, si el investigador lo pide, la disponibilidad del REST con las dos consultas mínimas del ADR-0011 (punto 18).
- **Por fuente informa:**
  - el código HTTP, o el fallo de red o el tiempo agotado, y el tiempo de respuesta;
  - **los encabezados de límite** presentes en la respuesta, con su valor (p. ej. los cuatro `X-RateLimit-*` de OpenAlex, incluido `X-RateLimit-Credits-Used`, que mide la unidad del presupuesto), o «sin encabezados de límite» si no hay;
  - **si la clave existe: «presente» o «ausente».** Nunca el valor, ni su longitud, ni ningún fragmento. Lo mismo para el correo;
  - la fecha y hora UTC y la versión del agente.
- **Encabezados:** se guardan solo los de una lista permitida (límites, reintento y reinicio del presupuesto), no el resto de la respuesta. Una lista permitida es más segura que una de excluidos, porque un encabezado nuevo con una credencial no se guardaría.
- **Dónde se guarda.** Solo en el equipo del investigador, en una carpeta ignorada del estudio (`diagnostico_local/`; decisión D3 del investigador), con la misma comprobación de `git check-ignore`. No se versiona, y la plantilla del estudio agrega la carpeta al `.gitignore`. El diagnóstico no es un registro de la búsqueda del estudio.
- **Quién lo ejecuta.** El investigador o Claude Code: la regla de permisos del estudio lo permite, porque no imprime secretos y solo hace una consulta mínima por fuente.
- **Salida:** código 0 si se completa el diagnóstico, aunque alguna fuente falle (el fallo de una fuente es un resultado, no un error del comando); 1 si no se pudo completar o escribir; 2 si los argumentos no son válidos.

**Costo en cuota.** Unas 7 solicitudes por ejecución: una a OpenAlex, una a Crossref, una a PubMed, una a Semantic Scholar (un solo intento, sin reintentos, para no cargar el grupo común), una a Springer (de sus 500 diarias) y dos al REST de AGROVOC si se pide. Es poco frente a los límites publicados, y no usa el plan de Claude porque no consulta al LLM. El gasto de OpenAlex en su unidad de presupuesto es lo que el diagnóstico debe medir (ADR-0003, nota posterior).

**Criterio de aceptación.** El diagnóstico **reproduce lo que vio el investigador** el 2026-10-04: el mismo código HTTP y la misma presencia o ausencia de encabezados de límite (p. ej., OpenAlex con clave: 200 y `X-RateLimit-Remaining` presente; Springer con clave: 200 y sin encabezados de límite; Semantic Scholar sin clave: 429 o tiempo agotado; REST de AGROVOC: error 5xx cuando el servicio está caído). Se comprueba con pruebas simuladas y con una prueba en vivo marcada aparte, que el investigador ejecuta en su equipo.

### Pruebas

- Interfaz común: un conector simulado con éxito, con fallo transitorio, con fallo permanente y con límite excedido.
- Control de tasa: ritmo respetado con un reloj inyectado; presupuesto diario que sobrevive entre ejecuciones y se reinicia al cambiar el día.
- Saneo: una clave y un correo de prueba no aparecen en las URL, los parámetros, los encabezados, la caché, los mensajes de error, los eventos ni el diagnóstico.
- Degradación: cada fila de la tabla de verificación del ADR-0011 (reintentos acotados, evento escrito sin credenciales, paso a importación manual con enmienda, sin sustitución silenciosa, caché etiquetada).
- Caché: acierto, fallo y respuesta identificada como de caché.
- Diagnóstico: cada fuente con éxito, con fallo y sin clave; solo los encabezados permitidos; escritura únicamente en la carpeta ignorada; comprobación de `git check-ignore`.

## 3b. OpenAlex y Crossref

- **OpenAlex:** búsqueda con la ecuación traducida en el hito 1 (ADR-0009), con los límites de la búsqueda como parámetros. `per_page` máximo 100; el paginado básico llega a 10 000 resultados y, para más, se usa el paginado por cursor. Se guardan los encabezados `X-RateLimit-*`. La clave es opcional pero recomendada (ADR-0003, nota posterior).
- **Crossref:** completa metadatos por DOI y apoya la deduplicación del hito 4. Usa el grupo *polite* con el correo del investigador tomado de `.env`, saneado de todo lo que se guarda. **Los resúmenes de Crossref no se versionan.** La licencia de sus metadatos se verifica al implementar.
- Normalizan sus respuestas al registro del ADR-0010 (con fuente `openalex` o `crossref` y su identificador de la fuente).
- **Criterio de omisión:** ninguno. Son el mínimo del hito, junto con el 3a.

## 3c. PubMed

- E-utilities con `tool` y `email` tomados de `.env`, saneados de lo guardado. Ritmo de 3 solicitudes por segundo sin clave y 10 con clave.
- Los trabajos grandes se recomiendan en fin de semana o entre las 21:00 y las 05:00, hora del Este: el conector **avisa** cuando la búsqueda estimada es grande y propone ese horario. No lo programa ni lo impone.
- Los resúmenes de PubMed no se versionan (ADR-0010).
- Los límites de la búsqueda se aplican como parámetros.
- **Criterio de omisión:** ninguno previsto; PubMed respondió 200 sin clave y con clave. Las cifras de NCBI las verificó el asesor y Claude Code no pudo reconsultarlas (reCAPTCHA): se reverifican contra la guía oficial NBK25497 al implementar, y si no es posible se deja constancia de que se usan las del asesor.

## 3d. Semantic Scholar

- Búsqueda, referencias y citas para la bola de nieve del hito 6. Exige clave (1 solicitud por segundo) y que el investigador acepte la licencia de la API: esa aceptación no se automatiza.
- Se decide aquí si necesita un traductor propio de ecuaciones o si usa la genérica (hoja de ruta, nota del hito 3).
- **Criterio de omisión:** sin clave no se intenta como vía principal. El grupo compartido sin clave estaba saturado (ADR-0003, nota posterior). Si el investigador no tiene la clave al llegar al 3d, la fuente se omite de `v0.3.0` con la razón escrita, el hito 6 hace la bola de nieve solo con OpenAlex, y se declara la limitación.

## 3e. Springer Nature OA y AGROVOC

### Springer Nature OA

- Metadatos y texto de artículos de acceso abierto. Tamaño máximo de página `p` = 20, con el inicio en `s`, una clave por usuario que **viaja en la URL** (el asesor las verificó). Por eso la clave se quita de toda URL guardada, de la cadena de eventos y de los mensajes (reglas comunes).
- **Presupuesto diario de 500 consultas** (plan Basic, con 100 por minuto) y no solo el ritmo por minuto: el control de tasa del 3a lo cuenta, y el conector informa cuántas quedan y cuántas necesita la búsqueda estimada.
- **La caché de respuestas crudas es obligatoria** (propuesta), para no gastar la cuota repitiendo una consulta.
- La licencia Creative Commons de cada artículo rige el uso de su contenido, y el conector la registra por artículo. El acuerdo de uso de la API lo leyó el investigador; no se cita como verificado por Claude Code.
- **Criterio de omisión:** si el investigador no confirma las condiciones de uso antes del 3e, o si la cuota diaria no alcanza para la búsqueda del estudio y el investigador decide no repartirla en varios días, Springer se omite de `v0.3.0` con la razón escrita y se declara la limitación.

### AGROVOC

- Copia local descargada, con su nota de versión y su hash, como vía principal; el REST de Skosmos, solo como apoyo opcional, con `maxhits` siempre fijo, `offset` y `unique=true` (ADR-0011, puntos 11 a 18).
- Antes de implementar se verifican con el archivo real el formato, el tamaño descomprimido y el nombre del archivo oficial, y el investigador confirma la licencia.
- Propone sinónimos para la ecuación PCC: es una propuesta que el investigador decide (regla 9), y registra la nota de versión que usó.
- **Criterio de omisión:** el del ADR-0011 (punto 19): si la licencia no se confirma, el formato o el tamaño no coinciden o el investigador no valida la descarga, se omite de `v0.3.0` con la razón escrita y el estudio propone los sinónimos sin tesauro.

## ADR que el hito 3 debe producir

- **ADR-0011** (degradación y AGROVOC): propuesta ahora; se acepta al cerrar el 3e, con su sección «Aceptación».
- **Nota posterior del ADR-0003** al cerrar el hito, con las condiciones reverificadas al implementar cada conector (hoja de ruta, hito 3).
- Un ADR nuevo solo si una decisión de implementación lo exige (p. ej. una dependencia de RDF).

## Criterio de terminado del hito 3

- Sub-hitos 3a a 3e completos o con su omisión documentada, con pruebas.
- Cobertura de al menos 90 % en `fuentes`, verificada por la integración continua.
- CI en verde en Windows y Ubuntu.
- ADR-0011 aceptado, `arquitectura.md` y `CHANGELOG.md` actualizados.
- Etiqueta `v0.3.0`.
- Búsqueda del estudio de demostración en las APIs que declara, con respuestas crudas guardadas en local sin credenciales, y el diagnóstico de fuentes reproduciendo lo observado.
