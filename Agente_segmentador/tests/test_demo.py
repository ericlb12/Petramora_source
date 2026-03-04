"""
DEMO para presentación — Agente Segmentador Petramora v6.0
14 preguntas conversacionales que muestran todas las capacidades.
Sesión compartida para flujo natural de conversación.

Ejecutar: python tests/test_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import uuid
from agent import chat


def main():
    session_id = str(uuid.uuid4())
    history = []

    preguntas = [
        # 1. Visión general
        "¿Cuántos clientes tenemos y cómo se distribuyen?",

        # 2. Acción inmediata — la pregunta estrella
        "¿A quién debería llamar hoy?",

        # 3. Profundización — por qué llamar a alguien
        "¿Por qué debería llamar al primero de la lista?",

        # 4. Detalle individual
        "Dime todo sobre ese cliente",

        # 5. Visión de negocio — métricas por segmento
        "¿Qué segmento genera más ingresos?",

        # 6. Top clientes
        "¿Quiénes son nuestros 5 mejores clientes por gasto histórico?",

        # 7. Estrategia de retención
        "¿Qué segmentos deberíamos priorizar para retención?",

        # 8. Clientes en riesgo
        "¿Qué clientes están en riesgo de irse?",

        # 9. Todos los segmentos con acciones
        "Dame un resumen de todos los segmentos con las acciones que debo tomar",

        # 10. Clientes nuevos con potencial
        "¿Tenemos clientes nuevos que valga la pena fidelizar?",

        # 11. Preparar llamada completa (get_recommendation)
        "Prepara la llamada al primero de la lista urgente de hoy. ¿Qué le ofrezco?",

        # 12. Historial de productos de ese cliente (get_customer_products)
        "¿Qué compra ese cliente habitualmente? Dame su historial de productos.",

        # 13. Familia dominante (get_customer_family)
        "¿En qué familia está especializado ese cliente?",

        # 14. Catálogo de productos disponibles (get_product_catalog)
        "¿Qué productos de CARNE tenemos disponibles en catálogo?",
    ]

    print("\n" + "=" * 70)
    print("  🎯 DEMO — AGENTE SEGMENTADOR PETRAMORA v6.0")
    print("  Análisis inteligente de 24,000+ clientes")
    print("=" * 70)

    for i, pregunta in enumerate(preguntas, 1):
        print(f"\n\n{'━' * 70}")
        print(f"  📌 Pregunta {i}/{len(preguntas)}")
        print(f"{'━' * 70}")
        print(f"\n  👤 {pregunta}\n")

        start = time.time()
        response = chat(pregunta, session_id, history)
        elapsed = time.time() - start

        print(f"  🤖 {response}")
        print(f"\n  ⏱ {elapsed:.1f}s")

    print(f"\n\n{'=' * 70}")
    print("  ✅ DEMO COMPLETADA")
    print("=" * 70)
    print("""
  Capacidades demostradas:
  ✓ Distribución de clientes por segmento
  ✓ Lista priorizada de clientes a contactar hoy (agrupada por segmento)
  ✓ Explicación de por qué contactar a cada cliente
  ✓ Detalle completo de un cliente con desglose anual
  ✓ Métricas de ingresos por segmento
  ✓ Ranking de mejores clientes por gasto histórico
  ✓ Recomendación estratégica de retención
  ✓ Identificación de clientes en riesgo de fuga
  ✓ Resumen de todos los segmentos con acciones sugeridas
  ✓ Identificación de clientes nuevos con potencial
  ✓ Recomendación comercial completa + guion de llamada (v6.0)
  ✓ Historial de productos por cliente (v6.0)
  ✓ Familia dominante de un cliente (v6.0)
  ✓ Catálogo de productos disponibles por familia (v6.0)
""")


if __name__ == "__main__":
    main()