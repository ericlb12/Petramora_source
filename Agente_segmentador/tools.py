"""
Tools del Agente Segmentador v6.0
- Priorización inteligente por segmento:
  - Dormidos/Perdidos: mayor gasto reciente + más días sin comprar
  - Activos/Potencial: mayor gasto reciente + compra más reciente
- Usa columnas gasto_total y gasto_reciente de Supabase (ORDER BY directo)
- Todas las tools devuelven "tabla_formateada" con markdown listo
- v6.0: tools de productos (historial, familia, catálogo, recomendación)
"""

from datetime import datetime, date
from config import get_supabase


# ─────────────────────────────────────────────
# PRIORIDAD Y ACCIONES POR SEGMENTO
# ─────────────────────────────────────────────

SEGMENTOS_PRIORIDAD = [
    {
        "segmento": "Champions dormido",
        "prioridad": "🔴 URGENTE — Llamar HOY",
        "accion": "Llamada de relación, no de venta. Preguntar cómo va todo, detectar si hay un problema. Gastaban mucho y se están enfriando.",
        "orden": "recuperar",
    },
    {
        "segmento": "Rico perdido",
        "prioridad": "🔴 URGENTE — Llamar HOY",
        "accion": "Llamada de recuperación. Entender qué pasó, si hubo problema con el servicio o se fueron a la competencia. Considerar condiciones especiales.",
        "orden": "recuperar",
    },
    {
        "segmento": "Champions casi recurrente",
        "prioridad": "🟡 IMPORTANTE — Llamar esta semana",
        "accion": "Llamada de desarrollo. Ofrecer productos complementarios, proponer pedido recurrente. Son buenos clientes activos que podrían comprar más.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Rico potencial",
        "prioridad": "🟡 IMPORTANTE — Llamar esta semana",
        "accion": "Seguimiento post-primera compra grande. Preguntar cómo les fue con el producto, abrir puerta a pedidos regulares.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Oportunista con potencial",
        "prioridad": "🟢 NORMAL — Llamar este mes",
        "accion": "Entender su negocio. ¿Compran poco porque no necesitan más o porque compran el resto en otro sitio? Oportunidad de ampliar catálogo.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Oportunista nuevo",
        "prioridad": "🟢 NORMAL — Llamar este mes",
        "accion": "Seguimiento post-venta básico. ¿Quedaron satisfechos? ¿Conocen el resto del catálogo? Sin presionar.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Activo Básico",
        "prioridad": "⚪ BAJO — Mantenimiento",
        "accion": "No requieren llamada urgente. Candidatos a campañas de upselling por email o WhatsApp.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Champion",
        "prioridad": "⚪ BAJO — Fidelización",
        "accion": "No necesitan llamada de venta. Llamada de agradecimiento y fidelización. Ya son los mejores clientes.",
        "orden": "desarrollar",
    },
    {
        "segmento": "Oportunista perdido",
        "prioridad": "⚪ BAJO — Solo campañas masivas",
        "accion": "Compraban poco y se fueron. No merece llamada individual. Incluir en campañas masivas de reactivación.",
        "orden": "recuperar",
    },
]

SEGMENTO_INFO = {s["segmento"]: s for s in SEGMENTOS_PRIORIDAD}

SEGMENTOS_LLAMAR_HOY = [
    "Champions dormido",
    "Rico perdido",
    "Champions casi recurrente",
    "Rico potencial",
]


def _calcular_dias_recencia(fecha_ultima_compra_str: str) -> int:
    if not fecha_ultima_compra_str:
        return 9999
    try:
        fecha = datetime.strptime(str(fecha_ultima_compra_str), '%Y-%m-%d').date()
        return (date.today() - fecha).days
    except (ValueError, TypeError):
        return 9999


def _calcular_gasto_historico(row: dict) -> float:
    return round(
        float(row.get('ventas_2024') or 0) +
        float(row.get('ventas_2025') or 0) +
        float(row.get('ventas_2026') or 0),
        2
    )


def _calcular_facturas_historico(row: dict) -> int:
    return (
        int(row.get('facturas_2024') or 0) +
        int(row.get('facturas_2025') or 0) +
        int(row.get('facturas_2026') or 0)
    )


# ─────────────────────────────────────────────
# TOOLS PRINCIPALES
# ─────────────────────────────────────────────

COLS_BASE = 'cliente_id, segmento_rfm, fecha_ultima_compra, ventas_2024, ventas_2025, ventas_2026, facturas_2024, facturas_2025, facturas_2026, gasto_total, gasto_reciente'


def _fetch_all_rows(supabase, select_cols: str, filtro_segmento: str = None) -> list:
    """
    Pagina automáticamente segmentacion_clientes_raw en batches de 1,000.
    Necesario porque PostgREST tiene max_rows=1,000 por request.
    """
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        q = supabase.table('segmentacion_clientes_raw').select(select_cols)
        if filtro_segmento:
            q = q.eq('segmento_rfm', filtro_segmento)
        response = q.range(offset, offset + batch - 1).execute()
        if not response.data:
            break
        all_rows.extend(response.data)
        if len(response.data) < batch:
            break
        offset += batch
    return all_rows


_COLS_LINEAS = 'familia, ventas_netas, codigo_producto, descripcion, margen_prom, descuento_prom'


def _fetch_all_lines(supabase, cliente_id: str) -> list:
    """
    Pagina todas las líneas de un cliente en lineas_cliente_producto.
    Necesario porque PostgREST tiene max_rows=1,000 por request.
    """
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        response = (
            supabase.table('lineas_cliente_producto')
            .select(_COLS_LINEAS)
            .eq('cliente_id', cliente_id)
            .range(offset, offset + batch - 1)
            .execute()
        )
        if not response.data:
            break
        all_rows.extend(response.data)
        if len(response.data) < batch:
            break
        offset += batch
    return all_rows


def _top_productos_familia(supabase, familia: str, limite: int = 10) -> list:
    """
    Top productos de una familia por ventas agregadas (todos los clientes).
    Muestra las 1,000 transacciones más altas y agrega por producto.
    """
    response = (
        supabase.table('lineas_cliente_producto')
        .select(_COLS_LINEAS)
        .eq('familia', familia)
        .order('ventas_netas', desc=True)
        .limit(1000)
        .execute()
    )
    if not response.data:
        return []

    productos: dict[str, dict] = {}
    for l in response.data:
        key = l.get('codigo_producto') or ''
        v = float(l.get('ventas_netas') or 0)
        m = float(l.get('margen_prom') or 0)
        d = float(l.get('descuento_prom') or 0)
        if key not in productos:
            productos[key] = {
                'codigo_producto': key,
                'descripcion': l.get('descripcion', ''),
                'familia': familia,
                'ventas_total': 0.0,
                'margen_sum': 0.0,
                'descuento_sum': 0.0,
                'lineas': 0,
            }
        productos[key]['ventas_total'] += v
        productos[key]['margen_sum'] += m
        productos[key]['descuento_sum'] += d
        productos[key]['lineas'] += 1

    result = []
    for p in sorted(productos.values(), key=lambda x: -x['ventas_total'])[:limite]:
        n = p['lineas']
        result.append({
            'codigo_producto': p['codigo_producto'],
            'descripcion': p['descripcion'],
            'familia': p['familia'],
            'ventas_total': round(p['ventas_total'], 2),
            'margen_prom': round(p['margen_sum'] / n * 100, 1) if n else 0,
            'descuento_prom': round(p['descuento_sum'] / n, 1) if n else 0,
        })

    return result


def get_segment_distribution() -> dict:
    supabase = get_supabase()
    rows = _fetch_all_rows(supabase, 'segmento_rfm')

    if not rows:
        return {"error": "No se obtuvieron datos"}

    total = len(rows)

    segmentos = {}
    for row in rows:
        seg = row['segmento_rfm'] or 'Sin Clasificar'
        segmentos[seg] = segmentos.get(seg, 0) + 1

    por_segmento = {
        seg: {"clientes": c, "porcentaje": round(c / total * 100, 1)}
        for seg, c in sorted(segmentos.items(), key=lambda x: x[1], reverse=True)
    }

    lines = ["| Segmento | Clientes | Porcentaje |", "|:---|---:|---:|"]
    for seg, d in por_segmento.items():
        lines.append(f"| {seg} | {d['clientes']:,} | {d['porcentaje']}% |")

    return {
        "total_clientes": total,
        "por_segmento_rfm": por_segmento,
        "tabla_formateada": f"**Distribución actual — {total:,} clientes totales**\n\n" + "\n".join(lines),
    }


def get_segment_metrics(segmento: str = None) -> dict:
    supabase = get_supabase()
    rows = _fetch_all_rows(supabase, COLS_BASE, filtro_segmento=segmento)

    if not rows:
        return {"error": f"No hay datos{' para ' + segmento if segmento else ''}"}

    metricas = {}
    gasto_global = 0
    for row in rows:
        seg = row['segmento_rfm'] or 'Sin Clasificar'
        gasto_hist = _calcular_gasto_historico(row)
        facturas_hist = _calcular_facturas_historico(row)
        gasto_global += gasto_hist

        if seg not in metricas:
            metricas[seg] = {'clientes': 0, 'gasto_total': 0, 'facturas_total': 0}
        metricas[seg]['clientes'] += 1
        metricas[seg]['gasto_total'] += gasto_hist
        metricas[seg]['facturas_total'] += facturas_hist

    metricas = dict(sorted(metricas.items(), key=lambda x: x[1]['gasto_total'], reverse=True))

    resultado = {}
    for seg, d in metricas.items():
        n = d['clientes']
        resultado[seg] = {
            'clientes': n,
            'gasto_total': round(d['gasto_total'], 2),
            'porcentaje_gasto': round(d['gasto_total'] / gasto_global * 100, 1) if gasto_global else 0,
            'gasto_promedio': round(d['gasto_total'] / n, 2) if n else 0,
            'facturas_promedio': round(d['facturas_total'] / n, 1) if n else 0,
        }

    lines = [
        "| Segmento | Clientes | Gasto histórico (€) | % Gasto | Gasto prom. (€) | Facturas prom. |",
        "|:---|---:|---:|---:|---:|---:|"
    ]
    for seg, d in resultado.items():
        lines.append(
            f"| {seg} | {d['clientes']:,} | {d['gasto_total']:,.2f} | "
            f"{d['porcentaje_gasto']}% | {d['gasto_promedio']:,.2f} | {d['facturas_promedio']} |"
        )

    titulo = f"**Métricas por segmento — Gasto histórico total: {gasto_global:,.2f}€**"
    nota = "\n\n_Nota: El gasto mostrado es el acumulado histórico (2024+2025+2026), no solo del mes actual._"

    return {
        "segmento_filtrado": segmento or "Todos",
        "gasto_total_global": round(gasto_global, 2),
        "metricas_por_segmento": resultado,
        "tabla_formateada": titulo + "\n\n" + "\n".join(lines) + nota,
    }


def get_actionable_customers(criterio: str = "today", limite: int = 10, orden_por: str = "gasto") -> dict:
    supabase = get_supabase()
    if criterio == "today":
        return _actionable_today(supabase, limite, orden_por)
    elif criterio == "all_segments":
        return _actionable_all_segments(supabase, limite, orden_por)
    elif criterio in SEGMENTO_INFO:
        # Nombre de segmento exacto — filtra solo ese segmento con orden_por respetado
        return _actionable_single_segment(supabase, criterio, limite, orden_por)
    else:
        return _actionable_by_filter(supabase, criterio, limite, orden_por)


def _query_segmento_priorizado(supabase, segmento: str, limite: int, orden_por: str = "gasto") -> list:
    """
    Trae top N clientes con ORDER BY configurable:
    - orden_por="gasto" (default): gasto_reciente DESC + urgencia natural del segmento
    - orden_por="recencia": fecha_ultima_compra DESC (compra más reciente primero)
    """
    query = (
        supabase.table('segmentacion_clientes_raw')
        .select(COLS_BASE)
        .eq('segmento_rfm', segmento)
    )

    if orden_por == "recencia":
        query = query.order('fecha_ultima_compra', desc=True)
    else:
        seg_info = SEGMENTO_INFO.get(segmento, {})
        tipo_orden = seg_info.get("orden", "desarrollar")
        query = query.order('gasto_reciente', desc=True)
        if tipo_orden == "recuperar":
            query = query.order('fecha_ultima_compra', desc=False)
        else:
            query = query.order('fecha_ultima_compra', desc=True)

    response = query.limit(limite).execute()

    clientes = []
    for row in (response.data or []):
        clientes.append({
            "cliente_id": row['cliente_id'],
            "segmento_rfm": segmento,
            "gasto_historico": float(row.get('gasto_total') or 0),
            "gasto_reciente": float(row.get('gasto_reciente') or 0),
            "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
        })
    return clientes


def _actionable_single_segment(supabase, segmento: str, limite: int, orden_por: str) -> dict:
    """
    Devuelve clientes de un único segmento con orden_por respetado.
    Usa _query_segmento_priorizado (ORDER BY server-side), por lo que
    orden_por="recencia" trae los más recientes sin importar su gasto.
    """
    info = SEGMENTO_INFO[segmento]
    clientes = _query_segmento_priorizado(supabase, segmento, limite, orden_por)
    grupos = [{
        "segmento": segmento,
        "prioridad": info["prioridad"],
        "accion": info["accion"],
        "clientes": clientes,
    }]
    tabla = _formatear_tabla_agrupada(grupos)
    return {
        "criterio": segmento,
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes),
        "grupos": grupos,
        "clientes": clientes,
        "tabla_formateada": tabla,
    }


def _actionable_today(supabase, limite: int, orden_por: str = "gasto") -> dict:
    grupos = []
    clientes_total = []

    for segmento in SEGMENTOS_LLAMAR_HOY:
        info = SEGMENTO_INFO[segmento]
        clientes_seg = _query_segmento_priorizado(supabase, segmento, limite, orden_por)
        if not clientes_seg:
            continue
        grupos.append({
            "segmento": segmento,
            "prioridad": info["prioridad"],
            "accion": info["accion"],
            "clientes": clientes_seg,
        })
        clientes_total.extend(clientes_seg)

    tabla = _formatear_tabla_agrupada(grupos)
    return {
        "criterio": "today",
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes_total),
        "grupos": grupos,
        "clientes": clientes_total,
        "tabla_formateada": tabla,
    }


def _actionable_all_segments(supabase, limite: int, orden_por: str = "gasto") -> dict:
    grupos = []
    clientes_total = []

    for seg_info in SEGMENTOS_PRIORIDAD:
        segmento = seg_info["segmento"]
        clientes_seg = _query_segmento_priorizado(supabase, segmento, limite, orden_por)
        grupos.append({
            "segmento": segmento,
            "prioridad": seg_info["prioridad"],
            "accion": seg_info["accion"],
            "clientes": clientes_seg,
        })
        clientes_total.extend(clientes_seg)

    tabla = _formatear_tabla_agrupada(grupos)
    return {
        "criterio": "all_segments",
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes_total),
        "grupos": grupos,
        "clientes": clientes_total,
        "tabla_formateada": tabla,
    }


def _actionable_by_filter(supabase, criterio: str, limite: int, orden_por: str = "gasto") -> dict:
    if criterio == "churn_risk":
        segmentos_filtro = ['Champion', 'Champions casi recurrente']
    elif criterio == "growth_potential":
        segmentos_filtro = ['Oportunista con potencial', 'Activo Básico']
    elif criterio == "inactive_vip":
        segmentos_filtro = ['Rico perdido', 'Champions dormido']
    elif criterio == "new_high_value":
        segmentos_filtro = ['Rico potencial', 'Oportunista nuevo']
    elif criterio == "top_historical":
        segmentos_filtro = None
    else:
        segmentos_filtro = None

    query = supabase.table('segmentacion_clientes_raw').select(COLS_BASE)

    if criterio == "top_historical":
        response = query.order('gasto_total', desc=True).limit(limite * 5).execute()
    elif orden_por == "recencia":
        if segmentos_filtro:
            query = query.in_('segmento_rfm', segmentos_filtro)
        query = query.order('fecha_ultima_compra', desc=True)
        response = query.limit(limite * 2).execute()
    else:
        if segmentos_filtro:
            query = query.in_('segmento_rfm', segmentos_filtro)
        query = query.order('gasto_reciente', desc=True)
        response = query.limit(limite * 2).execute()

    clientes = []
    for row in (response.data or []):
        gasto_hist = float(row.get('gasto_total') or 0) or _calcular_gasto_historico(row)
        gasto_rec = float(row.get('gasto_reciente') or 0)
        if criterio in ("growth_potential", "new_high_value") and gasto_hist < 138:
            continue
        clientes.append({
            "cliente_id": row['cliente_id'],
            "segmento_rfm": row['segmento_rfm'],
            "gasto_historico": gasto_hist,
            "gasto_reciente": gasto_rec,
            "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
        })

    if criterio == "top_historical":
        clientes.sort(key=lambda x: -x['gasto_historico'])
    elif orden_por == "recencia":
        clientes.sort(key=lambda x: x['dias_recencia'])  # ASC: menos días = compra más reciente
    else:
        clientes.sort(key=lambda x: -x['gasto_reciente'])
    clientes = clientes[:limite]

    grupos_dict = {}
    for c in clientes:
        seg = c['segmento_rfm']
        if seg not in grupos_dict:
            info = SEGMENTO_INFO.get(seg, {"prioridad": "", "accion": ""})
            grupos_dict[seg] = {
                "segmento": seg,
                "prioridad": info.get("prioridad", ""),
                "accion": info.get("accion", ""),
                "clientes": [],
            }
        grupos_dict[seg]["clientes"].append(c)

    orden_segmentos = [s["segmento"] for s in SEGMENTOS_PRIORIDAD]
    grupos = sorted(
        grupos_dict.values(),
        key=lambda g: orden_segmentos.index(g["segmento"]) if g["segmento"] in orden_segmentos else 99
    )

    titulo_map = {
        "churn_risk": "Clientes en riesgo de fuga",
        "growth_potential": "Clientes con potencial de crecimiento",
        "inactive_vip": "VIPs inactivos",
        "new_high_value": "Nuevos clientes de alto valor",
        "top_historical": f"Top {len(clientes)} clientes por gasto histórico",
    }
    titulo = titulo_map.get(criterio, criterio)
    tabla = _formatear_tabla_agrupada(grupos, titulo_override=titulo)

    return {
        "criterio": criterio,
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes),
        "grupos": grupos,
        "clientes": clientes,
        "tabla_formateada": tabla,
    }


def _formatear_tabla_agrupada(grupos: list, titulo_override: str = None) -> str:
    hoy = date.today().isoformat()
    titulo = titulo_override or f"Clientes a contactar ({hoy})"
    lines = [f"**{titulo}**\n"]

    for grupo in grupos:
        if not grupo["clientes"]:
            continue

        segmento = grupo["segmento"]
        prioridad = grupo["prioridad"]
        accion = grupo["accion"]
        n_clientes = len(grupo["clientes"])

        lines.append(f"### {prioridad}")
        lines.append(f"**{segmento}** ({n_clientes} clientes)")
        lines.append(f"_Acción: {accion}_\n")
        lines.append("| # | Cliente | Gasto reciente (€) | Gasto histórico (€) | Días sin comprar |")
        lines.append("|---:|:---|---:|---:|---:|")

        for i, c in enumerate(grupo["clientes"], 1):
            lines.append(
                f"| {i} | {c['cliente_id']} | {c.get('gasto_reciente', 0):,.2f} | {c['gasto_historico']:,.2f} | {c['dias_recencia']} |"
            )
        lines.append("")

    return "\n".join(lines)


def get_customer_detail(cliente_id: str) -> dict:
    supabase = get_supabase()

    response = (
        supabase.table('segmentacion_clientes_raw')
        .select(COLS_BASE)
        .eq('cliente_id', cliente_id)
        .execute()
    )

    if not response.data:
        # Espacios flexibles: "TORREGROSA VALERO" matchea "TORREGROSA  VALERO"
        pattern = '%'.join(cliente_id.split())
        response = (
            supabase.table('segmentacion_clientes_raw')
            .select(COLS_BASE)
            .ilike('cliente_id', f'%{pattern}%')
            .limit(5)
            .execute()
        )
        if not response.data:
            return {"error": f"No se encontró el cliente '{cliente_id}'"}
        if len(response.data) > 1:
            nombres = [r['cliente_id'] for r in response.data]
            return {
                "error": f"Se encontraron {len(nombres)} coincidencias. Sé más específico.",
                "coincidencias": nombres,
                "tabla_formateada": f"**Múltiples coincidencias para '{cliente_id}':**\n\n" +
                                   "\n".join(f"- {n}" for n in nombres)
            }

    row = response.data[0]
    gasto_hist = float(row.get('gasto_total') or 0) or _calcular_gasto_historico(row)
    gasto_rec = float(row.get('gasto_reciente') or 0)
    facturas_hist = _calcular_facturas_historico(row)
    dias_recencia = _calcular_dias_recencia(row.get('fecha_ultima_compra'))
    segmento = row['segmento_rfm'] or 'Sin Clasificar'

    seg_info = SEGMENTO_INFO.get(segmento, {})
    accion = seg_info.get("accion", "Sin acción definida para este segmento.")
    prioridad = seg_info.get("prioridad", "")

    lines = ["| Año | Ventas (€) | Facturas |", "|:---|---:|---:|"]
    for year in ['2024', '2025', '2026']:
        v = float(row.get(f'ventas_{year}') or 0)
        f = int(row.get(f'facturas_{year}') or 0)
        lines.append(f"| {year} | {v:,.2f} | {f} |")
    lines.append(f"| **TOTAL** | **{gasto_hist:,.2f}** | **{facturas_hist}** |")

    resumen = f"**{row['cliente_id']}**\n"
    resumen += f"- Segmento: {segmento}\n"
    if prioridad:
        resumen += f"- Prioridad: {prioridad}\n"
    resumen += f"- Gasto histórico: {gasto_hist:,.2f}€\n"
    resumen += f"- Gasto reciente (2025+2026): {gasto_rec:,.2f}€\n"
    resumen += f"- Días sin comprar: {dias_recencia}\n"
    resumen += f"- Última compra: {row.get('fecha_ultima_compra', '?')}\n"
    resumen += f"- **Acción sugerida:** {accion}\n\n"

    tabla = resumen + "\n".join(lines)

    return {
        "cliente_id": row['cliente_id'],
        "segmento_rfm": segmento,
        "gasto_historico": gasto_hist,
        "gasto_reciente": gasto_rec,
        "facturas_historico": facturas_hist,
        "dias_recencia": dias_recencia,
        "fecha_ultima_compra": row.get('fecha_ultima_compra'),
        "accion_sugerida": accion,
        "prioridad": prioridad,
        "desglose_anual": {
            "ventas_2024": float(row.get('ventas_2024') or 0),
            "ventas_2025": float(row.get('ventas_2025') or 0),
            "ventas_2026": float(row.get('ventas_2026') or 0),
            "facturas_2024": int(row.get('facturas_2024') or 0),
            "facturas_2025": int(row.get('facturas_2025') or 0),
            "facturas_2026": int(row.get('facturas_2026') or 0),
        },
        "tabla_formateada": tabla,
    }


# ─────────────────────────────────────────────
# TOOLS v6.0 — PRODUCTOS E HISTORIAL
# ─────────────────────────────────────────────

def _resolver_cliente_id(supabase, cliente_id: str) -> tuple[str | None, dict | None]:
    """
    Resuelve un nombre de cliente (exacto o parcial) contra segmentacion_clientes_raw.
    Retorna (cliente_id_real, None) si resuelve, o (None, error_dict) si falla.
    """
    # Espacios flexibles: "TORREGROSA VALERO" matchea "TORREGROSA  VALERO"
    pattern = '%'.join(cliente_id.split())
    response = (
        supabase.table('segmentacion_clientes_raw')
        .select('cliente_id')
        .ilike('cliente_id', f'%{pattern}%')
        .limit(5)
        .execute()
    )
    if not response.data:
        return None, {"error": f"No se encontró el cliente '{cliente_id}'"}
    if len(response.data) > 1:
        nombres = [r['cliente_id'] for r in response.data]
        return None, {
            "error": f"Se encontraron {len(nombres)} coincidencias. Sé más específico.",
            "coincidencias": nombres,
            "tabla_formateada": f"**Múltiples coincidencias para '{cliente_id}':**\n\n" +
                                "\n".join(f"- {n}" for n in nombres),
        }
    return response.data[0]['cliente_id'], None


def get_customer_products(cliente_id: str, limite: int = 20) -> dict:
    """
    Historial de compras de un cliente agrupado por familia y por producto.
    Usa lineas_cliente_producto (~691K filas, indexada por cliente_id).
    """
    print(f"[Tool: get_customer_products({cliente_id!r}, limite={limite})]")
    supabase = get_supabase()

    # Exact match — paginado para clientes con >1,000 líneas
    lineas = _fetch_all_lines(supabase, cliente_id)

    # Fuzzy fallback via segmentacion_clientes_raw (1 fila por cliente)
    if not lineas:
        cliente_id_real, error = _resolver_cliente_id(supabase, cliente_id)
        if error:
            return error
        cliente_id = cliente_id_real
        lineas = _fetch_all_lines(supabase, cliente_id)
        if not lineas:
            return {
                "error": f"Cliente '{cliente_id}' existe en segmentación pero no tiene historial de productos.",
                "cliente_id": cliente_id,
                "tabla_formateada": f"**{cliente_id}** no tiene líneas de compra registradas.",
            }
    total_ventas = sum(float(l.get('ventas_netas') or 0) for l in lineas)

    # Agrupar por familia
    familias: dict[str, float] = {}
    for l in lineas:
        fam = l.get('familia') or 'Sin Clasificar'
        familias[fam] = familias.get(fam, 0) + float(l.get('ventas_netas') or 0)

    distribucion_familias = [
        {
            "familia": fam,
            "ventas": round(v, 2),
            "porcentaje": round(v / total_ventas * 100, 1) if total_ventas else 0,
        }
        for fam, v in sorted(familias.items(), key=lambda x: -x[1])
    ]

    # Agrupar por producto (codigo + descripcion) — avg margen y descuento ponderados por líneas
    productos: dict[tuple, dict] = {}
    for l in lineas:
        key = (l.get('codigo_producto') or '', l.get('descripcion') or '')
        v = float(l.get('ventas_netas') or 0)
        m = float(l.get('margen_prom') or 0)
        d = float(l.get('descuento_prom') or 0)
        fam = l.get('familia') or 'Sin Clasificar'
        if key not in productos:
            productos[key] = {'ventas': 0.0, 'margen_sum': 0.0, 'descuento_sum': 0.0, 'lineas': 0, 'familia': fam}
        productos[key]['ventas'] += v
        productos[key]['margen_sum'] += m
        productos[key]['descuento_sum'] += d
        productos[key]['lineas'] += 1

    top_productos = [
        {
            "codigo_producto": k[0],
            "descripcion": k[1],
            "familia": v['familia'],
            "ventas_total": round(v['ventas'], 2),
            "porcentaje": round(v['ventas'] / total_ventas * 100, 1) if total_ventas else 0,
            "margen_prom": round(v['margen_sum'] / v['lineas'] * 100, 1) if v['lineas'] else 0,
            "descuento_prom": round(v['descuento_sum'] / v['lineas'], 1) if v['lineas'] else 0,
        }
        for k, v in sorted(productos.items(), key=lambda x: -x[1]['ventas'])[:limite]
    ]

    # Tabla: sección familias
    lines = [f"**Historial de compras — {cliente_id}**"]
    lines.append(f"_Total: {total_ventas:,.2f}€ en {len(lineas):,} líneas de factura_\n")
    lines.append("### Por familia")
    lines.append("| Familia | Ventas (€) | % |")
    lines.append("|:---|---:|---:|")
    for d in distribucion_familias:
        lines.append(f"| {d['familia']} | {d['ventas']:,.2f} | {d['porcentaje']}% |")

    # Tabla: sección top productos
    lines.append("\n### Top productos")
    lines.append("| Producto | Familia | Ventas (€) | % | Margen % | Dcto % |")
    lines.append("|:---|:---|---:|---:|---:|---:|")
    for p in top_productos:
        desc = (p['descripcion'] or p['codigo_producto'])[:45]
        lines.append(
            f"| {desc} | {p['familia']} | {p['ventas_total']:,.2f} | {p['porcentaje']}% "
            f"| {p['margen_prom']} | {p['descuento_prom']} |"
        )

    return {
        "cliente_id": cliente_id,
        "total_ventas": round(total_ventas, 2),
        "total_lineas": len(lineas),
        "distribucion_familias": distribucion_familias,
        "top_productos": top_productos,
        "tabla_formateada": "\n".join(lines),
    }


def get_customer_family(cliente_id: str) -> dict:
    """
    Familia dominante de compra de un cliente.
    Regla: familia con >40% del gasto = dominante; si ninguna supera 40% → "Mixto".
    Llama internamente a get_customer_products (sin coste extra de red).
    """
    print(f"[Tool: get_customer_family({cliente_id!r})]")

    historial = get_customer_products(cliente_id)
    if "error" in historial:
        return historial

    distribucion = historial["distribucion_familias"]
    if not distribucion:
        return {
            "error": f"El cliente '{historial['cliente_id']}' no tiene historial de compras.",
            "cliente_id": historial["cliente_id"],
        }

    cliente_id_real = historial["cliente_id"]
    top = distribucion[0]

    if top["porcentaje"] > 40:
        familia_dominante = top["familia"]
        tipo_perfil = f"Especialista en {familia_dominante}"
    else:
        familia_dominante = "Mixto"
        top2 = [d["familia"] for d in distribucion[:2]]
        tipo_perfil = f"Comprador mixto ({' + '.join(top2)})"

    # Tabla resumen
    lines = [f"**Perfil de familia — {cliente_id_real}**"]
    lines.append(f"- Familia dominante: **{familia_dominante}**")
    lines.append(f"- Perfil: {tipo_perfil}\n")
    lines.append("| Familia | Ventas (€) | % |")
    lines.append("|:---|---:|---:|")
    for d in distribucion:
        marca = " ◀" if d["familia"] == familia_dominante and familia_dominante != "Mixto" else ""
        lines.append(f"| {d['familia']}{marca} | {d['ventas']:,.2f} | {d['porcentaje']}% |")

    return {
        "cliente_id": cliente_id_real,
        "familia_dominante": familia_dominante,
        "tipo_perfil": tipo_perfil,
        "distribucion_familias": distribucion,
        "tabla_formateada": "\n".join(lines),
    }


def get_product_catalog(familia: str = None, orden_por: str = "margen", limite: int = 10) -> dict:
    """
    Productos disponibles del catálogo (no bloqueados, precio > 0).
    orden_por: "margen" (margen_teorico_pct DESC) | "precio" (precio_con_iva DESC).
    Si se especifica familia, filtra por ella (exact match → ilike si no hay resultados).
    """
    print(f"[Tool: get_product_catalog(familia={familia!r}, orden_por={orden_por!r}, limite={limite})]")
    supabase = get_supabase()

    COLS = 'codigo_producto, descripcion, familia, subfamilia, precio_con_iva, margen_teorico_pct, stock, unidad_medida'
    ORDER_COL = 'margen_teorico_pct' if orden_por == "margen" else 'precio_con_iva'

    def _build_query(familia_filtro: str | None):
        q = (
            supabase.table('catalogo_productos')
            .select(COLS)
            .eq('bloqueado', False)
            .gt('precio_con_iva', 0)
        )
        if familia_filtro:
            q = q.eq('familia', familia_filtro)
        return q.order(ORDER_COL, desc=True).limit(limite)

    response = _build_query(familia).execute()

    # Fuzzy fallback de familia si no hay resultados
    familia_usada = familia
    if familia and not response.data:
        response_fuzzy = (
            supabase.table('catalogo_productos')
            .select('familia')
            .ilike('familia', f'%{familia}%')
            .limit(1)
            .execute()
        )
        if response_fuzzy.data:
            familia_usada = response_fuzzy.data[0]['familia']
            response = _build_query(familia_usada).execute()

    if not response.data:
        msg = f"No se encontraron productos activos" + (f" en la familia '{familia}'" if familia else "")
        return {"error": msg}

    productos = [
        {
            "codigo_producto": r['codigo_producto'],
            "descripcion": r['descripcion'] or '',
            "familia": r['familia'] or '',
            "subfamilia": r['subfamilia'] or '',
            "precio_con_iva": float(r.get('precio_con_iva') or 0),
            "margen_teorico_pct": float(r.get('margen_teorico_pct') or 0),
            "stock": int(r.get('stock') or 0),
            "unidad_medida": r.get('unidad_medida') or '',
        }
        for r in response.data
    ]

    titulo_familia = f" — {familia_usada}" if familia_usada else " — Todas las familias"
    orden_label = "margen teórico" if orden_por == "margen" else "precio"
    lines = [f"**Catálogo disponible{titulo_familia}** (por {orden_label})\n"]
    lines.append("| Producto | Familia | Precio IVA (€) | Margen % | Stock | UM |")
    lines.append("|:---|:---|---:|---:|---:|:---|")
    for p in productos:
        desc = (p['descripcion'] or p['codigo_producto'])[:45]
        lines.append(
            f"| {desc} | {p['familia']} | {p['precio_con_iva']:,.2f} "
            f"| {p['margen_teorico_pct']:.1f}% | {p['stock']:,} | {p['unidad_medida']} |"
        )

    return {
        "familia_filtrada": familia_usada,
        "orden_por": orden_por,
        "total_productos": len(productos),
        "productos": productos,
        "tabla_formateada": "\n".join(lines),
    }


# ─────────────────────────────────────────────
# LÓGICA DE NEGOCIO PARA RECOMENDACIONES
# ─────────────────────────────────────────────

# Estrategia por segmento: qué tipo de productos priorizar del catálogo
_ESTRATEGIA_SEGMENTO = {
    "Champion":                   ("Desarrollo/Premium",    "margen"),
    "Champions casi recurrente":  ("Desarrollo/Premium",    "margen"),
    "Champions dormido":          ("Recuperación mixta",    "margen"),
    "Rico perdido":               ("Recuperación agresiva", "precio"),
    "Rico potencial":             ("Fidelización",          "margen"),
    "Oportunista con potencial":  ("Ampliación de catálogo","margen"),
    "Oportunista nuevo":          ("Descubrimiento",        "margen"),
    "Activo Básico":              ("Upselling",             "precio"),
    "Oportunista perdido":        None,  # Solo campañas masivas, sin llamada
}

_NOTAS_SEGMENTO = {
    "Champion":                   "Cliente VIP activo. Ofrecer lo mejor del catálogo y novedades.",
    "Champions casi recurrente":  "Buen cliente activo. Proponer pedido recurrente o productos complementarios.",
    "Champions dormido":          "Era VIP, lleva meses sin comprar. Llamada de relación, no de venta. Escuchar primero.",
    "Rico perdido":               "Alto gasto histórico, inactivo >1 año. Entender qué pasó. Considerar condiciones especiales o regalo.",
    "Rico potencial":             "Primera compra grande. Convertir en relación estable. Preguntar cómo fue el producto.",
    "Oportunista con potencial":  "Compra con cierta regularidad pero poco volumen. ¿Compran el resto en otro sitio?",
    "Oportunista nuevo":          "Primera compra reciente. Seguimiento básico. ¿Conocen el catálogo completo?",
    "Activo Básico":              "Compran regularmente pero poco. Candidatos a upselling de versiones premium.",
    "Oportunista perdido":        "Compraban poco y se fueron. No hacer llamada individual. Solo campañas masivas.",
}


def _aplicar_reglas_negocio(
    segmento: str,
    catalogo_familia: list[dict],
    historial_productos: list[dict],
    top_familia: list[dict] = None,
) -> dict:
    """
    Aplica la estrategia comercial según segmento y devuelve productos priorizados.
    Patrón A (historial propio): Champions dormido, Rico perdido, Champion,
                                  Champions casi recurrente, Rico potencial
    Patrón B (top de familia): Oportunista con potencial, Activo Básico, Oportunista nuevo
    """
    estrategia_info = _ESTRATEGIA_SEGMENTO.get(segmento)
    nota = _NOTAS_SEGMENTO.get(segmento, "")

    # Caso especial: no hacer llamada individual
    if estrategia_info is None:
        return {
            "estrategia": "Solo campañas masivas",
            "nota_comercial": nota,
            "productos_recomendados": [],
            "llamada_individual": False,
        }

    estrategia_nombre, _ = estrategia_info

    # PATRÓN A: Historial propio → top 5 → mejor margen + producto con descuento
    if segmento in ("Champions dormido", "Rico perdido",
                    "Champion", "Champions casi recurrente", "Rico potencial"):
        top5 = historial_productos[:5]
        if not top5:
            productos_rec = catalogo_familia[:2]
        else:
            mejor = sorted(top5, key=lambda x: -x.get('margen_prom', 0))[0]
            productos_rec = [mejor]
            con_dcto = [
                p for p in top5
                if p.get('descuento_prom', 0) > 0
                and p.get('codigo_producto') != mejor.get('codigo_producto')
            ]
            if con_dcto:
                mejor_dcto = sorted(con_dcto, key=lambda x: -x.get('margen_prom', 0))[0]
                productos_rec.append({
                    **mejor_dcto,
                    "nota": f"Compró con {mejor_dcto['descuento_prom']:.0f}% dcto — ofrecer con descuento",
                })

    # PATRÓN B: Top productos de la familia → más vendido + más descuento
    elif segmento in ("Oportunista con potencial", "Activo Básico", "Oportunista nuevo"):
        fuente = top_familia or catalogo_familia
        if not fuente:
            productos_rec = []
        else:
            productos_rec = [fuente[0]]
            con_dcto = [p for p in fuente[1:] if p.get('descuento_prom', 0) > 0]
            if con_dcto:
                mejor_dcto = sorted(con_dcto, key=lambda x: -x.get('descuento_prom', 0))[0]
                productos_rec.append({
                    **mejor_dcto,
                    "nota": f"Dcto medio {mejor_dcto['descuento_prom']:.0f}% — producto con descuento habitual",
                })
            elif len(fuente) >= 2:
                productos_rec.append(fuente[1])

    else:
        productos_rec = catalogo_familia[:2]

    return {
        "estrategia": estrategia_nombre,
        "nota_comercial": nota,
        "productos_recomendados": productos_rec,
        "llamada_individual": True,
    }


def get_recommendation(cliente_id: str) -> dict:
    """
    Recomendación comercial completa para un cliente.
    Orquesta get_customer_detail, get_customer_products, get_customer_family
    y get_product_catalog internamente. El agente usa la tabla_formateada
    para redactar el guion de llamada en lenguaje natural.
    """
    print(f"[Tool: get_recommendation({cliente_id!r})]")

    # Paso 1: ficha RFM
    detalle = get_customer_detail(cliente_id)
    if "error" in detalle:
        return detalle
    cliente_id_real = detalle["cliente_id"]
    segmento = detalle["segmento_rfm"]

    # Caso: no llamar individualmente
    if _ESTRATEGIA_SEGMENTO.get(segmento) is None:
        nota = _NOTAS_SEGMENTO.get(segmento, "")
        return {
            "cliente_id": cliente_id_real,
            "segmento_rfm": segmento,
            "llamada_individual": False,
            "tabla_formateada": (
                f"**{cliente_id_real}** — {segmento}\n\n"
                f"⚠️ {nota}\n\n"
                "_No se genera recomendación de llamada individual para este segmento._"
            ),
        }

    # Paso 2: historial de productos + familia dominante
    familia_info = get_customer_family(cliente_id_real)
    if "error" in familia_info:
        familia_dominante = "Sin datos"
        historial_productos = []
    else:
        familia_dominante = familia_info["familia_dominante"]
        historial_productos = get_customer_products(cliente_id_real).get("top_productos", [])

    # Paso 3: catálogo activo en su familia dominante
    familia_catalogo = None if familia_dominante == "Mixto" else familia_dominante
    catalogo_result = get_product_catalog(familia=familia_catalogo, orden_por="margen", limite=5)
    catalogo_productos = catalogo_result.get("productos", []) if "error" not in catalogo_result else []

    # Paso 3b: top productos de la familia por ventas reales (para Patrón B)
    top_familia = []
    if familia_dominante and familia_dominante not in ("Mixto", "Sin datos"):
        supabase = get_supabase()
        top_familia = _top_productos_familia(supabase, familia_dominante)

    # Paso 4: aplicar reglas de negocio
    recomendacion = _aplicar_reglas_negocio(segmento, catalogo_productos, historial_productos, top_familia)

    # Construir tabla_formateada para el agente
    seg_info = SEGMENTO_INFO.get(segmento, {})
    lines = [f"**Recomendación comercial — {cliente_id_real}**\n"]
    lines.append(f"| Campo | Valor |")
    lines.append(f"|:---|:---|")
    lines.append(f"| Segmento | {segmento} |")
    lines.append(f"| Prioridad | {seg_info.get('prioridad', '')} |")
    lines.append(f"| Gasto histórico | {detalle['gasto_historico']:,.2f}€ |")
    lines.append(f"| Gasto reciente | {detalle['gasto_reciente']:,.2f}€ |")
    lines.append(f"| Días sin comprar | {detalle['dias_recencia']} |")
    lines.append(f"| Familia dominante | {familia_dominante} |")
    lines.append(f"| Estrategia | {recomendacion['estrategia']} |")
    lines.append(f"\n**Nota comercial:** {recomendacion['nota_comercial']}\n")

    # Productos recomendados
    prod_rec = recomendacion["productos_recomendados"]
    if prod_rec:
        lines.append("### Productos a ofrecer")
        lines.append("| Producto | Ventas (€) | Margen % | Dcto % | Nota |")
        lines.append("|:---|---:|---:|---:|:---|")
        for p in prod_rec:
            desc = (p.get('descripcion') or p.get('codigo_producto', ''))[:45]
            ventas = p.get('ventas_total', 0) or p.get('precio_con_iva', 0)
            margen = p.get('margen_prom', 0) or p.get('margen_teorico_pct', 0)
            dcto = p.get('descuento_prom', 0)
            nota_p = p.get('nota', '')
            lines.append(f"| {desc} | {ventas:,.2f} | {margen:.1f}% | {dcto:.1f}% | {nota_p} |")
    else:
        lines.append("_No hay productos específicos a recomendar._")

    # Historial resumido (top 3) para contexto de la llamada
    if historial_productos:
        lines.append("\n### Lo que ya compra habitualmente (top 3)")
        lines.append("| Producto | Ventas (€) | Margen % |")
        lines.append("|:---|---:|---:|")
        for p in historial_productos[:3]:
            desc = (p.get('descripcion') or p.get('codigo_producto', ''))[:45]
            lines.append(f"| {desc} | {p['ventas_total']:,.2f} | {p['margen_prom']} |")

    return {
        "cliente_id": cliente_id_real,
        "segmento_rfm": segmento,
        "familia_dominante": familia_dominante,
        "gasto_historico": detalle["gasto_historico"],
        "gasto_reciente": detalle["gasto_reciente"],
        "dias_recencia": detalle["dias_recencia"],
        "estrategia": recomendacion["estrategia"],
        "nota_comercial": recomendacion["nota_comercial"],
        "productos_recomendados": prod_rec,
        "llamada_individual": recomendacion["llamada_individual"],
        "tabla_formateada": "\n".join(lines),
    }