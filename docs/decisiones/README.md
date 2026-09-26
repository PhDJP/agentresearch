# Registro de decisiones de arquitectura (ADR)

Cada decisión de diseño relevante queda en un archivo numerado. Una decisión aceptada no se edita: si cambia, se crea un ADR nuevo que la reemplaza y se actualiza el estado del anterior a "Reemplazada por ADR-XXXX". Este registro es parte de la evidencia de reproducibilidad del proyecto.

## Índice

| ADR | Título | Estado | Fecha |
|-----|--------|--------|-------|
| [0001](0001-arquitectura-claude-code-y-paquete-python.md) | Claude Code como cerebro y paquete Python como motor, sin API de pago | Aceptada | 2026-09-25 |
| [0002](0002-marco-metodologico.md) | Marco metodológico: Kitchenham, Petersen y PRISMA-ScR | Aceptada | 2026-09-25 |
| [0003](0003-fuentes-y-formatos.md) | Fuentes de información y formatos de importación | Aceptada | 2026-09-25 |
| [0004](0004-trazabilidad-y-reproducibilidad.md) | Trazabilidad de decisiones y reproducibilidad | Aceptada | 2026-09-25 |
| [0005](0005-ingenieria-idioma-y-publicacion.md) | Ingeniería, idioma y publicación | Aceptada | 2026-09-25 |
| [0006](0006-formato-del-protocolo-y-registro-encadenado.md) | Formato del protocolo y registro encadenado de eventos | Aceptada | 2026-09-26 |
| [0008](0008-ciclo-de-vida-del-protocolo.md) | Ciclo de vida del protocolo | Propuesta | 2026-09-26 |

## Plantilla

```markdown
# ADR-XXXX: Título

- Estado: Propuesta | Aceptada | Reemplazada por ADR-YYYY
- Fecha: AAAA-MM-DD
- Participantes: quién decidió

## Contexto
Qué problema o restricción obliga a decidir.

## Decisión
Qué se decidió, de forma verificable.

## Alternativas consideradas
Cada alternativa y por qué no se eligió.

## Consecuencias
Qué se gana, qué se pierde y qué queda pendiente.
```
