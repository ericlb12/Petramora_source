"""
Pruebas de Tools — Agente Segmentador Petramora v5.0
Prueba cada tool directamente sin pasar por el modelo.

Ejecutar: python tests/test_tools.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from datetime import datetime
from tools import (
    get_segment_distribution,
    get_segment_metrics,
    get_actionable_customers,
    get_customer_detail,
)


class Colors:
    OK = '\033[92m'
    FAIL = '\033[91m'
    INFO = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title):
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print(f"   {title}")
    print(f"{'=' * 60}{Colors.END}")


def print_test(name, passed, details=""):
    status = f"{Colors.OK}PASS{Colors.END}" if passed else f"{Colors.FAIL}FAIL{Colors.END}"
    print(f"  [{status}] {name}")
    if details:
        print(f"        {Colors.INFO}{details}{Colors.END}")


def test_distribution():
    print_header("1. get_segment_distribution")

    start = time.time()
    result = get_segment_distribution()
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Retorna datos", has_data, f"{elapsed}ms")

    if has_data:
        total = result['total_clientes']
        n_segmentos = len(result['por_segmento_rfm'])
        print_test(f"Total clientes: {total:,}", total > 0)
        print_test(f"Segmentos encontrados: {n_segmentos}", n_segmentos > 0)
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)


def test_metrics():
    print_header("2. get_segment_metrics")

    # Sin filtro
    start = time.time()
    result = get_segment_metrics()
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Sin filtro", has_data, f"{elapsed}ms")

    if has_data:
        gasto = result['gasto_total_global']
        print_test(f"Gasto global: {gasto:,.2f}€", gasto > 0)

    # Con filtro
    start = time.time()
    result = get_segment_metrics(segmento="Champion")
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Filtro 'Champion'", has_data, f"{elapsed}ms")


def test_actionable_today():
    print_header("3. get_actionable_customers — criterio 'today'")

    start = time.time()
    result = get_actionable_customers(criterio="today", limite=5)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Retorna datos", has_data, f"{elapsed}ms")

    if has_data:
        n_grupos = len(result.get('grupos', []))
        n_clientes = result['total_encontrados']
        print_test(f"Grupos de segmento: {n_grupos}", n_grupos > 0)
        print_test(f"Clientes totales: {n_clientes}", n_clientes > 0)
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

        # Verificar que los grupos tienen prioridad y acción
        for grupo in result.get('grupos', []):
            has_fields = all(k in grupo for k in ['segmento', 'prioridad', 'accion', 'clientes'])
            print_test(f"  Grupo '{grupo['segmento']}' tiene campos completos", has_fields,
                       f"{len(grupo['clientes'])} clientes")


def test_actionable_all_segments():
    print_header("4. get_actionable_customers — criterio 'all_segments'")

    start = time.time()
    result = get_actionable_customers(criterio="all_segments", limite=3)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Retorna datos", has_data, f"{elapsed}ms")

    if has_data:
        n_grupos = len(result.get('grupos', []))
        print_test(f"Cubre {n_grupos} segmentos", n_grupos >= 5)


def test_actionable_criteria():
    print_header("5. get_actionable_customers — otros criterios")

    criterios = [
        ("churn_risk", "Riesgo de fuga"),
        ("growth_potential", "Potencial de crecimiento"),
        ("inactive_vip", "VIPs inactivos"),
        ("new_high_value", "Nuevos alto valor"),
        ("top_historical", "Top histórico"),
    ]

    for crit, desc in criterios:
        start = time.time()
        result = get_actionable_customers(criterio=crit, limite=5)
        elapsed = int((time.time() - start) * 1000)

        has_data = 'error' not in result
        n = result.get('total_encontrados', 0)
        print_test(f"{desc} ({crit})", has_data, f"{n} clientes, {elapsed}ms")


def test_customer_detail():
    print_header("6. get_customer_detail")

    # Primero obtener un nombre real de la base
    dist = get_actionable_customers(criterio="top_historical", limite=1)
    if not dist.get('clientes'):
        print_test("No se pudo obtener un cliente para probar", False)
        return

    nombre = dist['clientes'][0]['cliente_id']

    # Búsqueda exacta
    start = time.time()
    result = get_customer_detail(cliente_id=nombre)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test(f"Búsqueda exacta: '{nombre}'", has_data, f"{elapsed}ms")

    if has_data:
        print_test("Tiene segmento", bool(result.get('segmento_rfm')))
        print_test("Tiene acción sugerida", bool(result.get('accion_sugerida')))
        print_test("Tiene desglose anual", bool(result.get('desglose_anual')))
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

    # Búsqueda parcial (fuzzy)
    start = time.time()
    result = get_customer_detail(cliente_id=nombre[:5])
    elapsed = int((time.time() - start) * 1000)

    is_ok = 'error' not in result or 'coincidencias' in result
    print_test(f"Búsqueda parcial: '{nombre[:5]}'", is_ok, f"{elapsed}ms")

    # Búsqueda inexistente
    start = time.time()
    result = get_customer_detail(cliente_id="ZZZZZ_NO_EXISTE_12345")
    elapsed = int((time.time() - start) * 1000)

    has_error = 'error' in result
    print_test("Cliente inexistente retorna error", has_error, f"{elapsed}ms")


def main():
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print("   PRUEBAS DE TOOLS — AGENTE SEGMENTADOR v5.0")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}{Colors.END}")

    test_distribution()
    test_metrics()
    test_actionable_today()
    test_actionable_all_segments()
    test_actionable_criteria()
    test_customer_detail()

    print(f"\n{Colors.BOLD}Tests completados.{Colors.END}\n")


if __name__ == "__main__":
    main()