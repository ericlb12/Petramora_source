"""
Pruebas de calidad v3.3 — Agente Segmentador Petramora
Sesión compartida por bloque para mantener contexto conversacional.
Ejecutar: python tests/test_quality_v3.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import uuid
from agent import chat


class TestSession:
    """Mantiene sesión y historial por bloque."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.session_id = str(uuid.uuid4())
        self.history = []

    def ask(self, pregunta, contexto=""):
        print(f"\n{'─' * 70}")
        if contexto:
            print(f"  📋 {contexto}")
        print(f"  ❓ {pregunta}")
        print(f"{'─' * 70}")

        start = time.time()
        response = chat(pregunta, self.session_id, self.history)
        elapsed = int((time.time() - start) * 1000)

        print(f"\n{response}")
        print(f"\n  ⏱ {elapsed}ms")
        print(f"{'─' * 70}")
        return response


def main():
    s = TestSession()

    print("=" * 70)
    print("  PRUEBAS DE CALIDAD v3.3 — AGENTE SEGMENTADOR")
    print("=" * 70)

    # ── BLOQUE 1: A quién llamar (sesión compartida) ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 1: ¿A QUIÉN LLAMAR? (con contexto)")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿A quién debo llamar hoy?",
        "Debe mostrar Champions dormido primero, ordenados por gasto histórico"
    )

    s.ask(
        "¿Por qué?",
        "FIX: Con sesión compartida, debe explicar SIN repetir la tabla"
    )

    # ── BLOQUE 2: Distribución ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 2: DISTRIBUCIÓN")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Cuántos clientes tenemos en total?",
        "Debe responder ~24,260"
    )

    s.ask(
        "¿Cómo se distribuyen por segmento?",
        "Debe mostrar tabla con los 9 segmentos + Sin Clasificar"
    )

    s.ask(
        "¿Cuántos Champions tenemos?",
        "Debe decir 60 Champions (con contexto de distribución anterior)"
    )

    # ── BLOQUE 3: Evolución temporal ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 3: EVOLUCIÓN TEMPORAL")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Cómo evolucionaron los Champions dormido en los últimos 6 meses?",
        "CRÍTICO: Debe mostrar 281→281→281→281→437→437 exactos"
    )

    s.ask(
        "¿Y los Champions?",
        "Con contexto, debe entender que se refiere a Champion y mostrar 255→60"
    )

    s.ask(
        "¿Estamos ganando o perdiendo clientes?",
        "Debe notar crecimiento general 21K→24K"
    )

    # ── BLOQUE 4: Historial individual ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 4: HISTORIAL INDIVIDUAL")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Beatriz Pizarro siempre fue Champions dormido?",
        "Debe mostrar 3 cambios de segmento"
    )

    s.ask(
        "¿Y cuánto ha gastado en total?",
        "Con contexto, debe responder €786.77 sin volver a llamar la tool"
    )

    s.ask(
        "Dime todo sobre Jose Luis Pego Alonso",
        "Historial completo con cambios Champion → casi recurrente → dormido"
    )

    # ── BLOQUE 5: Top clientes ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 5: TOP CLIENTES")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Cuáles son los clientes que más han comprado históricamente?",
        "Debe usar criterio top_historical"
    )

    s.ask(
        "¿Quiénes son mis 5 mejores clientes?",
        "Top 5 por gasto histórico"
    )

    # ── BLOQUE 6: Métricas (FIX: debe aclarar que es mensual) ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 6: MÉTRICAS (debe aclarar que es gasto mensual)")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Cuánto gastan en promedio los Champions?",
        "FIX: Debe aclarar que €27.09 es el promedio del MES actual, no histórico"
    )

    s.ask(
        "¿Qué segmento genera más ingresos?",
        "FIX: Debe aclarar que los ingresos son del mes, no acumulados"
    )

    # ── BLOQUE 7: Fuera de alcance ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 7: FUERA DE ALCANCE")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Cuál es el producto más vendido?",
        "Debe indicar que no tiene datos de productos"
    )

    s.ask(
        "¿Qué canal de venta funciona mejor?",
        "Debe indicar que no tiene datos de canales"
    )

    # ── BLOQUE 8: Retención (FIX: debe mencionar Champions dormido) ──
    print(f"\n\n{'=' * 70}")
    print("  BLOQUE 8: RETENCIÓN (debe mencionar Champions dormido)")
    print(f"{'=' * 70}")
    s.reset()

    s.ask(
        "¿Qué segmentos deberíamos priorizar para retención?",
        "FIX: Debe mencionar Champions dormido, Rico perdido, Champions casi recurrente"
    )

    s.ask(
        "Dame nombres concretos de Champions dormido a contactar",
        "Debe usar get_actionable_customers con today o inactive_vip"
    )

    s.ask(
        "¿Tenemos muchos clientes que solo han comprado una vez?",
        "Debe hablar de Oportunista nuevo (4,148)"
    )

    # ── RESUMEN ──
    print(f"\n\n{'=' * 70}")
    print("  ✅ PRUEBAS COMPLETADAS — 20 preguntas en 8 bloques")
    print(f"  Revisa especialmente los marcados con FIX.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()