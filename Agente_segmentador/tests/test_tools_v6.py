"""
Pruebas de Tools v6.0 — Agente Segmentador Petramora
Prueba las 4 nuevas herramientas directamente sin pasar por el modelo.

Ejecutar: python tests/test_tools_v6.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from datetime import datetime
from tools import (
    get_actionable_customers,
    get_customer_products,
    get_customer_family,
    get_product_catalog,
    get_recommendation,
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


def _get_real_client_name():
    """Obtiene un nombre de cliente real desde la base de datos."""
    dist = get_actionable_customers(criterio="top_historical", limite=1)
    if dist.get('clientes'):
        return dist['clientes'][0]['cliente_id']
    # Fallback: buscar en grupos
    for grupo in dist.get('grupos', []):
        if grupo.get('clientes'):
            return grupo['clientes'][0]['cliente_id']
    return None


def test_customer_products(nombre_cliente):
    print_header("1. get_customer_products")

    # Búsqueda exacta
    start = time.time()
    result = get_customer_products(cliente_id=nombre_cliente)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test(f"Búsqueda exacta: '{nombre_cliente}'", has_data, f"{elapsed}ms")

    if has_data:
        total_ventas = result.get('total_ventas', 0)
        n_familias = len(result.get('distribucion_familias', []))
        n_productos = len(result.get('top_productos', []))

        print_test(f"Total ventas: {total_ventas:,.2f}€", total_ventas > 0)
        print_test(f"Familias encontradas: {n_familias}", n_familias > 0)
        print_test(f"Top productos: {n_productos}", n_productos > 0)
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

        # Verificar estructura de una familia
        if result.get('distribucion_familias'):
            fam = result['distribucion_familias'][0]
            has_fields = all(k in fam for k in ['familia', 'ventas', 'porcentaje'])
            print_test("Familia tiene campos completos (familia/ventas/porcentaje)", has_fields,
                       f"familia={fam.get('familia')}, {fam.get('porcentaje')}%")

        # Verificar estructura de un producto
        if result.get('top_productos'):
            prod = result['top_productos'][0]
            has_fields = all(k in prod for k in ['descripcion', 'familia', 'ventas_total', 'porcentaje'])
            print_test("Producto tiene campos completos", has_fields,
                       f"familia={prod.get('familia')}, ventas={prod.get('ventas_total'):,.2f}€")

    # Búsqueda parcial (fuzzy)
    start = time.time()
    result = get_customer_products(cliente_id=nombre_cliente[:5])
    elapsed = int((time.time() - start) * 1000)

    is_ok = 'error' not in result or 'coincidencias' in result
    print_test(f"Búsqueda parcial: '{nombre_cliente[:5]}'", is_ok, f"{elapsed}ms")

    # Cliente inexistente
    start = time.time()
    result = get_customer_products(cliente_id="ZZZZZ_NO_EXISTE_12345")
    elapsed = int((time.time() - start) * 1000)

    has_error = 'error' in result
    print_test("Cliente inexistente retorna error", has_error, f"{elapsed}ms")


def test_customer_family(nombre_cliente):
    print_header("2. get_customer_family")

    # Búsqueda exacta
    start = time.time()
    result = get_customer_family(cliente_id=nombre_cliente)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test(f"Búsqueda exacta: '{nombre_cliente}'", has_data, f"{elapsed}ms")

    if has_data:
        familia = result.get('familia_dominante', '')
        tipo_perfil = result.get('tipo_perfil', '')
        n_familias = len(result.get('distribucion_familias', []))

        print_test(f"Familia dominante: '{familia}'", bool(familia))
        print_test(f"Tiene tipo_perfil: '{tipo_perfil}'", bool(tipo_perfil))
        print_test(f"Distribución de familias: {n_familias}", n_familias > 0)
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

        # La familia puede ser "Mixto" o un nombre real
        es_valido = familia == "Mixto" or (familia and familia != "Sin Clasificar")
        print_test("Familia tiene valor válido (Mixto o nombre real)", es_valido,
                   f"familia={familia!r}")

    # Búsqueda parcial (fuzzy)
    start = time.time()
    result = get_customer_family(cliente_id=nombre_cliente[:5])
    elapsed = int((time.time() - start) * 1000)

    is_ok = 'error' not in result or 'coincidencias' in result
    print_test(f"Búsqueda parcial: '{nombre_cliente[:5]}'", is_ok, f"{elapsed}ms")

    # Cliente inexistente
    start = time.time()
    result = get_customer_family(cliente_id="ZZZZZ_NO_EXISTE_12345")
    elapsed = int((time.time() - start) * 1000)

    has_error = 'error' in result
    print_test("Cliente inexistente retorna error", has_error, f"{elapsed}ms")


def test_product_catalog():
    print_header("3. get_product_catalog")

    # Sin filtro (todas las familias, ordenado por margen)
    start = time.time()
    result = get_product_catalog()
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Sin filtro de familia (por margen)", has_data, f"{elapsed}ms")

    if has_data:
        n_productos = len(result.get('productos', []))
        print_test(f"Retorna {n_productos} productos", n_productos > 0)
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

        # Verificar estructura de un producto
        if result.get('productos'):
            prod = result['productos'][0]
            has_fields = all(k in prod for k in ['codigo_producto', 'familia', 'precio_con_iva', 'margen_teorico_pct'])
            print_test("Producto tiene campos completos", has_fields,
                       f"familia={prod.get('familia')}, precio={prod.get('precio_con_iva'):.2f}€")

    # Con filtro de familia — CARNE
    start = time.time()
    result = get_product_catalog(familia="CARNE", limite=5)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Filtro familia 'CARNE'", has_data, f"{elapsed}ms")

    if has_data:
        n = len(result.get('productos', []))
        all_carne = all(
            (p.get('familia') or '').upper() == 'CARNE'
            for p in result.get('productos', [])
        )
        print_test(f"Solo devuelve CARNE ({n} productos)", all_carne and n > 0)

    # Con filtro orden_por precio
    start = time.time()
    result = get_product_catalog(familia="QUESOS", orden_por="precio", limite=5)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test("Filtro 'QUESOS' ordenado por precio", has_data, f"{elapsed}ms")

    if has_data:
        prods = result.get('productos', [])
        precios = [p.get('precio_con_iva', 0) for p in prods]
        is_desc = all(precios[i] >= precios[i+1] for i in range(len(precios)-1)) if len(precios) > 1 else True
        print_test(f"Orden descendente de precio verificado", is_desc,
                   f"precios={[round(p, 2) for p in precios[:3]]}")

    # Familia inexistente — fuzzy fallback o error limpio (no excepción)
    start = time.time()
    result = get_product_catalog(familia="FAMILIA_INEXISTENTE_ZZZ")
    elapsed = int((time.time() - start) * 1000)

    no_crash = isinstance(result, dict)
    print_test("Familia inexistente no lanza excepción", no_crash, f"{elapsed}ms")


def test_recommendation(nombre_cliente):
    print_header("4. get_recommendation")

    # Búsqueda exacta
    start = time.time()
    result = get_recommendation(cliente_id=nombre_cliente)
    elapsed = int((time.time() - start) * 1000)

    has_data = 'error' not in result
    print_test(f"Búsqueda exacta: '{nombre_cliente}'", has_data, f"{elapsed}ms")

    if has_data:
        segmento = result.get('segmento_rfm', '')
        llamada = result.get('llamada_individual')

        print_test("Tiene segmento_rfm", bool(segmento), f"segmento='{segmento}'")
        print_test("Tiene llamada_individual (bool)", isinstance(llamada, bool),
                   f"llamada_individual={llamada}")
        print_test("Tiene tabla_formateada", 'tabla_formateada' in result)

        if llamada:
            print_test("Tiene estrategia", bool(result.get('estrategia')))
            print_test("Tiene nota_comercial", bool(result.get('nota_comercial')))
            print_test("Tiene productos_recomendados (lista)", isinstance(result.get('productos_recomendados'), list))
            print_test("Tiene familia_dominante", bool(result.get('familia_dominante')))

    # Búsqueda parcial (fuzzy)
    start = time.time()
    result = get_recommendation(cliente_id=nombre_cliente[:5])
    elapsed = int((time.time() - start) * 1000)

    is_ok = 'error' not in result or 'coincidencias' in result
    print_test(f"Búsqueda parcial: '{nombre_cliente[:5]}'", is_ok, f"{elapsed}ms")

    # Oportunista perdido → llamada_individual=False
    dist_op = get_actionable_customers(criterio="all_segments", limite=1)
    op_cliente = None
    for grupo in dist_op.get('grupos', []):
        if grupo.get('segmento') == 'Oportunista perdido' and grupo.get('clientes'):
            op_cliente = grupo['clientes'][0]['cliente_id']
            break

    if op_cliente:
        start = time.time()
        result = get_recommendation(cliente_id=op_cliente)
        elapsed = int((time.time() - start) * 1000)

        llamada = result.get('llamada_individual')
        print_test("Oportunista perdido → llamada_individual=False",
                   llamada is False,
                   f"cliente='{op_cliente}', {elapsed}ms")
    else:
        print_test("Oportunista perdido (segmento no presente en DB)", True,
                   "Omitido — sin clientes en ese segmento")

    # Cliente inexistente
    start = time.time()
    result = get_recommendation(cliente_id="ZZZZZ_NO_EXISTE_12345")
    elapsed = int((time.time() - start) * 1000)

    has_error = 'error' in result
    print_test("Cliente inexistente retorna error", has_error, f"{elapsed}ms")


def main():
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print("   PRUEBAS DE TOOLS v6.0 — AGENTE SEGMENTADOR")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}{Colors.END}")

    # Obtener un cliente real una sola vez
    print(f"\n  {Colors.INFO}Obteniendo cliente real de la base...{Colors.END}")
    nombre_cliente = _get_real_client_name()
    if not nombre_cliente:
        print(f"  {Colors.FAIL}No se pudo obtener un cliente real. Verifica la conexión a Supabase.{Colors.END}\n")
        return

    print(f"  {Colors.OK}Cliente de prueba: '{nombre_cliente}'{Colors.END}")

    test_customer_products(nombre_cliente)
    test_customer_family(nombre_cliente)
    test_product_catalog()
    test_recommendation(nombre_cliente)

    print(f"\n{Colors.BOLD}Tests completados.{Colors.END}\n")


if __name__ == "__main__":
    main()
