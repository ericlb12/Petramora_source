import pandas as pd
import sys
import os

# Añadir el directorio del ETL al path para poder importar
sys.path.append(os.path.abspath("ETL-Segmentador-Petramora"))
from etl_segmentador import calculate_segments

def test_logic():
    # Casos de prueba basados en la matriz del usuario
    test_cases = [
        # 1. Champion: R >= 4, F >= 4, M >= 4
        {"r": 10, "f": 25, "m": 500, "expected": "Champion"}, # 555
        {"r": 60, "f": 15, "m": 300, "expected": "Champion"}, # 445
        
        # 2. Champions casi recurrente: R >= 4, M >= 4, (F 2-3 o M=4)
        {"r": 15, "f": 2, "m": 400, "expected": "Champions casi recurrente"}, # 525
        {"r": 45, "f": 5, "m": 200, "expected": "Champions casi recurrente"}, # 434
        
        # 3. Champions dormido: R 2-3, F >= 3, M >= 4
        {"r": 100, "f": 5, "m": 300, "expected": "Champions dormido"}, # 335
        {"r": 200, "f": 10, "m": 150, "expected": "Champions dormido"}, # 244
        
        # 4. Rico perdido: R <= 2, M >= 4
        {"r": 400, "f": 1, "m": 500, "expected": "Rico perdido"}, # 115 (El "VIP que desapareció")
        {"r": 250, "f": 10, "m": 300, "expected": "Rico perdido"}, # 245
        
        # 5. Rico potencial: R >= 3, F = 1, M >= 4
        {"r": 5, "f": 1, "m": 400, "expected": "Rico potencial"}, # 515
        {"r": 150, "f": 1, "m": 200, "expected": "Rico potencial"}, # 314
        
        # 6. Activo Básico: R >= 4, F >= 2, M <= 3
        {"r": 15, "f": 2, "m": 50, "expected": "Activo Básico"}, # 522
        {"r": 10, "f": 30, "m": 20, "expected": "Activo Básico"}, # 551 (El "Leal de bajo presupuesto")
        
        # 7. Oportunista con potencial: R = 3, F >= 2, M <= 4
        {"r": 120, "f": 3, "m": 80, "expected": "Oportunista con potencial"}, # 323
        {"r": 150, "f": 5, "m": 140, "expected": "Oportunista con potencial"}, # 334
        
        # 8. Oportunista nuevo: R >= 3, F = 1, M <= 3
        {"r": 10, "f": 1, "m": 30, "expected": "Oportunista nuevo"}, # 511
        {"r": 100, "f": 1, "m": 60, "expected": "Oportunista nuevo"}, # 312
        
        # 9. Oportunista perdido: Fallback (R <= 2, M <= 3)
        {"r": 200, "f": 1, "m": 20, "expected": "Oportunista perdido"}, # 211
        {"r": 400, "f": 2, "m": 45, "expected": "Oportunista perdido"}, # 122
    ]

    print(f"{'Caso':<30} | {'Score':<7} | {'Esperado':<25} | {'Resultado':<25} | {'Status'}")
    print("-" * 110)

    for case in test_cases:
        row = {
            'dias_recencia': case['r'],
            'num_facturas': case['f'],
            'gasto_total': case['m']
        }
        res = calculate_segments(row)
        score = res[3]
        segmento = res[4]
        
        status = "OK" if segmento == case['expected'] else f"ERROR (Got: {segmento})"
        print(f"{str(case['r'])+'/'+str(case['f'])+'/'+str(case['m']):<30} | {score:<7} | {case['expected']:<25} | {segmento:<25} | {status}")

if __name__ == "__main__":
    test_logic()
