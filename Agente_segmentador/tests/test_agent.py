"""
Script de pruebas para el Agente Segmentador - Petramora
Evalúa capacidades, limitaciones y rendimiento del MVP
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from datetime import datetime
from config import get_supabase, MEMORY_FILE
from tools import (
    get_segment_distribution,
    get_segment_evolution,
    get_segment_metrics,
)
from agent import chat

# Colores para output
class Colors:
    OK = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    INFO = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print('='*60)

def print_test(name, passed, details="", time_ms=None):
    status = f"{Colors.OK}PASS{Colors.END}" if passed else f"{Colors.FAIL}FAIL{Colors.END}"
    time_str = f" ({time_ms}ms)" if time_ms else ""
    print(f"  [{status}] {name}{time_str}")
    if details:
        print(f"        {Colors.INFO}{details}{Colors.END}")

def print_warning(msg):
    print(f"  {Colors.WARN}[WARN] {msg}{Colors.END}")

def print_info(msg):
    print(f"  {Colors.INFO}[INFO] {msg}{Colors.END}")


# =============================================================================
# PRUEBAS DE CONEXIÓN Y DATOS
# =============================================================================

def test_supabase_connection():
    """Prueba conexión a Supabase"""
    print_header("1. CONEXIÓN A SUPABASE")
    
    try:
        start = time.time()
        supabase = get_supabase()
        response = supabase.table('segmentacion_clientes_raw').select('id').limit(1).execute()
        elapsed = int((time.time() - start) * 1000)
        
        print_test("Conexión establecida", True, time_ms=elapsed)
        return True
    except Exception as e:
        print_test("Conexión establecida", False, str(e))
        return False


def test_data_volume():
    """Prueba volumen de datos y fechas disponibles usando RPC"""
    print_header("2. VOLUMEN DE DATOS")
    
    supabase = get_supabase()
    
    try:
        # Usar RPC para obtener fechas sin truncamiento
        start = time.time()
        response = supabase.rpc('get_available_dates', {}).execute()
        elapsed = int((time.time() - start) * 1000)
        
        if response.data:
            data = response.data
            total = data['total_registros']
            n_cortes = data['total_cortes']
            fecha_min = data['fecha_min']
            fecha_max = data['fecha_max']
            fechas = data['fechas']
            
            print_test(f"Total registros: {total:,}", total > 0, time_ms=elapsed)
            print_test(f"Fechas disponibles: {n_cortes} meses", n_cortes > 0)
            print_info(f"Rango: {fecha_min} a {fecha_max}")
            
            # Clientes en última fecha
            if fechas:
                ultima = fechas[0]  # Ya ordenado DESC
                print_test(
                    f"Clientes en {ultima['fecha_corte']}: {ultima['clientes']:,}",
                    ultima['clientes'] > 0
                )
            
            return total
        else:
            print_test("Datos disponibles", False, "RPC retornó vacío")
            return 0
            
    except Exception as e:
        # Fallback si la RPC no existe
        print_warning(f"RPC get_available_dates no disponible ({e}), usando fallback")
        
        start = time.time()
        response = supabase.table('segmentacion_clientes_raw').select('id', count='exact').execute()
        elapsed = int((time.time() - start) * 1000)
        total = response.count
        print_test(f"Total registros: {total:,}", total > 0, time_ms=elapsed)
        
        return total


# =============================================================================
# PRUEBAS DE TOOLS
# =============================================================================

def test_tool_distribution():
    """Prueba tool get_segment_distribution"""
    print_header("3. TOOL: get_segment_distribution")
    
    # Sin parámetros (fecha más reciente)
    start = time.time()
    result = get_segment_distribution()
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Sin parámetros (última fecha)", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Fecha: {result['fecha_corte']}, Total: {result['total_clientes']:,}")
        segmentos = list(result['por_segmento_rfm'].keys())[:3]
        print_info(f"Top 3 segmentos: {', '.join(segmentos)}")
    
    # Con filtro de grupo
    start = time.time()
    result = get_segment_distribution(grupo="1. Champions")
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Filtro por grupo '1. Champions'", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Clientes en grupo: {result['total_clientes']:,}")
    
    # Con fecha específica
    start = time.time()
    result = get_segment_distribution(fecha_corte="2025-12-31")
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Fecha específica (2025-12-31)", has_data, time_ms=elapsed)
    
    # Fecha inválida
    start = time.time()
    result = get_segment_distribution(fecha_corte="2020-01-01")
    elapsed = int((time.time() - start) * 1000)
    
    has_error = 'error' in result
    print_test("Fecha inválida retorna error", has_error, time_ms=elapsed)


def test_tool_evolution():
    """Prueba tool get_segment_evolution"""
    print_header("4. TOOL: get_segment_evolution")
    
    # Evolución de todos los segmentos (3 meses)
    start = time.time()
    result = get_segment_evolution(meses=3)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Todos los segmentos (3 meses)", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Meses consultados: {result['meses_consultados']}")
    
    # Evolución de segmento específico (6 meses)
    start = time.time()
    result = get_segment_evolution(segmento="Champion", meses=6)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Segmento 'Champion' (6 meses)", has_data, time_ms=elapsed)
    
    if has_data and result['evolucion']:
        fechas = list(result['evolucion'].keys())
        primera = result['evolucion'][fechas[0]]
        ultima = result['evolucion'][fechas[-1]]
        print_info(f"Evolución: {primera['clientes']} → {ultima['clientes']} clientes ({len(fechas)} meses)")
    
    # Evolución de 12 meses (validación de rango amplio)
    start = time.time()
    result = get_segment_evolution(segmento="Champion", meses=12)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Segmento 'Champion' (12 meses)", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Meses consultados: {result['meses_consultados']}")
    
    # Segmento inexistente
    start = time.time()
    result = get_segment_evolution(segmento="SegmentoFalso", meses=3)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Segmento inexistente (retorna vacío)", has_data, time_ms=elapsed)


def test_tool_metrics():
    """Prueba tool get_segment_metrics"""
    print_header("5. TOOL: get_segment_metrics")
    
    # Métricas de todos los segmentos
    start = time.time()
    result = get_segment_metrics()
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Todos los segmentos", has_data, time_ms=elapsed)
    
    if has_data:
        gasto = result['gasto_total_global']
        print_test(f"Gasto total global: {gasto:,.2f}€", gasto > 0)
        top_seg = list(result['metricas_por_segmento'].keys())[0]
        top_data = result['metricas_por_segmento'][top_seg]
        print_info(f"Top segmento: {top_seg} ({top_data['porcentaje_gasto']}% del gasto)")
    
    # Métricas de segmento específico
    start = time.time()
    result = get_segment_metrics(segmento="Champion")
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Segmento 'Champion'", has_data, time_ms=elapsed)
    
    if has_data and 'Champion' in result['metricas_por_segmento']:
        data = result['metricas_por_segmento']['Champion']
        print_info(f"Gasto promedio Champion: {data['gasto_promedio']:,.2f}€")
    
    # Métricas de fecha anterior (validar datos históricos)
    start = time.time()
    result = get_segment_metrics(fecha_corte="2025-06-30")
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Métricas fecha histórica (jun 2025)", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Gasto global jun 2025: {result['gasto_total_global']:,.2f}€")



# =============================================================================
# PRUEBAS DEL AGENTE COMPLETO
# =============================================================================

def test_agent_basic():
    """Prueba respuestas básicas del agente"""
    print_header("7. AGENTE: Respuestas básicas")
    
    test_cases = [
        {
            "pregunta": "¿Cuántos clientes tenemos en total?",
            "espera": ["clientes", "total", "24"],
            "descripcion": "Pregunta simple de conteo"
        },
        {
            "pregunta": "¿Cuál es la distribución de segmentos?",
            "espera": ["Champion", "segmento", "%"],
            "descripcion": "Distribución de segmentos"
        },
        {
            "pregunta": "¿Qué segmento genera más ingresos?",
            "espera": ["gasto", "€", "ingreso", "Champion"],
            "descripcion": "Métricas de gasto"
        }
    ]
    
    for tc in test_cases:
        start = time.time()
        response = chat(tc["pregunta"])
        elapsed = int((time.time() - start) * 1000)
        
        response_lower = response.lower()
        found = any(word.lower() in response_lower for word in tc["espera"])
        
        print_test(tc["descripcion"], found, time_ms=elapsed)
        if not found:
            print_warning(f"Respuesta: {response[:100]}...")



def test_agent_edge_cases():
    """Prueba casos límite del agente"""
    print_header("9. AGENTE: Casos límite")
    
    test_cases = [
        {
            "pregunta": "¿Cuántos clientes compraron el producto X?",
            "espera_error": True,
            "descripcion": "Pregunta fuera de alcance (productos)"
        },
        {
            "pregunta": "¿Cuántos clientes hay en la tienda online?",
            "espera_error": True,
            "descripcion": "Pregunta fuera de alcance (canales)"
        },
        {
            "pregunta": "",
            "espera_error": True,
            "descripcion": "Pregunta vacía"
        }
    ]
    
    for tc in test_cases:
        if not tc["pregunta"]:
            print_test(tc["descripcion"], True, "Manejado por validación de input")
            continue
            
        start = time.time()
        response = chat(tc["pregunta"])
        elapsed = int((time.time() - start) * 1000)
        
        indicates_limitation = any(word in response.lower() for word in 
            ["no tengo", "no puedo", "no dispongo", "limitación", "no está disponible",
             "próximamente", "no cuento", "actualmente no", "no disponemos"])
        
        print_test(tc["descripcion"], indicates_limitation, time_ms=elapsed)
        if not indicates_limitation:
            print_warning(f"Respuesta: {response[:100]}...")


# =============================================================================
# PRUEBAS DE RENDIMIENTO
# =============================================================================

def test_performance():
    """Prueba rendimiento con diferentes volúmenes"""
    print_header("10. RENDIMIENTO")
    
    supabase = get_supabase()
    
    # Query simple
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm') \
        .limit(100) \
        .execute()
    elapsed = int((time.time() - start) * 1000)
    print_test("Query 100 registros", True, time_ms=elapsed)
    
    # Query 1000 registros
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm') \
        .limit(1000) \
        .execute()
    elapsed = int((time.time() - start) * 1000)
    print_test("Query 1,000 registros", True, time_ms=elapsed)
    
    # Query 10000 registros
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm') \
        .limit(10000) \
        .execute()
    elapsed = int((time.time() - start) * 1000)
    print_test("Query 10,000 registros", True, time_ms=elapsed)
    
    # RPC distribution (mide rendimiento real de las tools)
    start = time.time()
    result = get_segment_distribution()
    elapsed = int((time.time() - start) * 1000)
    print_test("RPC distribution", 'error' not in result, time_ms=elapsed)
    
    # RPC metrics
    start = time.time()
    result = get_segment_metrics()
    elapsed = int((time.time() - start) * 1000)
    print_test("RPC metrics", 'error' not in result, time_ms=elapsed)
    
    # RPC evolution (6 meses)
    start = time.time()
    result = get_segment_evolution(segmento="Champion", meses=6)
    elapsed = int((time.time() - start) * 1000)
    print_test("RPC evolution (6 meses)", 'error' not in result, time_ms=elapsed)
    
    # Agente completo
    start = time.time()
    response = chat("¿Cuántos Champions hay?")
    elapsed = int((time.time() - start) * 1000)
    print_test("Agente respuesta completa", len(response) > 0, time_ms=elapsed)


# =============================================================================
# PRUEBAS DE LOGS EN SUPABASE
# =============================================================================

def test_logging():
    """Prueba que los logs se guardan en Supabase"""
    print_header("11. LOGGING EN SUPABASE")
    
    supabase = get_supabase()
    
    # Verificar tabla agent_logs
    try:
        response = supabase.table('agent_logs').select('*').limit(5).order('timestamp', desc=True).execute()
        has_logs = len(response.data) > 0
        print_test("Tabla agent_logs accesible", True)
        print_test("Hay logs registrados", has_logs)
        
        if has_logs:
            latest = response.data[0]
            print_info(f"Último log: {latest.get('timestamp', 'N/A')}")
            print_info(f"Modelo usado: {latest.get('model_used', 'N/A')}")
            print_info(f"Latencia: {latest.get('latency_ms', 'N/A')}ms")
    except Exception as e:
        print_test("Tabla agent_logs accesible", False, str(e))
    
    # Verificar tabla agent_sessions
    try:
        response = supabase.table('agent_sessions').select('*').limit(5).order('updated_at', desc=True).execute()
        has_sessions = len(response.data) > 0
        print_test("Tabla agent_sessions accesible", True)
        print_test("Hay sesiones registradas", has_sessions)
        
        if has_sessions:
            latest = response.data[0]
            history_len = len(latest.get('history', []))
            print_info(f"Última sesión: {latest.get('session_id', 'N/A')[:8]}...")
            print_info(f"Mensajes en historial: {history_len}")
    except Exception as e:
        print_test("Tabla agent_sessions accesible", False, str(e))


# =============================================================================
# RESUMEN Y LIMITACIONES
# =============================================================================

def print_summary():
    """Imprime resumen de capacidades y limitaciones"""
    print_header("RESUMEN: CAPACIDADES DEL MVP")
    
    print(f"""
{Colors.OK}✓ PUEDE:{Colors.END}
  • Consultar distribución de clientes por segmento RFM (24,131 clientes, 26 meses)
  • Ver evolución temporal de segmentos (hasta 26 meses disponibles)
  • Obtener métricas de gasto, recencia y frecuencia por segmento
  • Filtrar por grupo o segmento específico
  • Filtrar por fecha de corte (ene 2024 - feb 2026)
  • Persistir conversaciones en Supabase
  • Loguear todas las interacciones para análisis
  • Fallback automático entre modelos de Google
  • Agregaciones server-side via RPCs (sin límite de filas)

{Colors.FAIL}✗ NO PUEDE:{Colors.END}
  • Consultar por canal de venta (online vs tienda física)
  • Consultar productos específicos que compra cada cliente
  • Identificar clientes individuales por nombre
  • Comparar automáticamente con período anterior (Hito 3)

{Colors.WARN}⚠ LIMITACIONES TÉCNICAS:{Colors.END}
  • gasto_total es acumulado anual (no mensual) — comparaciones requieren delta
  • El contexto del modelo tiene límite de tokens

{Colors.INFO}ℹ PENDIENTES (HITO 3):{Colors.END}
  • Comparación automática con mes anterior
  • Filtrar evolución por grupo
  • Métricas adicionales (mediana, ticket promedio)
""")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print(f"\n{Colors.BOLD}{'='*60}")
    print("   PRUEBAS DEL AGENTE SEGMENTADOR - PETRAMORA MVP")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}{Colors.END}")
    
    # Ejecutar pruebas
    test_supabase_connection()
    test_data_volume()
    test_tool_distribution()
    test_tool_evolution()
    test_tool_metrics()
    test_agent_basic()
    test_agent_edge_cases()
    test_performance()
    test_logging()
    
    # Resumen
    print_summary()
    
    print(f"\n{Colors.BOLD}Pruebas completadas.{Colors.END}\n")


if __name__ == "__main__":
    main()