# Plan: FastAPI Backend + Frontend React (Vite)

## Resumen

Envolver el agente existente en una API REST con FastAPI (desplegable en Cloud Run) y crear un frontend chat simple en React + Vite para Vercel. **Sin refactorizar** el agente — solo añadir capas encima.

---

## Estructura de archivos nuevos

```
source_petramora/
├── Agente_segmentador/
│   ├── api.py              ← NUEVO: FastAPI app (endpoints)
│   ├── Dockerfile          ← NUEVO: para Cloud Run
│   ├── .dockerignore       ← NUEVO
│   ├── requirements.txt    ← MODIFICAR: añadir fastapi, uvicorn
│   ├── agent.py            ← SIN CAMBIOS
│   ├── tools.py            ← SIN CAMBIOS
│   ├── prompts.py          ← SIN CAMBIOS
│   └── config.py           ← SIN CAMBIOS
│
└── frontend/               ← NUEVO: proyecto React + Vite
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    ├── .env.example         ← VITE_API_URL=https://...
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx          ← Chat UI principal
    │   ├── App.css
    │   └── components/
    │       └── ChatMessage.tsx  ← Mensaje con markdown renderizado
    └── tsconfig.json
```

---

## Paso 1: Backend FastAPI (`api.py`)

Crear `Agente_segmentador/api.py` con:

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/chat` | Enviar mensaje, recibir respuesta |
| `POST` | `/api/chat/new` | Crear nueva sesión (reset historial) |
| `GET` | `/api/health` | Health check para Cloud Run |

### POST /api/chat
```python
# Request
{"message": str, "session_id": str | None}

# Response
{"session_id": str, "response": str, "tools_called": list, "model_used": str, "latency_ms": int}
```

### Detalles de implementación
- Importar `chat()` directamente de `agent.py` — es la función core, ya maneja todo (history, tools, logging)
- Usar `asyncio.to_thread(chat, ...)` para no bloquear el event loop (las llamadas a Gemini y Supabase son sync)
- CORS middleware habilitado para el dominio de Vercel (y `*` en desarrollo)
- Manejo de errores: try/catch alrededor de `chat()`, devolver HTTP 500 con mensaje

### Dependencias nuevas en requirements.txt
```
fastapi
uvicorn[standard]
```

---

## Paso 2: Dockerfile para Cloud Run

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
```

- Cloud Run usa puerto 8080 por defecto
- Variables de entorno (GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_KEY) se configuran en Cloud Run, no en el Dockerfile
- `.dockerignore` para excluir tests/, __pycache__, .env

---

## Paso 3: Frontend React + Vite (`frontend/`)

Chat simple estilo conversacional:

### UI
- Input de texto abajo + botón enviar
- Historial de mensajes arriba (scrollable)
- Mensajes del usuario a la derecha, del agente a la izquierda
- Markdown renderizado (tablas, negritas, emojis) con `react-markdown` + `remark-gfm`
- Indicador de "pensando..." mientras espera respuesta
- Botón "Nueva conversación" para resetear sesión

### Lógica
- Estado local: `messages[]`, `sessionId`, `isLoading`
- Al enviar mensaje: POST a `${VITE_API_URL}/api/chat` con `{message, session_id}`
- Guardar `session_id` del response para mensajes siguientes
- El historial se persiste en Supabase (lado servidor), el frontend solo muestra la sesión actual

### Stack frontend
- React 18 + TypeScript
- Vite como bundler
- Tailwind CSS (estilos)
- react-markdown + remark-gfm (renderizar tablas markdown)

---

## Paso 4: Configuración de despliegue

### Cloud Run
1. Build imagen Docker desde `Agente_segmentador/`
2. Deploy con variables de entorno: `GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
3. Obtener URL del servicio (ej: `https://petramora-agent-xxxxx.run.app`)

### Vercel
1. Deploy `frontend/` como proyecto React (framework: Vite)
2. Variable de entorno: `VITE_API_URL` = URL de Cloud Run

---

## Orden de implementación

1. **`api.py`** — Backend FastAPI (endpoints + CORS)
2. **`requirements.txt`** — Añadir dependencias
3. **`Dockerfile`** + **`.dockerignore`** — Containerización
4. **`frontend/`** — Proyecto React + Vite completo (chat UI)
5. **Probar local** — uvicorn + npm run dev, verificar flujo completo
