"""
DEMO para presentación — Agente Segmentador Petramora v6.1
Flujo conversacional: lista de llamadas + recomendación por tipo de segmento.

Ejecutar: python tests/test_demo.py
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import uuid
from agent import chat


# Clientes representativos por segmento (top gasto de cada uno)
CLIENTES_POR_SEGMENTO = {
    # URGENTE (hoy)
    "Champions dormido": "Euroambrosías",
    "Rico perdido": "ARREAINVEST S.L",
    # IMPORTANTE (semana)
    "Champions casi recurrente": "ROOFTOP SMOKEHOUSE S.L",
    "Rico potencial": "VINSELECCION SA",
    # NORMAL (mes)
    "Oportunista con potencial": "Cristina San Juan",
    "Oportunista nuevo": "BIMBA Y LOLA LOGÍSTICA SLU",
    # BAJA
    "Activo Básico": "BORGWARNER EMISSIONS SYSTEMS SPAIN S.L.",
    "Champion": "JESÚS DOMÍNGUEZ",
    # Sin llamada individual
    "Oportunista perdido": "Manuel REGUEIRO GOMEZ",
}


def run_demo():
    session_id = str(uuid.uuid4())
    history = []
    results = []

    print("\n" + "=" * 70)
    print("  DEMO — AGENTE SEGMENTADOR PETRAMORA v6.1")
    print("  Lista de llamadas + recomendación por segmento")
    print("=" * 70)

    # --- Parte 1: A quién llamar hoy ---
    pregunta_llamadas = "¿A quién debo llamar hoy?"
    print(f"\n\n{'━' * 70}")
    print(f"  Pregunta 1: Lista de llamadas")
    print(f"{'━' * 70}")
    print(f"\n  Tu: {pregunta_llamadas}\n")

    start = time.time()
    response = chat(pregunta_llamadas, session_id, history)
    elapsed = time.time() - start

    print(f"  Agente: {response}")
    print(f"\n  ({elapsed:.1f}s)")
    results.append(("Lista de llamadas", elapsed, "OK" if len(response) > 100 else "CORTA"))

    # --- Parte 2: Recomendación por cada segmento ---
    for i, (segmento, cliente) in enumerate(CLIENTES_POR_SEGMENTO.items(), 2):
        # Nueva sesión por cliente para evitar confusión de contexto
        sess = str(uuid.uuid4())
        hist = []

        pregunta = f"¿Qué le ofrezco a {cliente}?"
        print(f"\n\n{'━' * 70}")
        print(f"  Pregunta {i}: {segmento}")
        print(f"{'━' * 70}")
        print(f"\n  Tu: {pregunta}\n")

        start = time.time()
        response = chat(pregunta, sess, hist)
        elapsed = time.time() - start

        print(f"  Agente: {response}")
        print(f"\n  ({elapsed:.1f}s)")

        # Validación básica
        status = "OK"
        resp_lower = response.lower()
        frases_error = ["error", "no se encontró", "no encontré", "no he encontrado", "no existe"]
        if any(frase in resp_lower for frase in frases_error):
            status = "ERROR"
        elif segmento == "Oportunista perdido" and "no se genera" not in resp_lower and "campañas" not in resp_lower:
            status = "REVISAR (debería indicar que no se llama individualmente)"
        elif len(response) < 50:
            status = "RESPUESTA CORTA"
        results.append((f"{segmento} ({cliente})", elapsed, status))

    # --- Resumen ---
    print(f"\n\n{'=' * 70}")
    print("  RESUMEN DE RESULTADOS")
    print("=" * 70)
    total_time = sum(r[1] for r in results)
    print(f"\n  {'Test':<55} {'Tiempo':>8} {'Estado':>10}")
    print(f"  {'-' * 75}")
    for name, elapsed, status in results:
        name_short = name[:54]
        color = "\033[92m" if status == "OK" else "\033[93m" if status.startswith("REVISAR") else "\033[91m"
        print(f"  {name_short:<55} {elapsed:>7.1f}s {color}{status}\033[0m")
    print(f"  {'-' * 75}")
    print(f"  {'TOTAL':<55} {total_time:>7.1f}s")

    ok_count = sum(1 for _, _, s in results if s == "OK")
    print(f"\n  {ok_count}/{len(results)} tests OK")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
