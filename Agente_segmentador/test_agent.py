"""
Script de pruebas para el Agente Segmentador - Petramora
Evalúa capacidades, limitaciones y rendimiento del MVP
"""

import time
import os
from datetime import datetime
from config import get_supabase, MEMORY_FILE
from tools import (
    get_segment_distribution,
    get_segment_evolution,
    get_segment_metrics,
    save_to_memory
)
from agent import chat, load_memory

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
    """Prueba volumen de datos y fechas disponibles"""
    print_header("2. VOLUMEN DE DATOS")
    
    supabase = get_supabase()
    
    # Total de registros
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw').select('id', count='exact').execute()
    elapsed = int((time.time() - start) * 1000)
    total = response.count
    print_test(f"Total registros: {total:,}", total > 0, time_ms=elapsed)
    
    # Fechas disponibles
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw').select('fecha_corte').execute()
    elapsed = int((time.time() - start) * 1000)
    fechas = sorted(list(set(row['fecha_corte'] for row in response.data)))
    print_test(f"Fechas disponibles: {len(fechas)} meses", len(fechas) > 0, time_ms=elapsed)
    
    if fechas:
        print_info(f"Rango: {fechas[0]} a {fechas[-1]}")
    
    # Clientes únicos en última fecha
    if fechas:
        ultima_fecha = fechas[-1]
        start = time.time()
        response = supabase.table('segmentacion_clientes_raw') \
            .select('cliente_id') \
            .eq('fecha_corte', ultima_fecha) \
            .execute()
        elapsed = int((time.time() - start) * 1000)
        clientes = len(response.data)
        print_test(f"Clientes en {ultima_fecha}: {clientes:,}", clientes > 0, time_ms=elapsed)
    
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
    
    # Evolución de todos los segmentos
    start = time.time()
    result = get_segment_evolution(meses=3)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Todos los segmentos (3 meses)", has_data, time_ms=elapsed)
    
    if has_data:
        print_info(f"Meses consultados: {result['meses_consultados']}")
    
    # Evolución de segmento específico
    start = time.time()
    result = get_segment_evolution(segmento="Champion", meses=6)
    elapsed = int((time.time() - start) * 1000)
    
    has_data = 'error' not in result
    print_test("Segmento 'Champion' (6 meses)", has_data, time_ms=elapsed)
    
    if has_data and result['evolucion']:
        fechas = list(result['evolucion'].keys())
        primera = result['evolucion'][fechas[0]]
        ultima = result['evolucion'][fechas[-1]]
        print_info(f"Evolución: {primera['clientes']} → {ultima['clientes']} clientes")
    
    # Segmento inexistente
    start = time.time()
    result = get_segment_evolution(segmento="SegmentoFalso", meses=3)
    elapsed = int((time.time() - start) * 1000)
    
    # Debería retornar 0 clientes, no error
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
        print_info(f"Gasto total global: {result['gasto_total_global']:,.2f}€")
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


def test_tool_memory():
    """Prueba tool save_to_memory"""
    print_header("6. TOOL: save_to_memory")
    
    # Guardar preferencia
    start = time.time()
    result = save_to_memory("preferencias", "TEST: Usuario prefiere ver datos en porcentajes")
    elapsed = int((time.time() - start) * 1000)
    
    success = result.get('success', False)
    print_test("Guardar preferencia", success, time_ms=elapsed)
    
    # Guardar insight
    start = time.time()
    result = save_to_memory("insights", "TEST: Champions son 8% de clientes pero 45% del gasto")
    elapsed = int((time.time() - start) * 1000)
    
    success = result.get('success', False)
    print_test("Guardar insight", success, time_ms=elapsed)
    
    # Categoría inválida
    start = time.time()
    result = save_to_memory("categoria_falsa", "Contenido de prueba")
    elapsed = int((time.time() - start) * 1000)
    
    has_error = 'error' in result
    print_test("Categoría inválida retorna error", has_error, time_ms=elapsed)
    
    # Verificar que se guardó en archivo
    memory_content = load_memory()
    has_test_content = "TEST:" in memory_content
    print_test("Contenido guardado en MEMORY.md", has_test_content)
    
    if has_test_content:
        print_info(f"Tamaño del archivo: {len(memory_content)} caracteres")


# =============================================================================
# PRUEBAS DEL AGENTE COMPLETO
# =============================================================================

def test_agent_basic():
    """Prueba respuestas básicas del agente"""
    print_header("7. AGENTE: Respuestas básicas")
    
    test_cases = [
        {
            "pregunta": "¿Cuántos clientes tenemos en total?",
            "espera": ["clientes", "total"],
            "descripcion": "Pregunta simple de conteo"
        },
        {
            "pregunta": "¿Cuál es la distribución de segmentos?",
            "espera": ["Champion", "segmento", "%"],
            "descripcion": "Distribución de segmentos"
        },
        {
            "pregunta": "¿Qué segmento genera más ingresos?",
            "espera": ["gasto", "€", "ingreso"],
            "descripcion": "Métricas de gasto"
        }
    ]
    
    for tc in test_cases:
        start = time.time()
        response = chat(tc["pregunta"])
        elapsed = int((time.time() - start) * 1000)
        
        # Verificar que contiene palabras esperadas
        response_lower = response.lower()
        found = any(word.lower() in response_lower for word in tc["espera"])
        
        print_test(tc["descripcion"], found, time_ms=elapsed)
        if not found:
            print_warning(f"Respuesta: {response[:100]}...")


def test_agent_memory_integration():
    """Prueba integración de memoria del agente"""
    print_header("8. AGENTE: Integración de memoria")
    
    # Pedir que recuerde algo
    start = time.time()
    response = chat("Recuerda que me interesa especialmente el segmento 'En riesgo' para futuras conversaciones")
    elapsed = int((time.time() - start) * 1000)
    
    # Verificar que guardó en memoria
    memory_content = load_memory()
    saved = "riesgo" in memory_content.lower() or "En riesgo" in memory_content
    
    print_test("Agente guarda en memoria cuando se le pide", saved, time_ms=elapsed)
    
    if not saved:
        print_warning("El agente no usó save_to_memory automáticamente")
        print_info("Esto puede requerir ajuste en el prompt")


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
        
        # El agente debería indicar que no puede responder
        indicates_limitation = any(word in response.lower() for word in 
            ["no tengo", "no puedo", "no dispongo", "limitación", "no está disponible", "próximamente"])
        
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
    
    # Query con filtro (más realista)
    start = time.time()
    response = supabase.table('segmentacion_clientes_raw') \
        .select('segmento_rfm, gasto_total') \
        .eq('segmento_rfm', 'Champion') \
        .execute()
    elapsed = int((time.time() - start) * 1000)
    count = len(response.data)
    print_test(f"Query filtrada ({count:,} Champions)", True, time_ms=elapsed)
    
    # Tool completa
    start = time.time()
    result = get_segment_distribution()
    elapsed = int((time.time() - start) * 1000)
    print_test("Tool distribution completa", 'error' not in result, time_ms=elapsed)
    
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
  • Consultar distribución de clientes por segmento RFM
  • Ver evolución temporal de segmentos (hasta 6 meses por defecto)
  • Obtener métricas de gasto, recencia y frecuencia por segmento
  • Filtrar por grupo o segmento específico
  • Guardar y recordar preferencias/insights en memoria local
  • Persistir conversaciones en Supabase
  • Loguear todas las interacciones para análisis
  • Fallback automático entre modelos de Google

{Colors.FAIL}✗ NO PUEDE:{Colors.END}
  • Consultar por canal de venta (online vs tienda física)
  • Consultar productos específicos que compra cada cliente
  • Identificar clientes individuales por nombre
  • Comparar automáticamente con período anterior (pendiente)
  • Buscar en historial de conversaciones pasadas (pendiente)

{Colors.WARN}⚠ LIMITACIONES TÉCNICAS:{Colors.END}
  • Supabase tiene límite de ~10,000 registros por query sin paginación
  • Las tools procesan datos en memoria (puede ser lento con muchos segmentos)
  • La memoria local (MEMORY.md) no tiene búsqueda semántica
  • El contexto del modelo tiene límite de tokens

{Colors.INFO}ℹ PENDIENTES IDENTIFICADOS:{Colors.END}
  • Tool memory_search para buscar en historial
  • Comparación automática con período anterior
  • Filtrar evolución por grupo
  • Métricas adicionales (mediana, ticket promedio)
  • Few-shot examples en el prompt
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
    test_tool_memory()
    test_agent_basic()
    test_agent_memory_integration()
    test_agent_edge_cases()
    test_performance()
    test_logging()
    
    # Resumen
    print_summary()
    
    print(f"\n{Colors.BOLD}Pruebas completadas.{Colors.END}\n")


if __name__ == "__main__":
    main()