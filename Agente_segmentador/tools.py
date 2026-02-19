"""
Tools del Agente Segmentador v3.1
- dias_recencia: calculado en tiempo real (hoy - fecha_ultima_compra)
- gasto_historico: SUM(gasto_total) de todos los meses del cliente
- segmento_rfm: directo del DAX (no calculado en Python)
"""

import os
from datetime import datetime, date
from config import get_supabase, MEMORY_FILE


# ─────────────────────────────────────────────
# Prioridad de segmentos para "¿a quién llamo?"
# ─────────────────────────────────────────────
SEGMENTOS_PRIORIDAD_TODAY = [
    "Champions dormido",          # 1. VIP enfriándose — máxima urgencia
    "Rico perdido",               # 2. Alto valor histórico, inactivo
    "Champions casi recurrente",  # 3. Bajando frecuencia
    "Rico potencial",             # 4. Primera compra grande, fidelizar
]


def _calcular_dias_recencia(fecha_ultima_compra_str: str) -> int:
    """Calcula días de recencia en tiempo real desde hoy."""
    if not fecha_ultima_compra_str:
        return 9999
    try:
        fecha = datetime.strptime(str(fecha_ultima_compra_str), '%Y-%m-%d').date()
        return (date.today() - fecha).days
    except (ValueError, TypeError):
        return 9999


def _calcular_gasto_historico(cliente_id: str) -> float:
    """Calcula el gasto histórico total de un cliente sumando todos sus meses."""
    supabase = get_supabase()
    try:
        response = (
            supabase.table('segmentacion_clientes_raw')
            .select('gasto_total')
            .eq('cliente_id', cliente_id)
            .execute()
        )
        if response.data:
            return round(sum(float(row['gasto_total'] or 0) for row in response.data), 2)
    except Exception:
        pass
    return 0.0


def get_segment_distribution(fecha_corte: str = None) -> dict:
    """
    Distribución de clientes por segmento RFM para una fecha.
    """
    supabase = get_supabase()

    params = {}
    if fecha_corte:
        params['p_fecha_corte'] = fecha_corte

    try:
        response = supabase.rpc('get_segment_distribution_agg', params).execute()
        if response.data:
            result = response.data
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                import json
                return json.loads(result)
            return result
        return {"error": "No se obtuvieron datos de la función"}

    except Exception as e:
        print(f"   [Warning RPC distribution: {e}]")
        return _get_segment_distribution_fallback(fecha_corte)


def get_segment_evolution(segmento: str = None, meses: int = 6) -> dict:
    """
    Evolución temporal de un segmento o todos.
    """
    supabase = get_supabase()

    params = {'p_meses': meses}
    if segmento:
        params['p_segmento'] = segmento

    try:
        response = supabase.rpc('get_segment_evolution_agg', params).execute()
        if response.data:
            result = response.data
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                import json
                return json.loads(result)
            return result
        return {"error": "No se obtuvieron datos de la función"}

    except Exception as e:
        print(f"   [Warning RPC evolution: {e}]")
        return _get_segment_evolution_fallback(segmento, meses)


def get_segment_metrics(fecha_corte: str = None, segmento: str = None) -> dict:
    """
    Métricas agregadas por segmento.
    """
    supabase = get_supabase()

    params = {}
    if fecha_corte:
        params['p_fecha_corte'] = fecha_corte
    if segmento:
        params['p_segmento'] = segmento

    try:
        response = supabase.rpc('get_segment_metrics_agg', params).execute()
        if response.data:
            result = response.data
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                import json
                return json.loads(result)
            return result
        return {"error": "No se obtuvieron datos de la función"}

    except Exception as e:
        print(f"   [Warning RPC metrics: {e}]")
        return _get_segment_metrics_fallback(fecha_corte, segmento)


def get_actionable_customers(criterio: str = "today", limite: int = 10) -> dict:
    """
    Clientes que requieren atención inmediata.
    
    Para criterio "today": consulta por segmento en orden de prioridad,
    calcula gasto HISTÓRICO (no mensual) y recencia en tiempo real.
    """
    supabase = get_supabase()

    # Fecha de corte más reciente
    res_fecha = (
        supabase.table('segmentacion_clientes_raw')
        .select('fecha_corte')
        .order('fecha_corte', desc=True)
        .limit(1)
        .execute()
    )
    if not res_fecha.data:
        return {"error": "No hay datos disponibles"}

    fecha_reciente = res_fecha.data[0]['fecha_corte']
    cols = 'cliente_id, segmento_rfm, gasto_total, num_facturas, fecha_ultima_compra, seg_recencia, seg_frecuencia, seg_monetario'

    if criterio == "today":
        # Consultar por cada segmento en orden de prioridad
        clientes = []
        restantes = limite

        for segmento in SEGMENTOS_PRIORIDAD_TODAY:
            if restantes <= 0:
                break

            response = (
                supabase.table('segmentacion_clientes_raw')
                .select(cols)
                .eq('fecha_corte', fecha_reciente)
                .eq('segmento_rfm', segmento)
                .order('gasto_total', desc=True)
                .limit(restantes)
                .execute()
            )

            if response.data:
                for row in response.data:
                    dias = _calcular_dias_recencia(row.get('fecha_ultima_compra'))
                    gasto_hist = _calcular_gasto_historico(row['cliente_id'])

                    clientes.append({
                        "cliente_id": row['cliente_id'],
                        "segmento_rfm": row['segmento_rfm'],
                        "gasto_historico": gasto_hist,
                        "gasto_mes_actual": float(row['gasto_total'] or 0),
                        "num_facturas_mes": int(row['num_facturas'] or 0),
                        "dias_recencia": dias,
                        "fecha_ultima_compra": row.get('fecha_ultima_compra'),
                        "seg_recencia": row.get('seg_recencia'),
                        "seg_frecuencia": row.get('seg_frecuencia'),
                        "seg_monetario": row.get('seg_monetario'),
                    })

                restantes -= len(response.data)

    else:
        # Otros criterios: query directa
        query = (
            supabase.table('segmentacion_clientes_raw')
            .select(cols)
            .eq('fecha_corte', fecha_reciente)
        )

        if criterio == "churn_risk":
            query = query.in_('segmento_rfm', ['Champion', 'Champions casi recurrente'])
        elif criterio == "growth_potential":
            query = query.in_('segmento_rfm', ['Oportunista con potencial', 'Activo Básico'])
            query = query.gte('gasto_total', 138)
        elif criterio == "inactive_vip":
            query = query.in_('segmento_rfm', ['Rico perdido', 'Champions dormido'])
        elif criterio == "new_high_value":
            query = query.in_('segmento_rfm', ['Rico potencial', 'Oportunista nuevo'])
            query = query.gte('gasto_total', 138)

        response = query.order('gasto_total', desc=True).limit(limite).execute()

        clientes = []
        for row in (response.data or []):
            dias = _calcular_dias_recencia(row.get('fecha_ultima_compra'))
            gasto_hist = _calcular_gasto_historico(row['cliente_id'])

            clientes.append({
                "cliente_id": row['cliente_id'],
                "segmento_rfm": row['segmento_rfm'],
                "gasto_historico": gasto_hist,
                "gasto_mes_actual": float(row['gasto_total'] or 0),
                "num_facturas_mes": int(row['num_facturas'] or 0),
                "dias_recencia": dias,
                "fecha_ultima_compra": row.get('fecha_ultima_compra'),
                "seg_recencia": row.get('seg_recencia'),
                "seg_frecuencia": row.get('seg_frecuencia'),
                "seg_monetario": row.get('seg_monetario'),
            })

    return {
        "criterio": criterio,
        "fecha_corte": fecha_reciente,
        "fecha_consulta": date.today().isoformat(),
        "total_encontrados": len(clientes),
        "clientes": clientes
    }


def save_to_memory(categoria: str, contenido: str) -> dict:
    """Guarda información en la memoria de largo plazo."""
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
        memory_content = "# Memoria del Agente Segmentador - Petramora\n\n## Preferencias del usuario\n\n## Insights importantes\n\n## Decisiones de negocio\n\n## Notas\n"

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
            memory_content = (
                memory_content[:pos_newline + 1]
                + nueva_entrada + '\n'
                + memory_content[pos_newline + 1:]
            )
    else:
        memory_content += f"\n{seccion}\n{nueva_entrada}\n"

    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.write(memory_content)

    return {"success": True, "mensaje": f"Guardado en '{categoria}': {contenido}", "fecha": fecha}


# ─────────────────────────────────────────────────────────────
# Fallbacks (con paginación para superar límite de 1000 filas)
# ─────────────────────────────────────────────────────────────

def _get_segment_distribution_fallback(fecha_corte: str = None) -> dict:
    supabase = get_supabase()

    if not fecha_corte:
        response = supabase.table('segmentacion_clientes_raw') \
            .select('fecha_corte') \
            .order('fecha_corte', desc=True) \
            .limit(1) \
            .execute()
        if response.data:
            fecha_corte = response.data[0]['fecha_corte']
        else:
            return {"error": "No hay datos en la tabla"}

    # Paginar para superar límite de 1000
    all_data = []
    page_size = 1000
    offset = 0
    while True:
        response = supabase.table('segmentacion_clientes_raw') \
            .select('segmento_rfm') \
            .eq('fecha_corte', fecha_corte) \
            .range(offset, offset + page_size - 1) \
            .execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break
        offset += page_size

    if not all_data:
        return {"error": f"No hay datos para la fecha {fecha_corte}"}

    total = len(all_data)
    segmentos = {}
    for row in all_data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        segmentos[seg] = segmentos.get(seg, 0) + 1

    segmentos_con_pct = {
        seg: {"clientes": count, "porcentaje": round(count / total * 100, 1)}
        for seg, count in sorted(segmentos.items(), key=lambda x: x[1], reverse=True)
    }

    return {
        "fecha_corte": fecha_corte,
        "total_clientes": total,
        "por_segmento_rfm": segmentos_con_pct,
    }


def _get_segment_evolution_fallback(segmento: str = None, meses: int = 6) -> dict:
    supabase = get_supabase()

    response = supabase.table('segmentacion_clientes_raw') \
        .select('fecha_corte') \
        .order('fecha_corte', desc=True) \
        .execute()

    if not response.data:
        return {"error": "No hay datos en la tabla"}

    fechas_unicas = sorted(list(set(row['fecha_corte'] for row in response.data)), reverse=True)
    fechas_a_consultar = fechas_unicas[:meses]

    evolucion = {}
    for fecha in fechas_a_consultar:
        response_total = supabase.table('segmentacion_clientes_raw') \
            .select('segmento_rfm') \
            .eq('fecha_corte', fecha) \
            .execute()

        total_fecha = len(response_total.data)

        if segmento:
            count = sum(1 for row in response_total.data if row['segmento_rfm'] == segmento)
            evolucion[fecha] = {
                "clientes": count,
                "porcentaje": round(count / total_fecha * 100, 1) if total_fecha > 0 else 0,
                "total_clientes_mes": total_fecha
            }
        else:
            conteo = {}
            for row in response_total.data:
                seg = row['segmento_rfm'] or 'Sin clasificar'
                conteo[seg] = conteo.get(seg, 0) + 1
            evolucion[fecha] = {
                "total_clientes_mes": total_fecha,
                "segmentos": {
                    seg: {"clientes": c, "porcentaje": round(c / total_fecha * 100, 1)}
                    for seg, c in conteo.items()
                }
            }

    return {
        "segmento_filtrado": segmento or "Todos",
        "meses_consultados": len(fechas_a_consultar),
        "evolucion": dict(sorted(evolucion.items()))
    }


def _get_segment_metrics_fallback(fecha_corte: str = None, segmento: str = None) -> dict:
    supabase = get_supabase()

    if not fecha_corte:
        response = supabase.table('segmentacion_clientes_raw') \
            .select('fecha_corte') \
            .order('fecha_corte', desc=True) \
            .limit(1) \
            .execute()
        if response.data:
            fecha_corte = response.data[0]['fecha_corte']
        else:
            return {"error": "No hay datos en la tabla"}

    # Paginar
    all_data = []
    page_size = 1000
    offset = 0
    while True:
        query = supabase.table('segmentacion_clientes_raw') \
            .select('segmento_rfm, gasto_total, num_facturas, fecha_ultima_compra') \
            .eq('fecha_corte', fecha_corte)
        if segmento:
            query = query.eq('segmento_rfm', segmento)
        response = query.range(offset, offset + page_size - 1).execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break
        offset += page_size

    if not all_data:
        return {"error": f"No hay datos para la fecha {fecha_corte}"}

    gasto_global = sum(float(row['gasto_total'] or 0) for row in all_data)
    total_clientes_global = len(all_data)

    metricas = {}
    for row in all_data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        if seg not in metricas:
            metricas[seg] = {'clientes': 0, 'gasto_total': 0, 'facturas_sum': 0, 'recencia_dias': []}
        metricas[seg]['clientes'] += 1
        metricas[seg]['gasto_total'] += float(row['gasto_total'] or 0)
        metricas[seg]['facturas_sum'] += int(row['num_facturas'] or 0)
        metricas[seg]['recencia_dias'].append(_calcular_dias_recencia(row.get('fecha_ultima_compra')))

    resultado = {}
    for seg, data in metricas.items():
        n = data['clientes']
        resultado[seg] = {
            'clientes': n,
            'porcentaje_clientes': round(n / total_clientes_global * 100, 1),
            'gasto_total': round(data['gasto_total'], 2),
            'porcentaje_gasto': round(data['gasto_total'] / gasto_global * 100, 1) if gasto_global > 0 else 0,
            'gasto_promedio': round(data['gasto_total'] / n, 2) if n > 0 else 0,
            'recencia_promedio_dias': round(sum(data['recencia_dias']) / n, 1) if n > 0 else 0,
            'facturas_promedio': round(data['facturas_sum'] / n, 1) if n > 0 else 0,
        }

    return {
        "fecha_corte": fecha_corte,
        "fecha_consulta": date.today().isoformat(),
        "segmento_filtrado": segmento or "Todos",
        "total_clientes": total_clientes_global,
        "gasto_total_global": round(gasto_global, 2),
        "metricas_por_segmento": dict(sorted(resultado.items(), key=lambda x: x[1]['gasto_total'], reverse=True))
    }