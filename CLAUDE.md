# CLAUDE.md - Petramora Source Code

## Proyecto

Sistema de inteligencia comercial para **Petramora** (tienda gourmet española). Dos componentes principales:

1. **Agente_segmentador/** - Agente conversacional IA (Gemini 2.5 Flash) que analiza ~24,363 clientes con segmentación RFM y recomienda acciones comerciales.
2. **ETL-Segmentador-Petramora/** - Pipeline ETL que transforma CSV de Power BI a Supabase.

## Arquitectura

```
Power BI CSV (;-separated, formato europeo)
    → ETL (pandas: limpieza, conversión, filtro mes actual, dedup)
    → Supabase PostgreSQL (3 tablas: segmentacion_clientes_raw, lineas_cliente_producto, catalogo_productos)
    → Agente v6.0 (8 tools via function calling de Gemini)
    → Respuestas en español con tablas markdown
```

## Stack tecnologico

- **Python 3.10+** (Windows)
- **LLM**: Google Gemini (`gemini-2.5-flash` principal, `gemini-2.5-flash-lite` fallback) via `google-genai`
- **Base de datos**: Supabase (PostgreSQL + REST API) via `supabase-py`
- **ETL**: pandas, numpy
- **Reintentos**: tenacity (backoff exponencial, max 3)
- **Config**: python-dotenv (.env)

## Variables de entorno requeridas (.env)

```
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

## Convenciones de codigo

- **Idioma en codigo**: snake_case en ingles para funciones y variables (`get_segment_distribution`), CONSTANT_CASE para constantes (`SEGMENTOS_PRIORIDAD`)
- **Idioma user-facing**: Todo en espanol (prompts, respuestas, nombres de segmentos, comentarios de logica de negocio)
- **Type hints**: Usar en firmas de funciones (`def transform(df: pd.DataFrame) -> pd.DataFrame`)
- **Errores**: Retornar `{"error": f"Mensaje: {str(e)[:100]}"}` en tools; truncar errores largos
- **Patron singleton**: Para cliente Supabase (`get_supabase()` en config.py)
- **Docstrings**: Breves, en espanol para modulos
- **Sin framework de logging**: Prints con prefijo `[Tool: nombre(...)]` + logs a Supabase

## Modelo RFM (9 segmentos)

Prioridades de mayor a menor urgencia:
1. **URGENTE (hoy)**: Champions dormido, Rico perdido
2. **IMPORTANTE (semana)**: Champions casi recurrente, Rico potencial
3. **NORMAL (mes)**: Oportunista con potencial, Oportunista nuevo
4. **BAJA**: Activo Basico, Champion, Oportunista perdido

## Herramientas del agente v6.0 (tools.py)

| Tool | Proposito | Parametros clave |
|------|-----------|-----------------|
| `get_segment_distribution()` | Conteo de clientes por segmento | — |
| `get_segment_metrics(segmento)` | Gasto agregado por segmento | segmento (opcional) |
| `get_actionable_customers(criterio, limite, orden_por)` | Lista priorizada para llamadas comerciales | criterio, limite, orden_por="gasto"\|"recencia" |
| `get_customer_detail(cliente_id)` | Perfil completo con desglose anual | cliente_id |
| `get_customer_products(cliente_id, limite)` | Historial de compras por familia y producto | cliente_id |
| `get_customer_family(cliente_id)` | Familia dominante de compra (>40% = dominante) | cliente_id |
| `get_product_catalog(familia, orden_por, limite)` | Productos activos del catálogo | familia (opcional) |
| `get_recommendation(cliente_id)` | Recomendacion comercial completa + guion llamada | cliente_id |

## Tablas Supabase

| Tabla | Filas aprox. | Uso |
|-------|-------------|-----|
| `segmentacion_clientes_raw` | 24,363 | Snapshot mensual RFM, 1 fila/cliente |
| `lineas_cliente_producto` | ~674K | Historial de compras por linea de factura |
| `catalogo_productos` | ~7,100 | Productos activos (bloqueado=False, precio>0) |

## Limitacion critica: PostgREST max_rows=1,000

Supabase devuelve maximo 1,000 filas por request REST independientemente del `.limit()` del cliente.
**Solucion implementada**: helpers de paginacion en `tools.py`:
- `_fetch_all_rows(supabase, cols, filtro_segmento)` — pagina `segmentacion_clientes_raw`
- `_fetch_all_lines(supabase, cliente_id)` — pagina `lineas_cliente_producto` para un cliente

Estas funciones paginan en batches de 1,000 con `.range()` hasta obtener todos los datos.
**NO usar** `.limit(50000)` directo — el servidor lo ignora.

## Busqueda de clientes — espacios flexibles

Los nombres de clientes en Supabase pueden tener espacios dobles (ej: `"TORREGROSA  VALERO"`).
Gemini normaliza a un solo espacio al enviar nombres via function calling.
**Solucion**: `get_customer_detail` y `_resolver_cliente_id` usan `'%'.join(nombre.split())` para generar patrones ilike flexibles: `%Maria%Jesús%TORREGROSA%VALERO%` matchea independientemente de espacios.

## ETL (etl_segmentador.py)

- Input: `Segmento_RFM_raw.csv` (Power BI export, `;`-separated, formato numerico europeo `1.234,56`)
- Transforma: mapeo de columnas, conversion de formatos, filtro ultimo mes, deduplicacion por `cliente_id`
- Output: Upsert batch (500 registros/batch) a Supabase
- Delete: intento rápido DELETE, fallback TRUNCATE via RPC `truncate_lineas()` para tablas grandes
- Función RPC `truncate_lineas()` creada en Supabase (TRUNCATE TABLE lineas_cliente_producto)

## Tests

```bash
# Tests del agente (60+ tests, integracion con Supabase real)
cd Agente_segmentador
python -m pytest tests/test_agent.py

# Demo de 14 preguntas (v6.0)
python tests/test_demo.py

# Tests de calidad manual
python tests/test_quality.py

# Tests de tools v5 (originales)
python tests/test_tools.py

# Tests de tools v6 (nuevas: productos, familia, catalogo, recomendacion)
python tests/test_tools_v6.py

# Tests de logica RFM del ETL
cd ETL-Segmentador-Petramora
python -m pytest tests/test_rfm_logic.py
```

Los tests son de **integracion** (llaman a Supabase y Gemini reales, no mocks). Usan prints con colores ANSI para output.

## Comandos utiles

```bash
# Instalar dependencias
pip install -r Agente_segmentador/requirements.txt
pip install -r ETL-Segmentador-Petramora/requirements.txt

# Ejecutar el agente (chat interactivo)
python Agente_segmentador/agent.py

# Ejecutar ETL (actualizar Supabase desde CSV)
python ETL-Segmentador-Petramora/etl_segmentador.py
```

## Preferencias de trabajo

- **Explicar antes de ejecutar**: Siempre describir los cambios propuestos (qué archivo, qué línea, qué efecto) y esperar confirmación antes de editar código.

## Reglas de negocio para recomendaciones (`_aplicar_reglas_negocio`)

Dos patrones de seleccion de productos:

### Patron A — Historial propio (segmentos de valor)
**Aplica a:** Champions dormido, Rico perdido, Champion, Champions casi recurrente, Rico potencial

1. Top 5 productos del historial del cliente (por ventas)
2. De esos 5, el de mayor `margen_prom` → Producto recomendado principal
3. Si alguno de los 5 tuvo `descuento_prom > 0` (y no es el mismo), el de mayor margen → Segundo producto con nota de descuento
4. Fallback al catalogo si no hay historial

### Patron B — Top de familia (segmentos de crecimiento)
**Aplica a:** Oportunista con potencial, Activo Basico, Oportunista nuevo

1. `_top_productos_familia(familia)` consulta `lineas_cliente_producto` (top 1,000 transacciones, agrega por producto)
2. Producto 1: el mas vendido de la familia (todos los clientes)
3. Producto 2: de los mas vendidos, el que tiene mas `descuento_prom` real
4. Fallback al catalogo si familia es "Mixto" o no hay datos

### Helper `_top_productos_familia(supabase, familia, limite)`
- Consulta `lineas_cliente_producto` WHERE familia=X, ORDER BY ventas_netas DESC, LIMIT 1000
- Agrega por `codigo_producto` en Python: ventas_total, margen_prom, descuento_prom
- Devuelve top `limite` productos por ventas agregadas

## Reglas importantes

- La tabla `segmentacion_clientes_raw` solo contiene el ultimo corte mensual (snapshot), no historico mes a mes.
- Las tools devuelven `tabla_formateada` (markdown) que el agente debe copiar **exacta** sin redondear ni reescribir.
- El agente usa function calling manual (no `automatic_function_calling`), con loop explicito en `agent.py`.
- `temperature=0.3` para respuestas factuales.
- Siempre filtrar por ultimo `fecha_corte` en queries a Supabase.
- `get_recommendation` orquesta otras tools internamente en Python (no via LLM). El LLM redacta el guion de llamada.
- `orden_por="recencia"` en `get_actionable_customers` ordena por `fecha_ultima_compra DESC` (compra mas reciente primero).
- `_ESTRATEGIA_SEGMENTO["Oportunista perdido"] = None` → `llamada_individual=False`, sin recomendacion de llamada.
- Dos tipos de margen: `margen_prom` (proporcion 0-1 en `lineas_cliente_producto`, multiplicar ×100 al agregar) vs `margen_teorico_pct` (ya en % en `catalogo_productos`).
- `descuento_prom` ya viene en % en `lineas_cliente_producto`. Al agregar, promediar solo lineas con descuento > 0 (no diluir con ceros).

## Patron A de recomendacion (v6.2)

Para segmentos de valor (Champions dormido, Rico perdido, Champion, Champions casi recurrente, Rico potencial):
1. **Producto mas comprado** (mayor ventas del top 5 historial)
2. **Mayor margen** (si es distinto al #1)
3. **Con descuento** (si existe, distinto a #1 y #2)
4. **Completar con catalogo** si hay menos de 3 productos

Cada producto lleva nota explicativa: "Producto mas comprado", "Mayor margen", "Compro con X% dcto", "Recomendado del catalogo".

## Pendientes — Despliegue FastAPI + Frontend

1. [ ] Crear `api.py` — Backend FastAPI con endpoints `/api/chat`, `/api/chat/new`, `/api/health`
2. [ ] Actualizar `requirements.txt` — Añadir fastapi y uvicorn
3. [ ] Crear `Dockerfile` + `.dockerignore` para Cloud Run
4. [ ] Crear frontend React + Vite (chat UI completo)
5. [ ] Probar flujo completo local (uvicorn + vite dev)

Detalle del plan en `plan.md`.

## Datos sucios — Estado actual

### ✅ RESUELTO: `lineas_cliente_producto.margen_prom` — overflow ±10^16

**Causa raíz:** Fórmula DAX `% Margen de ventas col = DIVIDE(Margen, Ventas netas)` explotaba cuando ventas netas ≈ 0 (residuo de punto flotante por descuento 100%). DIVIDE no protege cuando el denominador es ≈0 pero no exactamente 0.

**Fix aplicado (2 partes):**
1. **DAX en Power BI** — `Lineas_Cliente_Producto_Export` ahora filtra `% DESCUENTO < 100` (excluye regalos/muestras) y la fórmula `% Margen de ventas col` usa `IF(ABS(Ventas netas) < 0.01, 0, DIVIDE(...))` para ventas < 1 céntimo
2. **ETL** — `load_to_supabase` ahora usa fallback `TRUNCATE` via RPC (`truncate_lineas()`) cuando el DELETE da timeout en tablas grandes

**Residual:** "Bocadillo de jamón Ibérico" en Cliente genérico TPV tiene margen -156% (venta a pérdida real, no overflow). Solo afecta a TPV que no es un cliente real.

### ✅ RESUELTO: `catalogo_productos.margen_teorico_pct` > 100%

**Causa raíz:** 3 productos con `coste_unitario` negativo en el ERP → margen >100% (Mini Panettone 504%, Lenguado 133%, Toro Joaquina 106%).

**Fix aplicado:** DAX en `Catalogo_Productos_Export` — añadido `&& Productos[COSTE UNITARIO] >= 0` en la condición del `IF` de `MargenTeoricoPct`. Productos con coste negativo ahora tienen margen = 0%.

## Pendientes — test_demo.py

1. [ ] Cambiar "Cliente genérico TPV" por un Champion real (TPV tarda 117s, no es cliente real)
2. [ ] Cambiar "ARREAINVEST S.L" por otro Rico perdido (Gemini le añade punto "S.L." y falla búsqueda)
3. [ ] Validar que la deteccion de error en el test sea mas estricta (ARREAINVEST marco OK cuando fallo)
