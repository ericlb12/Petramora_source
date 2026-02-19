"""
Tools del Agente Segmentador v3.2
- Todas las tools devuelven "tabla_formateada" con markdown listo
- El agente DEBE copiar esa tabla tal cual, sin reinterpretar números
- Nueva tool: get_customer_history (historial de un cliente individual)
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


def _calcular_gasto_historico(cliente_id: str) -> float:
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


# ─────────────────────────────────────────────
# TOOLS PRINCIPALES
# ─────────────────────────────────────────────

def get_segment_distribution(fecha_corte: str = None) -> dict:
    supabase = get_supabase()
    params = {}
    if fecha_corte:
        params['p_fecha_corte'] = fecha_corte

    try:
        response = supabase.rpc('get_segment_distribution_agg', params).execute()
        if response.data:
            result = response.data
            if isinstance(result, str):
                import json
                result = json.loads(result)
            if isinstance(result, dict) and 'por_segmento_rfm' in result:
                # Generar tabla formateada
                total = result.get('total_clientes', 0)
                fecha = result.get('fecha_corte', '?')
                lines = [f"| Segmento | Clientes | Porcentaje |", f"|:---|---:|---:|"]
                for seg, data in sorted(result['por_segmento_rfm'].items(), key=lambda x: x[1]['clientes'], reverse=True):
                    lines.append(f"| {seg} | {data['clientes']:,} | {data['porcentaje']}% |")
                result['tabla_formateada'] = f"**Distribución ({fecha}) — {total:,} clientes totales**\n\n" + "\n".join(lines)
            return result
        return {"error": "No se obtuvieron datos"}
    except Exception as e:
        print(f"   [Warning RPC distribution: {e}]")
        return _get_segment_distribution_fallback(fecha_corte)


def get_segment_evolution(segmento: str = None, meses: int = 6) -> dict:
    supabase = get_supabase()
    params = {'p_meses': meses}
    if segmento:
        params['p_segmento'] = segmento

    try:
        response = supabase.rpc('get_segment_evolution_agg', params).execute()
        if response.data:
            result = response.data
            if isinstance(result, str):
                import json
                result = json.loads(result)
            if isinstance(result, dict) and 'evolucion' in result:
                evo = result['evolucion']
                if segmento:
                    # Tabla para un segmento específico
                    lines = ["| Fecha | Clientes | Porcentaje | Total mes |", "|:---|---:|---:|---:|"]
                    for fecha in sorted(evo.keys()):
                        d = evo[fecha]
                        lines.append(f"| {fecha} | {d['clientes']:,} | {d['porcentaje']}% | {d['total_clientes_mes']:,} |")
                    result['tabla_formateada'] = f"**Evolución de '{segmento}' ({len(evo)} meses)**\n\n" + "\n".join(lines)
                else:
                    # Tabla resumen con todos los segmentos
                    # Recopilar todos los segmentos
                    all_segs = set()
                    for fecha, data in evo.items():
                        if 'segmentos' in data:
                            all_segs.update(data['segmentos'].keys())
                    all_segs = sorted(all_segs)
                    
                    header = "| Fecha | " + " | ".join(all_segs) + " |"
                    sep = "|:---|" + "|".join(["---:" for _ in all_segs]) + "|"
                    lines = [header, sep]
                    for fecha in sorted(evo.keys()):
                        data = evo[fecha]
                        segs = data.get('segmentos', {})
                        vals = [str(segs.get(s, {}).get('clientes', 0)) for s in all_segs]
                        lines.append(f"| {fecha} | " + " | ".join(vals) + " |")
                    result['tabla_formateada'] = f"**Evolución de todos los segmentos ({len(evo)} meses)**\n\n" + "\n".join(lines)
            return result
        return {"error": "No se obtuvieron datos"}
    except Exception as e:
        print(f"   [Warning RPC evolution: {e}]")
        return _get_segment_evolution_fallback(segmento, meses)


def get_segment_metrics(fecha_corte: str = None, segmento: str = None) -> dict:
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
            if isinstance(result, str):
                import json
                result = json.loads(result)
            if isinstance(result, dict) and 'metricas_por_segmento' in result:
                fecha = result.get('fecha_corte', '?')
                gasto_global = result.get('gasto_total_global', 0)
                lines = ["| Segmento | Clientes | Gasto total (€) | % Gasto | Gasto prom. (€) | Facturas prom. |",
                         "|:---|---:|---:|---:|---:|---:|"]
                for seg, d in result['metricas_por_segmento'].items():
                    lines.append(f"| {seg} | {d['clientes']:,} | {d['gasto_total']:,.2f} | {d['porcentaje_gasto']}% | {d['gasto_promedio']:,.2f} | {d['facturas_promedio']} |")
                result['tabla_formateada'] = f"**Métricas por segmento ({fecha}) — Gasto global del mes: {gasto_global:,.2f}€**\n\n" + "\n".join(lines) + f"\n\n_Nota: Estos datos son del mes {fecha}. Los segmentos con €0 no compraron ese mes, no significa que nunca hayan gastado._"
            return result
        return {"error": "No se obtuvieron datos"}
    except Exception as e:
        print(f"   [Warning RPC metrics: {e}]")
        return _get_segment_metrics_fallback(fecha_corte, segmento)


def get_actionable_customers(criterio: str = "today", limite: int = 10) -> dict:
    supabase = get_supabase()

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
                        "dias_recencia": dias,
                        "seg_recencia": row.get('seg_recencia'),
                        "seg_frecuencia": row.get('seg_frecuencia'),
                        "seg_monetario": row.get('seg_monetario'),
                    })
                restantes -= len(response.data)

        # Ordenar por gasto histórico descendente
        clientes.sort(key=lambda x: -x['gasto_historico'])
    else:
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
        elif criterio == "top_historical":
            # No filtrar por segmento — traer todos, ordenar por gasto mensual alto
            # Traemos más para luego ordenar por gasto histórico
            pass

        response = query.order('gasto_total', desc=True).limit(limite * 3 if criterio == "top_historical" else limite).execute()
        clientes = []
        for row in (response.data or []):
            dias = _calcular_dias_recencia(row.get('fecha_ultima_compra'))
            gasto_hist = _calcular_gasto_historico(row['cliente_id'])
            clientes.append({
                "cliente_id": row['cliente_id'],
                "segmento_rfm": row['segmento_rfm'],
                "gasto_historico": gasto_hist,
                "dias_recencia": dias,
                "seg_recencia": row.get('seg_recencia'),
                "seg_frecuencia": row.get('seg_frecuencia'),
                "seg_monetario": row.get('seg_monetario'),
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


def get_customer_history(cliente_id: str) -> dict:
    """
    Obtiene el historial completo de un cliente: segmento, gasto y recencia por mes.
    Usa para: '¿Beatriz Pizarro siempre fue Champions dormido?' o 'Dime el historial de X'
    """
    supabase = get_supabase()

    response = (
        supabase.table('segmentacion_clientes_raw')
        .select('fecha_corte, segmento_rfm, gasto_total, num_facturas, fecha_ultima_compra, seg_recencia, seg_frecuencia, seg_monetario')
        .eq('cliente_id', cliente_id)
        .order('fecha_corte', desc=False)
        .execute()
    )

    if not response.data:
        return {"error": f"No se encontró el cliente '{cliente_id}'"}

    # Calcular métricas resumen
    gasto_historico = round(sum(float(row['gasto_total'] or 0) for row in response.data), 2)
    dias_recencia = _calcular_dias_recencia(response.data[-1].get('fecha_ultima_compra'))
    segmento_actual = response.data[-1]['segmento_rfm']
    meses_con_datos = len(response.data)

    # Detectar cambios de segmento
    cambios = []
    seg_anterior = None
    for row in response.data:
        if row['segmento_rfm'] != seg_anterior:
            cambios.append({"fecha": row['fecha_corte'], "segmento": row['segmento_rfm']})
            seg_anterior = row['segmento_rfm']

    # Tabla formateada con cambios de segmento
    lines = ["| Fecha | Segmento | Gasto mes (€) | Facturas |",
             "|:---|:---|---:|---:|"]
    for row in response.data:
        gasto = float(row['gasto_total'] or 0)
        facturas = int(row['num_facturas'] or 0)
        lines.append(f"| {row['fecha_corte']} | {row['segmento_rfm']} | {gasto:,.2f} | {facturas} |")

    resumen = f"**{cliente_id}**\n"
    resumen += f"- Segmento actual: {segmento_actual}\n"
    resumen += f"- Gasto histórico total: {gasto_historico:,.2f}€\n"
    resumen += f"- Días sin comprar: {dias_recencia}\n"
    resumen += f"- Meses con datos: {meses_con_datos}\n"
    resumen += f"- Cambios de segmento: {len(cambios)}\n\n"

    tabla = resumen + "\n".join(lines)

    return {
        "cliente_id": cliente_id,
        "segmento_actual": segmento_actual,
        "gasto_historico": gasto_historico,
        "dias_recencia": dias_recencia,
        "meses_con_datos": meses_con_datos,
        "cambios_segmento": cambios,
        "tabla_formateada": tabla,
        "historial": response.data,
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


# ─────────────────────────────────────────────
# FALLBACKS (con paginación)
# ─────────────────────────────────────────────

def _paginate_query(supabase, table, select_cols, filters=None, page_size=1000):
    all_data = []
    offset = 0
    while True:
        query = supabase.table(table).select(select_cols)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        response = query.range(offset, offset + page_size - 1).execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break
        offset += page_size
    return all_data


def _get_segment_distribution_fallback(fecha_corte=None):
    supabase = get_supabase()
    if not fecha_corte:
        r = supabase.table('segmentacion_clientes_raw').select('fecha_corte').order('fecha_corte', desc=True).limit(1).execute()
        if r.data:
            fecha_corte = r.data[0]['fecha_corte']
        else:
            return {"error": "No hay datos"}

    all_data = _paginate_query(supabase, 'segmentacion_clientes_raw', 'segmento_rfm', {'fecha_corte': fecha_corte})
    if not all_data:
        return {"error": f"No hay datos para {fecha_corte}"}

    total = len(all_data)
    segmentos = {}
    for row in all_data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        segmentos[seg] = segmentos.get(seg, 0) + 1

    por_segmento = {
        seg: {"clientes": c, "porcentaje": round(c / total * 100, 1)}
        for seg, c in sorted(segmentos.items(), key=lambda x: x[1], reverse=True)
    }

    lines = ["| Segmento | Clientes | Porcentaje |", "|:---|---:|---:|"]
    for seg, d in por_segmento.items():
        lines.append(f"| {seg} | {d['clientes']:,} | {d['porcentaje']}% |")

    return {
        "fecha_corte": fecha_corte,
        "total_clientes": total,
        "por_segmento_rfm": por_segmento,
        "tabla_formateada": f"**Distribución ({fecha_corte}) — {total:,} clientes**\n\n" + "\n".join(lines),
    }


def _get_segment_evolution_fallback(segmento=None, meses=6):
    supabase = get_supabase()
    r = supabase.table('segmentacion_clientes_raw').select('fecha_corte').order('fecha_corte', desc=True).execute()
    if not r.data:
        return {"error": "No hay datos"}

    fechas = sorted(list(set(row['fecha_corte'] for row in r.data)), reverse=True)[:meses]
    evolucion = {}

    for fecha in fechas:
        data = _paginate_query(supabase, 'segmentacion_clientes_raw', 'segmento_rfm', {'fecha_corte': fecha})
        total = len(data)
        if segmento:
            count = sum(1 for row in data if row['segmento_rfm'] == segmento)
            evolucion[fecha] = {"clientes": count, "porcentaje": round(count / total * 100, 1) if total else 0, "total_clientes_mes": total}
        else:
            conteo = {}
            for row in data:
                s = row['segmento_rfm'] or 'Sin clasificar'
                conteo[s] = conteo.get(s, 0) + 1
            evolucion[fecha] = {"total_clientes_mes": total, "segmentos": {s: {"clientes": c, "porcentaje": round(c / total * 100, 1)} for s, c in conteo.items()}}

    evo_sorted = dict(sorted(evolucion.items()))

    if segmento:
        lines = ["| Fecha | Clientes | Porcentaje | Total mes |", "|:---|---:|---:|---:|"]
        for f in sorted(evo_sorted.keys()):
            d = evo_sorted[f]
            lines.append(f"| {f} | {d['clientes']:,} | {d['porcentaje']}% | {d['total_clientes_mes']:,} |")
        tabla = f"**Evolución de '{segmento}' ({len(evo_sorted)} meses)**\n\n" + "\n".join(lines)
    else:
        tabla = f"**Evolución general ({len(evo_sorted)} meses)**"

    return {
        "segmento_filtrado": segmento or "Todos",
        "meses_consultados": len(fechas),
        "evolucion": evo_sorted,
        "tabla_formateada": tabla,
    }


def _get_segment_metrics_fallback(fecha_corte=None, segmento=None):
    supabase = get_supabase()
    if not fecha_corte:
        r = supabase.table('segmentacion_clientes_raw').select('fecha_corte').order('fecha_corte', desc=True).limit(1).execute()
        if r.data:
            fecha_corte = r.data[0]['fecha_corte']
        else:
            return {"error": "No hay datos"}

    filters = {'fecha_corte': fecha_corte}
    if segmento:
        filters['segmento_rfm'] = segmento
    all_data = _paginate_query(supabase, 'segmentacion_clientes_raw', 'segmento_rfm, gasto_total, num_facturas, fecha_ultima_compra', filters)

    if not all_data:
        return {"error": f"No hay datos para {fecha_corte}"}

    gasto_global = sum(float(r['gasto_total'] or 0) for r in all_data)
    total = len(all_data)

    metricas = {}
    for row in all_data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        if seg not in metricas:
            metricas[seg] = {'clientes': 0, 'gasto': 0, 'facturas': 0, 'recencia': []}
        metricas[seg]['clientes'] += 1
        metricas[seg]['gasto'] += float(row['gasto_total'] or 0)
        metricas[seg]['facturas'] += int(row['num_facturas'] or 0)
        metricas[seg]['recencia'].append(_calcular_dias_recencia(row.get('fecha_ultima_compra')))

    resultado = {}
    for seg, d in metricas.items():
        n = d['clientes']
        resultado[seg] = {
            'clientes': n, 'porcentaje_clientes': round(n / total * 100, 1),
            'gasto_total': round(d['gasto'], 2),
            'porcentaje_gasto': round(d['gasto'] / gasto_global * 100, 1) if gasto_global else 0,
            'gasto_promedio': round(d['gasto'] / n, 2) if n else 0,
            'recencia_promedio_dias': round(sum(d['recencia']) / n, 1) if n else 0,
            'facturas_promedio': round(d['facturas'] / n, 1) if n else 0,
        }

    resultado = dict(sorted(resultado.items(), key=lambda x: x[1]['gasto_total'], reverse=True))

    lines = ["| Segmento | Clientes | Gasto total (€) | % Gasto | Gasto prom. (€) |", "|:---|---:|---:|---:|---:|"]
    for seg, d in resultado.items():
        lines.append(f"| {seg} | {d['clientes']:,} | {d['gasto_total']:,.2f} | {d['porcentaje_gasto']}% | {d['gasto_promedio']:,.2f} |")

    return {
        "fecha_corte": fecha_corte, "fecha_consulta": date.today().isoformat(),
        "segmento_filtrado": segmento or "Todos", "total_clientes": total,
        "gasto_total_global": round(gasto_global, 2),
        "metricas_por_segmento": resultado,
        "tabla_formateada": f"**Métricas ({fecha_corte}) — Gasto global del mes: {gasto_global:,.2f}€**\n\n" + "\n".join(lines) + f"\n\n_Nota: Estos datos son del mes {fecha_corte}. Los segmentos con €0 no compraron ese mes, no significa que nunca hayan gastado._",
    }