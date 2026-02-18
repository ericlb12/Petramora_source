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
        "Debería usar get_segment_distribution y dar número + porcentaje"
    )
    
    test_query(
        "¿Cuántos clientes están en riesgo de perderse?",
        "Debería identificar segmentos: En riesgo, A punto de dormir, Hibernando"
    )
    
    # ── BLOQUE 2: Distribución ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 2: DISTRIBUCIÓN")
    print(f"{'='*60}")
    
    test_query(
        "Dame un resumen general de cómo están nuestros clientes",
        "Debería dar visión general por grupos, no solo listar números"
    )
    
    test_query(
        "¿Cuál es el grupo más grande de clientes?",
        "Debería ser Otros u Oportunistas según los datos"
    )
    
    # ── BLOQUE 3: Métricas de gasto ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 3: GASTO Y VALOR")
    print(f"{'='*60}")
    
    test_query(
        "¿Cuánto gastan en promedio nuestros mejores clientes?",
        "Debería hablar de Champions, gasto promedio ~2,006€"
    )
    
    test_query(
        "¿Qué porcentaje del ingreso generan los Champions?",
        "Debería responder ~42.8%"
    )
    
    test_query(
        "¿Cuánto facturamos en total este mes?",
        "Feb 2026 = ~299,989€. Debería aclarar que es acumulado del año"
    )
    
    # ── BLOQUE 4: Evolución temporal ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 4: EVOLUCIÓN TEMPORAL")
    print(f"{'='*60}")
    
    test_query(
        "¿Cómo han evolucionado los Champions en los últimos 6 meses?",
        "Debería mostrar tendencia con números por mes"
    )
    
    test_query(
        "¿Estamos ganando o perdiendo clientes?",
        "Debería notar el crecimiento de 2,422 a 24,131 en 26 meses"
    )
    
    # ── BLOQUE 5: Preguntas de negocio ──
    print(f"\n\n{'='*60}")
    print("  BLOQUE 5: PREGUNTAS DE NEGOCIO")
    print(f"{'='*60}")
    
    test_query(
        "¿Qué segmentos deberíamos priorizar para una campaña de retención?",
        "Debería recomendar En riesgo, No puedo perderlo, A punto de dormir"
    )
    
    test_query(
        "¿Tenemos muchos clientes que solo han comprado una vez?",
        "Debería hablar de Oportunista nuevo y clientes de 1 COMPRA"
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