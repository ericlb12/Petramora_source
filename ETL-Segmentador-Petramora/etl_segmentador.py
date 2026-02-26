"""
ETL Segmentador Petramora (v5.0 — Simplificado)
Solo sube el último mes con 11 columnas esenciales.
Fuente de verdad: Power BI / DAX.

Columnas que sube a Supabase (11):
  - cliente_id, fecha_corte, fecha_ultima_compra, segmento_rfm
  - ventas_2024, ventas_2025, ventas_2026
  - facturas_2024, facturas_2025, facturas_2026
  - gasto_total

Derivados en las tools del agente (NO en el ETL):
  - dias_recencia = hoy - fecha_ultima_compra
"""

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client
import os
import sys
import math

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ─────────────────────────────────────────────
# Mapeo de columnas: Power BI CSV → Supabase
# ─────────────────────────────────────────────
CSV_COLS = {
    'ClienteRelacionado': 'cliente_id',
    'Fecha_Fin_Mes': 'fecha_corte',
    'UltimaFactura': 'fecha_ultima_compra',
    'Ventas_2024_c': 'ventas_2024',
    'Ventas_2025_c': 'ventas_2025',
    'Ventas_2026_c': 'ventas_2026',
    'Facturas_2024_c': 'facturas_2024',
    'Facturas_2025_c': 'facturas_2025',
    'Facturas_2026_c': 'facturas_2026',
    'Gasto_Total_c': 'gasto_total',
}

# La columna de segmento tiene encoding raro — se busca dinámicamente
SEGMENTO_COL_PATTERN = 'ltimo global'

# Columnas finales que se suben a Supabase
SUPABASE_COLS = [
    'cliente_id',
    'fecha_corte',
    'fecha_ultima_compra',
    'segmento_rfm',
    'ventas_2024',
    'ventas_2025',
    'ventas_2026',
    'facturas_2024',
    'facturas_2025',
    'facturas_2026',
    'gasto_total',
]


def convert_european_number(value):
    """Convierte números con formato europeo (coma decimal) a float limpio."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if not (math.isinf(value) or math.isnan(value)) else 0.0
    try:
        val_str = str(value).replace(',', '.')
        result = float(val_str)
        return result if not (math.isinf(result) or math.isnan(result)) else 0.0
    except (ValueError, TypeError):
        return 0.0


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma el CSV de Power BI a formato Supabase.
    Solo mantiene las filas del último mes.
    """
    print("\n[Transform] Limpiando y mapeando columnas...")

    # Limpiar cabeceras (BOM, espacios)
    df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]

    # ── Buscar columna de segmento dinámicamente (encoding variable) ──
    seg_col = None
    for c in df.columns:
        if SEGMENTO_COL_PATTERN in c and 'Segmento' in c:
            seg_col = c
            break
    if not seg_col:
        raise ValueError(f"No se encontró columna de segmento con patrón '{SEGMENTO_COL_PATTERN}'. "
                         f"Columnas disponibles: {list(df.columns)}")
    print(f"   Columna de segmento encontrada: '{seg_col}'")

    # Verificar que las columnas del mapeo existen
    missing = [c for c in CSV_COLS.keys() if c not in df.columns]
    if missing:
        for m in missing:
            found = [c for c in df.columns if m.lower() in c.lower()]
            if found:
                print(f"   [Fallback] '{m}' no encontrada, usando '{found[0]}'")
                df = df.rename(columns={found[0]: m})
            else:
                raise ValueError(f"Columna requerida no encontrada: '{m}'. "
                                 f"Columnas disponibles: {list(df.columns)}")

    # Renombrar columnas del mapeo
    df_clean = df.rename(columns=CSV_COLS)

    # Renombrar columna de segmento
    df_clean = df_clean.rename(columns={seg_col: 'segmento_rfm'})

    # Seleccionar solo las columnas que necesitamos
    df_clean = df_clean[SUPABASE_COLS].copy()

    # ── Filtrar solo el último mes ──
    df_clean['fecha_corte_dt'] = pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce')
    ultimo_mes = df_clean['fecha_corte_dt'].max()
    print(f"   Último mes detectado: {ultimo_mes.strftime('%Y-%m-%d')}")

    df_clean = df_clean[df_clean['fecha_corte_dt'] == ultimo_mes].copy()
    df_clean = df_clean.drop(columns=['fecha_corte_dt'])
    print(f"   Filas después de filtro último mes: {len(df_clean):,}")

    # ── Limpieza de datos ──

    # Números: formato europeo + NaN/Inf
    for col in ['ventas_2024', 'ventas_2025', 'ventas_2026', 'gasto_total']:
        df_clean[col] = df_clean[col].apply(convert_european_number)
    for col in ['facturas_2024', 'facturas_2025', 'facturas_2026']:
        df_clean[col] = df_clean[col].apply(convert_european_number).astype(int)

    # Fechas: convertir a YYYY-MM-DD
    df_clean['fecha_corte'] = (
        pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )
    df_clean['fecha_ultima_compra'] = (
        pd.to_datetime(df_clean['fecha_ultima_compra'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )

    # Texto: limpiar segmento
    df_clean['segmento_rfm'] = df_clean['segmento_rfm'].fillna('Sin Clasificar').str.strip()

    # Limpieza final JSON (NaN → None)
    df_clean = df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0})

    # Deduplicar por cliente (PK)
    df_clean = df_clean.drop_duplicates(subset=['cliente_id'])

    print(f"   Registros finales: {len(df_clean):,}")
    print(f"   Segmentos encontrados: {df_clean['segmento_rfm'].unique().tolist()}")

    return df_clean


def load(df: pd.DataFrame, batch_size: int = 500):
    """Borra la tabla y carga datos nuevos en lotes."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan credenciales de Supabase en .env")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    records = df.to_dict('records')
    total = len(records)

    # ── Paso 1: Borrar datos existentes ──
    print(f"\n[Load] Borrando datos existentes de Supabase...")
    try:
        supabase.table('segmentacion_clientes_raw').delete().neq('cliente_id', '').execute()
        print(f"   ✅ Tabla limpiada")
    except Exception as e:
        print(f"   ⚠️  Error al borrar: {str(e)[:100]}")
        print(f"   Continuando con upsert...")

    # ── Paso 2: Insertar datos nuevos ──
    print(f"[Load] Subiendo {total:,} registros a Supabase...")

    errores = 0
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        try:
            supabase.table('segmentacion_clientes_raw').upsert(
                batch, on_conflict='cliente_id,fecha_corte'
            ).execute()
            if (i + batch_size) % 5000 == 0 or (i + batch_size) >= total:
                print(f"   Progreso: {min(i + batch_size, total):,}/{total:,}")
        except Exception as e:
            errores += 1
            print(f"   [Error] Lote {i // batch_size + 1}: {str(e)[:200]}")

    if errores:
        print(f"\n   ⚠️  {errores} lotes con error")
    else:
        print(f"\n   ✅ Carga completada sin errores")


def main():
    INPUT_FILE = "Segmento_RFM_raw.csv"
    PATH = INPUT_FILE if os.path.exists(INPUT_FILE) else os.path.join("ETL-Segmentador-Petramora", INPUT_FILE)

    print(f"\n{'=' * 60}")
    print(f"ETL PETRAMORA v5.0 — Simplificado (solo último mes)")
    print(f"{'=' * 60}")

    try:
        df = pd.read_csv(PATH, sep=';', encoding='utf-8-sig', low_memory=False)
        print(f"[Extract] Leídas {len(df):,} filas, {len(df.columns)} columnas")
        load(transform(df))
    except FileNotFoundError:
        print(f"\n[ERROR] Archivo no encontrado: {PATH}")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")


if __name__ == "__main__":
    main()