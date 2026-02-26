"""
Tools del Agente Segmentador v5.0
- Esquema simplificado: solo último mes, 10 columnas
- Ventas/facturas por año (2024, 2025, 2026)
- gasto_historico = ventas_2024 + ventas_2025 + ventas_2026 (directo, sin queries extra)
- get_actionable_customers agrupa por segmento con orden de prioridad
- Todas las tools devuelven "tabla_formateada" con markdown listo
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
    },
    {
        "segmento": "Rico perdido",
        "prioridad": "🔴 URGENTE — Llamar HOY",
        "accion": "Llamada de recuperación. Entender qué pasó, si hubo problema con el servicio o se fueron a la competencia. Considerar condiciones especiales.",
    },
    {
        "segmento": "Champions casi recurrente",
        "prioridad": "🟡 IMPORTANTE — Llamar esta semana",
        "accion": "Llamada de desarrollo. Ofrecer productos complementarios, proponer pedido recurrente. Son buenos clientes activos que podrían comprar más.",
    },
    {
        "segmento": "Rico potencial",
        "prioridad": "🟡 IMPORTANTE — Llamar esta semana",
        "accion": "Seguimiento post-primera compra grande. Preguntar cómo les fue con el producto, abrir puerta a pedidos regulares.",
    },
    {
        "segmento": "Oportunista con potencial",
        "prioridad": "🟢 NORMAL — Llamar este mes",
        "accion": "Entender su negocio. ¿Compran poco porque no necesitan más o porque compran el resto en otro sitio? Oportunidad de ampliar catálogo.",
    },
    {
        "segmento": "Oportunista nuevo",
        "prioridad": "🟢 NORMAL — Llamar este mes",
        "accion": "Seguimiento post-venta básico. ¿Quedaron satisfechos? ¿Conocen el resto del catálogo? Sin presionar.",
    },
    {
        "segmento": "Activo Básico",
        "prioridad": "⚪ BAJO — Mantenimiento",
        "accion": "No requieren llamada urgente. Candidatos a campañas de upselling por email o WhatsApp.",
    },
    {
        "segmento": "Champion",
        "prioridad": "⚪ BAJO — Fidelización",
        "accion": "No necesitan llamada de venta. Llamada de agradecimiento y fidelización. Ya son los mejores clientes.",
    },
    {
        "segmento": "Oportunista perdido",
        "prioridad": "⚪ BAJO — Solo campañas masivas",
        "accion": "Compraban poco y se fueron. No merece llamada individual. Incluir en campañas masivas de reactivación.",
    },
]

# Mapa rápido segmento → info de prioridad
SEGMENTO_INFO = {s["segmento"]: s for s in SEGMENTOS_PRIORIDAD}

# Segmentos que se incluyen en "¿a quién llamo hoy?" (los urgentes + importantes)
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
    """Calcula gasto histórico sumando ventas de todos los años. Sin queries extra."""
    return round(
        float(row.get('ventas_2024') or 0) +
        float(row.get('ventas_2025') or 0) +
        float(row.get('ventas_2026') or 0),
        2
    )


def _calcular_facturas_historico(row: dict) -> int:
    """Calcula facturas históricas sumando de todos los años."""
    return (
        int(row.get('facturas_2024') or 0) +
        int(row.get('facturas_2025') or 0) +
        int(row.get('facturas_2026') or 0)
    )


# ─────────────────────────────────────────────
# TOOLS PRINCIPALES
# ─────────────────────────────────────────────

COLS_BASE = 'cliente_id, segmento_rfm, fecha_ultima_compra, ventas_2024, ventas_2025, ventas_2026, facturas_2024, facturas_2025, facturas_2026'


def get_segment_distribution() -> dict:
    """
    Distribución actual de clientes por segmento RFM.
    Usa para: '¿Cuántos clientes tenemos?', '¿Cómo están distribuidos?'
    """
    supabase = get_supabase()

    response = (
        supabase.table('segmentacion_clientes_raw')
        .select('segmento_rfm')
        .execute()
    )

    if not response.data:
        return {"error": "No se obtuvieron datos"}

    total = len(response.data)
    segmentos = {}
    for row in response.data:
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
    """
    Métricas agregadas por segmento: gasto histórico total, facturas, clientes.
    Usa para: '¿Cuánto gastan los Champions?', '¿Métricas por segmento?'
    """
    supabase = get_supabase()

    query = supabase.table('segmentacion_clientes_raw').select(COLS_BASE)
    if segmento:
        query = query.eq('segmento_rfm', segmento)

    response = query.execute()

    if not response.data:
        return {"error": f"No hay datos{' para ' + segmento if segmento else ''}"}

    metricas = {}
    gasto_global = 0
    for row in response.data:
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


def get_actionable_customers(criterio: str = "today", limite: int = 10) -> dict:
    """
    Lista de clientes a contactar, agrupados por segmento en orden de prioridad.
    Criterios:
      - 'today': Clientes urgentes a llamar hoy (Champions dormido, Rico perdido,
                 Champions casi recurrente, Rico potencial).
      - 'churn_risk': Clientes en riesgo de fuga.
      - 'growth_potential': Clientes con potencial de crecimiento.
      - 'inactive_vip': VIPs inactivos.
      - 'new_high_value': Nuevos clientes de alto valor.
      - 'top_historical': Top clientes por gasto histórico total.
      - 'all_segments': Todos los segmentos con acción sugerida.
    """
    supabase = get_supabase()

    if criterio == "today":
        return _actionable_today(supabase, limite)
    elif criterio == "all_segments":
        return _actionable_all_segments(supabase, limite)
    else:
        return _actionable_by_filter(supabase, criterio, limite)


def _actionable_today(supabase, limite: int) -> dict:
    """
    Agrupa clientes por segmento en orden de prioridad de llamada.
    Cada segmento incluye su acción sugerida.
    """
    grupos = []
    clientes_total = []

    for segmento in SEGMENTOS_LLAMAR_HOY:
        info = SEGMENTO_INFO[segmento]

        response = (
            supabase.table('segmentacion_clientes_raw')
            .select(COLS_BASE)
            .eq('segmento_rfm', segmento)
            .limit(limite)
            .execute()
        )

        if not response.data:
            continue

        clientes_seg = []
        for row in response.data:
            cliente = {
                "cliente_id": row['cliente_id'],
                "segmento_rfm": segmento,
                "gasto_historico": _calcular_gasto_historico(row),
                "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
            }
            clientes_seg.append(cliente)

        # Ordenar por gasto histórico descendente dentro del segmento
        clientes_seg.sort(key=lambda x: -x['gasto_historico'])
        clientes_seg = clientes_seg[:limite]

        grupos.append({
            "segmento": segmento,
            "prioridad": info["prioridad"],
            "accion": info["accion"],
            "clientes": clientes_seg,
        })
        clientes_total.extend(clientes_seg)

    # Generar tabla formateada agrupada
    tabla = _formatear_tabla_agrupada(grupos, limite)

    return {
        "criterio": "today",
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes_total),
        "grupos": grupos,
        "clientes": clientes_total,
        "tabla_formateada": tabla,
    }


def _actionable_all_segments(supabase, limite: int) -> dict:
    """
    Muestra todos los segmentos con su prioridad y acción, incluyendo clientes ejemplo.
    """
    grupos = []
    clientes_total = []

    for seg_info in SEGMENTOS_PRIORIDAD:
        segmento = seg_info["segmento"]

        response = (
            supabase.table('segmentacion_clientes_raw')
            .select(COLS_BASE)
            .eq('segmento_rfm', segmento)
            .limit(limite)
            .execute()
        )

        clientes_seg = []
        for row in (response.data or []):
            cliente = {
                "cliente_id": row['cliente_id'],
                "segmento_rfm": segmento,
                "gasto_historico": _calcular_gasto_historico(row),
                "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
            }
            clientes_seg.append(cliente)

        clientes_seg.sort(key=lambda x: -x['gasto_historico'])
        clientes_seg = clientes_seg[:limite]

        grupos.append({
            "segmento": segmento,
            "prioridad": seg_info["prioridad"],
            "accion": seg_info["accion"],
            "clientes": clientes_seg,
        })
        clientes_total.extend(clientes_seg)

    tabla = _formatear_tabla_agrupada(grupos, limite)

    return {
        "criterio": "all_segments",
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes_total),
        "grupos": grupos,
        "clientes": clientes_total,
        "tabla_formateada": tabla,
    }


def _actionable_by_filter(supabase, criterio: str, limite: int) -> dict:
    """
    Filtra clientes por criterio específico (churn_risk, growth_potential, etc.)
    """
    query = supabase.table('segmentacion_clientes_raw').select(COLS_BASE)

    if criterio == "churn_risk":
        query = query.in_('segmento_rfm', ['Champion', 'Champions casi recurrente'])
    elif criterio == "growth_potential":
        query = query.in_('segmento_rfm', ['Oportunista con potencial', 'Activo Básico'])
    elif criterio == "inactive_vip":
        query = query.in_('segmento_rfm', ['Rico perdido', 'Champions dormido'])
    elif criterio == "new_high_value":
        query = query.in_('segmento_rfm', ['Rico potencial', 'Oportunista nuevo'])
    elif criterio == "top_historical":
        pass  # No filtrar — traer todos

    fetch_limit = limite * 2
    if criterio == "top_historical":
        # Traer TODOS para poder ordenar por gasto calculado en Python
        response = query.execute()
    else:
        response = query.limit(fetch_limit).execute()

    clientes = []
    for row in (response.data or []):
        gasto_hist = _calcular_gasto_historico(row)
        if criterio in ("growth_potential", "new_high_value") and gasto_hist < 138:
            continue
        clientes.append({
            "cliente_id": row['cliente_id'],
            "segmento_rfm": row['segmento_rfm'],
            "gasto_historico": gasto_hist,
            "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
        })

    clientes.sort(key=lambda x: -x['gasto_historico'])
    clientes = clientes[:limite]

    # Agrupar por segmento para tabla formateada
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

    # Ordenar grupos por prioridad definida
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
    tabla = _formatear_tabla_agrupada(grupos, limite, titulo_override=titulo)

    return {
        "criterio": criterio,
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes),
        "grupos": grupos,
        "clientes": clientes,
        "tabla_formateada": tabla,
    }


def _formatear_tabla_agrupada(grupos: list, limite: int, titulo_override: str = None) -> str:
    """
    Genera tabla markdown agrupada por segmento con prioridad y acción.
    """
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
        lines.append("| # | Cliente | Gasto histórico (€) | Días sin comprar |")
        lines.append("|---:|:---|---:|---:|")

        for i, c in enumerate(grupo["clientes"], 1):
            lines.append(
                f"| {i} | {c['cliente_id']} | {c['gasto_historico']:,.2f} | {c['dias_recencia']} |"
            )
        lines.append("")  # línea en blanco entre grupos

    return "\n".join(lines)


def get_customer_detail(cliente_id: str) -> dict:
    """
    Detalle completo de un cliente: segmento, gasto por año, facturas por año.
    Incluye acción sugerida basada en su segmento.
    Usa para: '¿Por qué llamar a Beatriz?', 'Dime sobre X', '¿Cuánto gastó X en 2024?'
    """
    supabase = get_supabase()

    response = (
        supabase.table('segmentacion_clientes_raw')
        .select(COLS_BASE)
        .eq('cliente_id', cliente_id)
        .execute()
    )

    if not response.data:
        # Buscar por coincidencia parcial (fuzzy básico)
        response = (
            supabase.table('segmentacion_clientes_raw')
            .select(COLS_BASE)
            .ilike('cliente_id', f'%{cliente_id}%')
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
    gasto_hist = _calcular_gasto_historico(row)
    facturas_hist = _calcular_facturas_historico(row)
    dias_recencia = _calcular_dias_recencia(row.get('fecha_ultima_compra'))
    segmento = row['segmento_rfm'] or 'Sin Clasificar'

    # Obtener acción sugerida del segmento
    seg_info = SEGMENTO_INFO.get(segmento, {})
    accion = seg_info.get("accion", "Sin acción definida para este segmento.")
    prioridad = seg_info.get("prioridad", "")

    # Tabla desglose por año
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
    resumen += f"- Días sin comprar: {dias_recencia}\n"
    resumen += f"- Última compra: {row.get('fecha_ultima_compra', '?')}\n"
    resumen += f"- **Acción sugerida:** {accion}\n\n"

    tabla = resumen + "\n".join(lines)

    return {
        "cliente_id": row['cliente_id'],
        "segmento_rfm": segmento,
        "gasto_historico": gasto_hist,
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