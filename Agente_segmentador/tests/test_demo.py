"""
DEMO para presentación — Agente Segmentador Petramora
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
        # 1. Visión general — ¿cuántos clientes tenemos?
        "¿Cuántos clientes tenemos y cómo se distribuyen?",

        # 2. Acción inmediata — la pregunta estrella
        "¿A quién debería llamar hoy?",

        # 3. Profundización bajo demanda
        "¿Por qué Jose Luis Pego es el primero de la lista?",

        # 4. Historial individual — poder ver la historia de un cliente
        "Muéstrame todo el historial de Jose Luis Pego Alonso",

        # 5. Tendencia preocupante — evolución de Champions
        "¿Cómo han evolucionado nuestros Champions en los últimos 6 meses?",

        # 6. Visión de negocio — entender qué está pasando
        "¿Estamos ganando o perdiendo clientes valiosos?",

        # 7. Top clientes — saber quiénes son los VIPs
        "¿Quiénes son nuestros 5 mejores clientes por gasto histórico?",

        # 8. Estrategia de retención — recomendación inteligente
        "¿Qué segmentos deberíamos priorizar para retención?",

        # 9. Métricas de negocio — ingresos por segmento
        "¿Qué segmento nos genera más ingresos este mes?",

        # 10. Cierre — clientes nuevos con potencial
        "¿Tenemos clientes nuevos que valga la pena fidelizar?",
    ]

    print("\n" + "=" * 70)
    print("  🎯 DEMO — AGENTE SEGMENTADOR PETRAMORA")
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
  ✓ Lista priorizada de clientes a contactar hoy
  ✓ Explicación inteligente de por qué contactar a cada cliente
  ✓ Historial completo de un cliente individual
  ✓ Evolución temporal de segmentos (tendencias)
  ✓ Análisis de ganancia/pérdida de clientes valiosos
  ✓ Ranking de mejores clientes por gasto histórico
  ✓ Recomendación estratégica de retención
  ✓ Métricas de ingresos por segmento
  ✓ Identificación de clientes nuevos con potencial
""")


if __name__ == "__main__":
    main()