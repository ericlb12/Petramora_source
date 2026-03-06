---
name: session-wrap
description: Actualiza CLAUDE.md y MEMORY.md con el estado actual y genera un resumen compacto para la siguiente sesión
allowed-tools: Read, Edit, Write, Glob, Grep
---

Cierre de sesión: actualiza documentación y genera resumen para continuidad.

## Pasos

1. **Revisar cambios de la sesión**: Leer `CLAUDE.md`, `MEMORY.md` y hacer `git diff` mental de los archivos modificados en esta conversación.

2. **Actualizar CLAUDE.md** (`source_petramora/CLAUDE.md`):
   - Marcar como ✅ RESUELTO los pendientes que se completaron en esta sesión
   - Añadir nuevos pendientes si los hay
   - Actualizar secciones que hayan cambiado (versiones, patrones, reglas de negocio)
   - NO borrar secciones existentes que sigan siendo válidas
   - Mantener el formato y estilo existente

3. **Actualizar MEMORY.md** (auto-memory persistente):
   - Actualizar versión del estado actual
   - Mover items resueltos a la sección ✅ RESUELTO (compactos)
   - Añadir nuevos patrones o decisiones confirmadas
   - Mantener conciso (max 200 líneas)

4. **Generar resumen compacto**: Mostrar al usuario un bloque de texto con este formato:

```
Resumen compacto para el próximo chat
Estado: [versión actual del agente]

Resuelto en esta sesión
[bullet points: qué se resolvió y cómo, 1 línea cada uno]

Archivos modificados
[lista de archivos tocados con descripción breve]

PENDIENTE: [siguiente tarea más importante]
[descripción breve del cambio acordado]

Otros pendientes
[lista breve si hay más]
```

## Reglas
- Ser conciso en las actualizaciones — no duplicar información entre CLAUDE.md y MEMORY.md
- CLAUDE.md es la referencia para nuevos chats (se carga automáticamente)
- MEMORY.md es para contexto adicional que no cabe en CLAUDE.md
- El resumen debe ser copy-pasteable como primer mensaje de la siguiente sesión
