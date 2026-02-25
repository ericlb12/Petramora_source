"""
Tools del Agente Segmentador v4.0
- Esquema simplificado: solo último mes, 10 columnas
- Ventas/facturas por año (2024, 2025, 2026)
- gasto_historico = ventas_2024 + ventas_2025 + ventas_2026 (directo, sin queries extra)
- Todas las tools devuelven "tabla_formateada" con markdown listo
"""

import os
from datetime import datetime, date
from config import get_supabase, MEMORY_FILE


SEGMENTOS_PRIORIDAD_TODAY = [
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

    # Agregar métricas por segmento
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

    # Ordenar por gasto total descendente
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
    Lista de clientes a contactar HOY, ordenados por prioridad de negocio.
    Criterios: today, churn_risk, growth_potential, inactive_vip, new_high_value, top_historical
    """
    supabase = get_supabase()

    if criterio == "today":
        clientes = []
        restantes = limite

        for segmento in SEGMENTOS_PRIORIDAD_TODAY:
            if restantes <= 0:
                break
            response = (
                supabase.table('segmentacion_clientes_raw')
                .select(COLS_BASE)
                .eq('segmento_rfm', segmento)
                .limit(restantes * 2)
                .execute()
            )
            if response.data:
                for row in response.data:
                    clientes.append({
                        "cliente_id": row['cliente_id'],
                        "segmento_rfm": row['segmento_rfm'],
                        "gasto_historico": _calcular_gasto_historico(row),
                        "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
                    })
                restantes -= len(response.data)

        # Ordenar por gasto histórico descendente y limitar
        clientes.sort(key=lambda x: -x['gasto_historico'])
        clientes = clientes[:limite]
    else:
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

        fetch_limit = limite * 3 if criterio == "top_historical" else limite * 2
        response = query.limit(fetch_limit).execute()

        clientes = []
        for row in (response.data or []):
            gasto_hist = _calcular_gasto_historico(row)
            # Filtrar growth_potential y new_high_value por gasto mínimo
            if criterio == "growth_potential" and gasto_hist < 138:
                continue
            if criterio == "new_high_value" and gasto_hist < 138:
                continue
            clientes.append({
                "cliente_id": row['cliente_id'],
                "segmento_rfm": row['segmento_rfm'],
                "gasto_historico": gasto_hist,
                "dias_recencia": _calcular_dias_recencia(row.get('fecha_ultima_compra')),
            })

        clientes.sort(key=lambda x: -x['gasto_historico'])
        clientes = clientes[:limite]

    # Generar tabla formateada
    if criterio == "top_historical":
        titulo = f"**Top {len(clientes)} clientes por gasto histórico**"
    else:
        titulo = f"**Clientes a contactar hoy ({date.today().isoformat()})**"

    lines = ["| # | Cliente | Segmento | Gasto histórico (€) | Días sin comprar |",
             "|---:|:---|:---|---:|---:|"]
    for i, c in enumerate(clientes, 1):
        lines.append(f"| {i} | {c['cliente_id']} | {c['segmento_rfm']} | {c['gasto_historico']:,.2f} | {c['dias_recencia']} |")

    tabla = titulo + "\n\n" + "\n".join(lines)

    return {
        "criterio": criterio,
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes),
        "tabla_formateada": tabla,
        "clientes": clientes,
    }


def get_customer_detail(cliente_id: str) -> dict:
    """
    Detalle completo de un cliente: segmento, gasto por año, facturas por año.
    Usa para: '¿Quién es UXÍA DOMÍNGUEZ?', 'Dime sobre cliente X'
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

    # Tabla desglose por año
    lines = ["| Año | Ventas (€) | Facturas |", "|:---|---:|---:|"]
    for year in ['2024', '2025', '2026']:
        v = float(row.get(f'ventas_{year}') or 0)
        f = int(row.get(f'facturas_{year}') or 0)
        lines.append(f"| {year} | {v:,.2f} | {f} |")
    lines.append(f"| **TOTAL** | **{gasto_hist:,.2f}** | **{facturas_hist}** |")

    resumen = f"**{row['cliente_id']}**\n"
    resumen += f"- Segmento actual: {row['segmento_rfm']}\n"
    resumen += f"- Gasto histórico total: {gasto_hist:,.2f}€\n"
    resumen += f"- Días sin comprar: {dias_recencia}\n"
    resumen += f"- Última compra: {row.get('fecha_ultima_compra', '?')}\n\n"

    tabla = resumen + "\n".join(lines)

    return {
        "cliente_id": row['cliente_id'],
        "segmento_rfm": row['segmento_rfm'],
        "gasto_historico": gasto_hist,
        "facturas_historico": facturas_hist,
        "dias_recencia": dias_recencia,
        "fecha_ultima_compra": row.get('fecha_ultima_compra'),
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


def save_to_memory(categoria: str, contenido: str) -> dict:
    categorias_validas = ["preferencias", "insights", "decisiones", "notas"]
    if categoria.lower() not in categorias_validas:
        return {"error": f"Categoría inválida. Usa: {', '.join(categorias_validas)}"}

    categoria = categoria.lower()
    fecha = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            memory_content = f.read()
    else:
        memory_content = "# Memoria del Agente Segmentador\n\n## Preferencias del usuario\n\n## Insights importantes\n\n## Decisiones de negocio\n\n## Notas\n"

    seccion_map = {
        "preferencias": "## Preferencias del usuario",
        "insights": "## Insights importantes",
        "decisiones": "## Decisiones de negocio",
        "notas": "## Notas"
    }
    seccion = seccion_map[categoria]
    nueva_entrada = f"- [{fecha}] {contenido}"

    if seccion in memory_content:
        pos = memory_content.find(seccion) + len(seccion)
        pos_newline = memory_content.find('\n', pos)
        if pos_newline != -1:
            memory_content = memory_content[:pos_newline + 1] + nueva_entrada + '\n' + memory_content[pos_newline + 1:]
    else:
        memory_content += f"\n{seccion}\n{nueva_entrada}\n"

    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.write(memory_content)
    return {"success": True, "mensaje": f"Guardado en '{categoria}': {contenido}", "fecha": fecha}