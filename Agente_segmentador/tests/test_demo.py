"""
DEMO para presentación — Agente Segmentador Petramora v5.0
10 preguntas conversacionales que muestran todas las capacidades.
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
    ]

    print("\n" + "=" * 70)
    print("  🎯 DEMO — AGENTE SEGMENTADOR PETRAMORA v5.0")
    print("  Análisis inteligente de 24,000+ clientes")
    print("=" * 70)

    for i, pregunta in enumerate(preguntas, 1):
        print(f"\n\n{'━' * 70}")
        print(f"  📌 Pregunta {i}/10")
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
""")


if __name__ == "__main__":
    main()