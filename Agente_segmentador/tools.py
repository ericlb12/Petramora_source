"""
Tools del Agente Segmentador
Consultas a la tabla segmentacion_clientes_raw en Supabase
"""

import os
from datetime import datetime
from config import get_supabase, MEMORY_FILE


def get_segment_distribution(fecha_corte: str = None, grupo: str = None) -> dict:
    """
    Obtiene la distribución de clientes por segmento RFM para una fecha específica.
    
    Args:
        fecha_corte: Fecha en formato YYYY-MM-DD. Si no se especifica, usa la más reciente.
        grupo: Filtrar por grupo específico (ej: "1. Champions", "2. Ricos", "3. Oportunistas", "Otros").
               Si no se especifica, retorna todos los grupos.
    
    Returns:
        dict con la distribución por segmento_rfm y grupo_segmento, incluyendo porcentajes
    """
    supabase = get_supabase()
    
    # Si no hay fecha, obtener la más reciente
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
    
    # Construir query
    query = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm, grupo_segmento') \
        .eq('fecha_corte', fecha_corte)
    
    # Aplicar filtro por grupo si se especifica
    if grupo:
        query = query.eq('grupo_segmento', grupo)
    
    response = query.execute()
    
    if not response.data:
        if grupo:
            return {"error": f"No hay datos para el grupo '{grupo}' en la fecha {fecha_corte}"}
        return {"error": f"No hay datos para la fecha {fecha_corte}"}
    
    total = len(response.data)
    
    # Contar por segmento_rfm
    segmentos = {}
    grupos = {}
    
    for row in response.data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        grp = row['grupo_segmento'] or 'Sin grupo'
        
        segmentos[seg] = segmentos.get(seg, 0) + 1
        grupos[grp] = grupos.get(grp, 0) + 1
    
    # Ordenar por cantidad descendente y agregar porcentajes
    segmentos_con_pct = {
        seg: {
            "clientes": count,
            "porcentaje": round(count / total * 100, 1)
        }
        for seg, count in sorted(segmentos.items(), key=lambda x: x[1], reverse=True)
    }
    
    grupos_con_pct = {
        grp: {
            "clientes": count,
            "porcentaje": round(count / total * 100, 1)
        }
        for grp, count in sorted(grupos.items(), key=lambda x: x[1], reverse=True)
    }
    
    return {
        "fecha_corte": fecha_corte,
        "grupo_filtrado": grupo or "Todos",
        "total_clientes": total,
        "por_segmento_rfm": segmentos_con_pct,
        "por_grupo": grupos_con_pct
    }


def get_segment_evolution(segmento: str = None, meses: int = 6) -> dict:
    """
    Obtiene la evolución temporal de un segmento o de todos los segmentos.
    
    Args:
        segmento: Nombre del segmento RFM (ej: "Champion", "En riesgo"). 
                  Si es None, retorna todos los segmentos.
        meses: Número de meses hacia atrás a consultar (default: 6)
    
    Returns:
        dict con la evolución mensual del segmento, incluyendo porcentajes y totales
    """
    supabase = get_supabase()
    
    # Obtener fechas disponibles
    response = supabase.table('segmentacion_clientes_raw') \
        .select('fecha_corte') \
        .order('fecha_corte', desc=True) \
        .execute()
    
    if not response.data:
        return {"error": "No hay datos en la tabla"}
    
    # Obtener fechas únicas y limitar a los últimos N meses
    fechas_unicas = sorted(list(set(row['fecha_corte'] for row in response.data)), reverse=True)
    fechas_a_consultar = fechas_unicas[:meses]
    
    evolucion = {}
    
    for fecha in fechas_a_consultar:
        # Consultar todos los registros de la fecha para obtener el total
        response_total = supabase.table('segmentacion_clientes_raw') \
            .select('segmento_rfm') \
            .eq('fecha_corte', fecha) \
            .execute()
        
        total_fecha = len(response_total.data)
        
        if segmento:
            # Contar solo el segmento específico
            count = sum(1 for row in response_total.data if row['segmento_rfm'] == segmento)
            evolucion[fecha] = {
                "clientes": count,
                "porcentaje": round(count / total_fecha * 100, 1) if total_fecha > 0 else 0,
                "total_clientes_mes": total_fecha
            }
        else:
            # Contar por cada segmento
            conteo = {}
            for row in response_total.data:
                seg = row['segmento_rfm'] or 'Sin clasificar'
                conteo[seg] = conteo.get(seg, 0) + 1
            
            # Agregar porcentajes a cada segmento
            conteo_con_pct = {
                seg: {
                    "clientes": count,
                    "porcentaje": round(count / total_fecha * 100, 1) if total_fecha > 0 else 0
                }
                for seg, count in conteo.items()
            }
            
            evolucion[fecha] = {
                "total_clientes_mes": total_fecha,
                "segmentos": conteo_con_pct
            }
    
    # Ordenar por fecha ascendente para mejor lectura
    evolucion_ordenada = dict(sorted(evolucion.items()))
    
    return {
        "segmento_filtrado": segmento or "Todos",
        "meses_consultados": len(fechas_a_consultar),
        "evolucion": evolucion_ordenada
    }


def get_segment_metrics(fecha_corte: str = None, segmento: str = None) -> dict:
    """
    Obtiene métricas agregadas por segmento: gasto total, promedio, 
    número de clientes, recencia promedio, porcentaje del gasto total.
    
    Args:
        fecha_corte: Fecha en formato YYYY-MM-DD. Si no se especifica, usa la más reciente.
        segmento: Filtrar por segmento específico (ej: "Champion", "En riesgo").
                  Si no se especifica, retorna todos los segmentos.
    
    Returns:
        dict con métricas por segmento, incluyendo porcentaje del gasto total
    """
    supabase = get_supabase()
    
    # Si no hay fecha, obtener la más reciente
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
    
    # Construir query
    query = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm, gasto_total, dias_recencia, num_facturas') \
        .eq('fecha_corte', fecha_corte)
    
    # Aplicar filtro por segmento si se especifica
    if segmento:
        query = query.eq('segmento_rfm', segmento)
    
    response = query.execute()
    
    if not response.data:
        if segmento:
            return {"error": f"No hay datos para el segmento '{segmento}' en la fecha {fecha_corte}"}
        return {"error": f"No hay datos para la fecha {fecha_corte}"}
    
    # Calcular gasto total global (necesario para porcentajes)
    # Si hay filtro, necesitamos consultar el total sin filtro
    if segmento:
        response_total = supabase.table('segmentacion_clientes_raw') \
            .select('gasto_total') \
            .eq('fecha_corte', fecha_corte) \
            .execute()
        gasto_global = sum(float(row['gasto_total'] or 0) for row in response_total.data)
        total_clientes_global = len(response_total.data)
    else:
        gasto_global = sum(float(row['gasto_total'] or 0) for row in response.data)
        total_clientes_global = len(response.data)
    
    # Agregar métricas por segmento
    metricas = {}
    
    for row in response.data:
        seg = row['segmento_rfm'] or 'Sin clasificar'
        
        if seg not in metricas:
            metricas[seg] = {
                'clientes': 0,
                'gasto_total': 0,
                'dias_recencia_sum': 0,
                'facturas_sum': 0
            }
        
        metricas[seg]['clientes'] += 1
        metricas[seg]['gasto_total'] += float(row['gasto_total'] or 0)
        metricas[seg]['dias_recencia_sum'] += int(row['dias_recencia'] or 0)
        metricas[seg]['facturas_sum'] += int(row['num_facturas'] or 0)
    
    # Calcular promedios y porcentajes
    resultado = {}
    for seg, data in metricas.items():
        n = data['clientes']
        resultado[seg] = {
            'clientes': n,
            'porcentaje_clientes': round(n / total_clientes_global * 100, 1) if total_clientes_global > 0 else 0,
            'gasto_total': round(data['gasto_total'], 2),
            'porcentaje_gasto': round(data['gasto_total'] / gasto_global * 100, 1) if gasto_global > 0 else 0,
            'gasto_promedio': round(data['gasto_total'] / n, 2) if n > 0 else 0,
            'recencia_promedio_dias': round(data['dias_recencia_sum'] / n, 1) if n > 0 else 0,
            'facturas_promedio': round(data['facturas_sum'] / n, 1) if n > 0 else 0
        }
    
    # Ordenar por gasto total descendente
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda x: x[1]['gasto_total'], reverse=True))
    
    return {
        "fecha_corte": fecha_corte,
        "segmento_filtrado": segmento or "Todos",
        "total_clientes": total_clientes_global,
        "gasto_total_global": round(gasto_global, 2),
        "metricas_por_segmento": resultado_ordenado
    }


def save_to_memory(categoria: str, contenido: str) -> dict:
    """
    Guarda información importante en la memoria de largo plazo del agente.
    Usa esta tool cuando descubras insights importantes, preferencias del usuario,
    o decisiones de negocio que deban recordarse en futuras conversaciones.
    
    Args:
        categoria: Categoría de la información. Opciones:
                   - "preferencias": Preferencias del usuario (formato, temas de interés, etc.)
                   - "insights": Descubrimientos importantes sobre los datos
                   - "decisiones": Decisiones de negocio tomadas basadas en análisis
                   - "notas": Otras notas relevantes
        contenido: Texto a guardar (debe ser conciso y accionable)
    
    Returns:
        dict confirmando el guardado
    """
    # Validar categoría
    categorias_validas = ["preferencias", "insights", "decisiones", "notas"]
    if categoria.lower() not in categorias_validas:
        return {"error": f"Categoría inválida. Usa: {', '.join(categorias_validas)}"}
    
    categoria = categoria.lower()
    fecha = datetime.now().strftime("%Y-%m-%d")
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    
    # Leer archivo existente o crear estructura base
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            memory_content = f.read()
    else:
        memory_content = """# Memoria del Agente Segmentador - Petramora

## Preferencias del usuario

## Insights importantes

## Decisiones de negocio

## Notas
"""
    
    # Mapeo de categoría a sección
    seccion_map = {
        "preferencias": "## Preferencias del usuario",
        "insights": "## Insights importantes",
        "decisiones": "## Decisiones de negocio",
        "notas": "## Notas"
    }
    
    seccion = seccion_map[categoria]
    nueva_entrada = f"- [{fecha}] {contenido}"
    
    # Insertar después del encabezado de sección
    if seccion in memory_content:
        # Encontrar la posición después del encabezado
        pos = memory_content.find(seccion) + len(seccion)
        # Encontrar el siguiente salto de línea
        pos_newline = memory_content.find('\n', pos)
        if pos_newline != -1:
            # Insertar la nueva entrada
            memory_content = (
                memory_content[:pos_newline + 1] + 
                nueva_entrada + '\n' + 
                memory_content[pos_newline + 1:]
            )
    else:
        # Si no existe la sección, agregarla al final
        memory_content += f"\n{seccion}\n{nueva_entrada}\n"
    
    # Guardar archivo
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.write(memory_content)
    
    return {
        "success": True,
        "mensaje": f"Guardado en '{categoria}': {contenido}",
        "fecha": fecha
    }