"""
Pruebas de calidad de respuestas del Agente Segmentador
Muestra las respuestas completas para evaluar calidad manualmente
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from agent import chat

def test_query(pregunta, contexto=""):
    """Ejecuta una pregunta y muestra la respuesta completa"""
    print(f"\n{'─'*60}")
    if contexto:
        print(f"  Contexto: {contexto}")
    print(f"  Pregunta: {pregunta}")
    print(f"{'─'*60}")
    
    start = time.time()
    response = chat(pregunta)
    elapsed = int((time.time() - start) * 1000)
    
    print(f"\n{response}")
    print(f"\n  ⏱ {elapsed}ms")
    print(f"{'─'*60}")
    
    return response


def main():
    print("="*60)
    print("  PRUEBAS DE CALIDAD - AGENTE SEGMENTADOR")
    print("  Evaluar respuestas manualmente")
    print("="*60)
    
    # ── BLOQUE 1: Preguntas básicas de conteo ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 1: CONTEOS BÁSICOS")
    print(f"{'='*60}")
    
    test_query(
        "¿Cuántos clientes tenemos en total?",
        "Debería responder ~24,131 (feb 2026)"
    )
    
    test_query(
        "¿Cuántos Champions tenemos?",
        "Debería dar: Champion (64), Champions casi recurrente (995), Champions dormido (448). Total grupo: 1,507"
    )
    
    test_query(
        "¿Cuántos clientes están en riesgo de perderse?",
        "Debería hablar de: Rico perdido (2,357), Champions dormido (448), Oportunista perdido (14,674)"
    )
    
    # ── BLOQUE 2: Distribución ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 2: DISTRIBUCIÓN")
    print(f"{'='*60}")
    
    test_query(
        "Dame un resumen general de cómo están nuestros clientes",
        "Debería dar visión general por grupos con números, no solo listar"
    )
    
    test_query(
        "¿Cuál es el grupo más grande de clientes?",
        "Oportunistas: 79.8% (19,257 clientes)"
    )
    
    # ── BLOQUE 3: Métricas de gasto ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 3: GASTO Y VALOR")
    print(f"{'='*60}")
    
    test_query(
        "¿Cuánto gastan en promedio nuestros mejores clientes?",
        "Champions gasto promedio ~2,006€"
    )
    
    test_query(
        "¿Qué porcentaje del ingreso generan los Champions?",
        "~42.8%"
    )
    
    test_query(
        "¿Cuánto facturamos en total este mes?",
        "Feb 2026 = ~299,989€. DEBE ACLARAR que es gasto acumulado en el año, no solo del mes"
    )
    
    # ── BLOQUE 4: Evolución temporal ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 4: EVOLUCIÓN TEMPORAL")
    print(f"{'='*60}")
    
    test_query(
        "¿Cómo han evolucionado los Champions en los últimos 6 meses?",
        "Tendencia con números por mes. Caída dic→ene por reseteo anual"
    )
    
    test_query(
        "¿Estamos ganando o perdiendo clientes?",
        "Crecimiento general: base crece. Pero Oportunista perdido también crece"
    )
    
    # ── BLOQUE 5: Preguntas de negocio ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 5: PREGUNTAS DE NEGOCIO")
    print(f"{'='*60}")
    
    test_query(
        "¿Qué segmentos deberíamos priorizar para una campaña de retención?",
        "Rico perdido (2,357), Champions dormido (448)"
    )
    
    test_query(
        "¿Tenemos muchos clientes que solo han comprado una vez?",
        "Oportunista nuevo (3,967) + Oportunista perdido (14,674)"
    )
    
    # ── BLOQUE 6: Fuera de alcance ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 6: FUERA DE ALCANCE")
    print(f"{'='*60}")
    
    test_query(
        "¿Cuál es el producto más vendido?",
        "Debería indicar que no tiene datos de productos"
    )
    
    test_query(
        "¿Quién es nuestro cliente más valioso? Dame su nombre",
        "Debería indicar que no puede identificar clientes individuales"
    )
    
    # ── RESUMEN ──
    print(f"\n\n{'='*60}")
    print("  PRUEBAS COMPLETADAS")
    print(f"  Revisa las respuestas arriba para evaluar calidad.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()