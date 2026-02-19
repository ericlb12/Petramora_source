import sys
import os
import time
from datetime import datetime

# Añadir el directorio base al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools import get_actionable_customers
from agent import chat

# Colores para output
class Colors:
    OK = '\033[92m'
    FAIL = '\033[91m'
    INFO = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title):
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"   {title}")
    print(f"{'='*60}{Colors.END}")

def print_test(name, passed, details=""):
    status = f"{Colors.OK}PASS{Colors.END}" if passed else f"{Colors.FAIL}FAIL{Colors.END}"
    print(f"  [{status}] {name}")
    if details:
        print(f"        {Colors.INFO}{details}{Colors.END}")

def test_tool_criteria():
    print_header("1. PRUEBAS DE LA TOOL: get_actionable_customers")
    
    criterios = [
        ("churn_risk", "Clientes en riesgo de fuga"),
        ("growth_potential", "Potencial de crecimiento"),
        ("inactive_vip", "VIPs inactivos"),
        ("new_high_value", "Nuevos clientes de alto valor")
    ]
    
    for crit, desc in criterios:
        start = time.time()
        result = get_actionable_customers(criterio=crit, limite=5)
        elapsed = int((time.time() - start) * 1000)
        
        has_data = "clientes" in result and isinstance(result["clientes"], list)
        print_test(f"Criterio: {desc} ({crit})", has_data, f"Encontrados: {len(result.get('clientes', []))} en {elapsed}ms")
        
        if has_data and len(result["clientes"]) > 0:
            first = result["clientes"][0]
            print(f"        Ejemplo: {first['cliente_id']} | Gasto: {first['gasto_total']}€ | Seg: {first['segmento_rfm']}")

def test_agent_business_logic():
    print_header("2. PRUEBAS DE LÓGICA DE NEGOCIO (AGENTE)")
    
    test_cases = [
        {
            "pregunta": "¿A quién debo contactar hoy y por qué?",
            "requiere": ["porque", "hoy", "contacto", "riesgo", "potencial"],
            "desc": "Pregunta general de acción"
        },
        {
            "pregunta": "¿Qué mejores clientes están en riesgo de irse?",
            "requiere": ["riesgo", "fuga", "contacto", "Champion"],
            "desc": "Foco en churn_risk"
        },
        {
            "pregunta": "Dáme una lista de clientes nuevos que han gastado mucho",
            "requiere": ["nuevo", "gasto", "Oro", "Plata", "contactar"],
            "desc": "Foco en new_high_value"
        }
    ]
    
    for tc in test_cases:
        print(f"\n  > Probando: {tc['desc']}")
        start = time.time()
        response = chat(tc["pregunta"])
        elapsed = int((time.time() - start) * 1000)
        
        # Verificar que la respuesta contenga palabras clave y explique el "Por qué"
        response_lower = response.lower()
        has_keywords = any(word.lower() in response_lower for word in tc["requiere"])
        
        # El agente debe dar una tabla o lista, buscamos patrones de nombres o tablas
        has_list = "|" in response or "-" in response or "*" in response
        
        print_test(f"Respuesta generada en {elapsed}ms", has_keywords and has_list)
        if not has_keywords:
            print(f"        {Colors.FAIL}Error: Faltan palabras clave de negocio en la respuesta.{Colors.END}")
        
        # Mostrar un fragmento de la respuesta para verificación manual en el log
        print(f"        Respuesta (fragmento): {response[:200].replace(chr(10), ' ')}...")

if __name__ == "__main__":
    print(f"\n{Colors.BOLD}INICIANDO TEST DE INSIGHTS ACCIONABLES{Colors.END}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_tool_criteria()
    test_agent_business_logic()
    
    print(f"\n{Colors.BOLD}Tests completados.{Colors.END}\n")
