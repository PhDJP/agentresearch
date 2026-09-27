# Formatos de los archivos de `.borradores/`

Los archivos que preparas para los comandos van en `.borradores/`, que no se versiona. Su contenido queda registrado en el protocolo o en los eventos. Escríbelos en UTF-8.

## Sección del protocolo: `.borradores/<sección>.yaml`

Una sola clave de primer nivel, la sección, con su contenido **completo**: lo que no esté en el fragmento se elimina del protocolo. Usa la misma forma que `protocolo/protocolo.yaml`, con sangría de 2 espacios y comillas dobles en los textos.

```yaml
criterios:
  inclusion:
    - id: CI1
      texto: "Estudia la obtención o el uso del subproducto."
      fase: titulo_resumen
      tipo: tema
      ejemplos_si: ["Extracción de pectina del subproducto"]
      ejemplos_no: ["Estudio del cultivo sin el subproducto"]
  exclusion:
    - id: CE1
      texto: "No es un estudio primario."
      fase: ambas
      tipo: tipo_documento
      ejemplos_si: ["Una revisión de literatura"]
      ejemplos_no: ["Un estudio experimental"]
```

Una sección de texto (`justificacion`, `objetivos`, `pregunta_general`) es una sola línea:

```yaml
justificacion: "Texto completo de la justificación."
```

Comando: `uv run agentresearch protocolo escribir criterios --archivo .borradores/criterios.yaml`. No se escriben `version_esquema`, `estado` ni `metadatos.version_protocolo`.

## Decisión: `.borradores/decision-<ID>.json`

Entre 2 y 4 opciones, cada una con descripción y al menos un pro, un contra y una referencia. `elegida` es el `id` de una opción. `decidido_por` es un revisor humano declarado en `seleccion.revisores`. `propuesto_por.modelo` es tu identificador exacto (sin alias como «opus»). Usa IDs de decisión cortos y únicos (`D1`, `D2`…). Para corregir una decisión ya registrada, registra otra con `"reemplaza": "<ID anterior>"`.

```json
{
  "id_decision": "D1",
  "tema": "Límites de la población",
  "pregunta": "¿Qué cuenta como subproducto?",
  "opciones": [
    {"id": "A", "descripcion": "…", "pros": ["…"], "contras": ["…"], "referencias": ["Petersen et al. (2015), §5.1.2"]},
    {"id": "B", "descripcion": "…", "pros": ["…"], "contras": ["…"], "referencias": ["…"]}
  ],
  "elegida": "A",
  "justificacion": "Por qué eligió A el investigador, con sus palabras.",
  "propuesto_por": {"tipo": "llm", "modelo": "<tu identificador exacto>"},
  "decidido_por": {"tipo": "humano", "id": "investigador-1"}
}
```

Comando: `uv run agentresearch protocolo decision registrar --archivo .borradores/decision-D1.json`. La decisión queda pendiente hasta que el investigador ejecute en su terminal `uv run agentresearch protocolo decision confirmar --confirmado-por <id>`.

## Justificaciones de advertencias: `.borradores/justificaciones.json`

Una entrada por advertencia activa (al aprobar) o por advertencia nueva (al enmendar), emparejada por `id_regla` y `ubicacion`, tal como salen en `protocolo validar --json`. La justificación es del investigador: redáctala con él.

```json
{
  "justificaciones": [
    {"id_regla": "P-A04", "ubicacion": "estrategias.conjunto_validacion", "justificacion": "…"}
  ]
}
```

Se pasa con `--justificaciones .borradores/justificaciones.json` a `aprobar` o `enmendar`. Si no hay advertencias, se omite la opción. Las que falten se piden en la terminal.

## Enmienda: `.borradores/enmienda.json`

```json
{"justificacion": "Por qué cambia el protocolo.", "efecto_esperado": "Qué cambia en los estudios incluidos o en su clasificación."}
```

Se pasa con `--archivo-enmienda .borradores/enmienda.json` a `protocolo enmendar`.
