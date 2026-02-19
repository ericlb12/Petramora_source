"""
ETL Segmentador Petramora (v3.1 — DAX Direct)
Importa segmentación RFM directamente del DAX de Power BI.
Ya NO calcula segmentos en Python — la fuente de verdad es Power BI.

Columnas que sube a Supabase (9):
  - cliente_id, fecha_corte, segmento_rfm
  - gasto_total (mensual, dato atómico)
  - num_facturas (mensual, dato atómico)
  - fecha_ultima_compra
  - seg_recencia, seg_frecuencia, seg_monetario

Derivados en las tools del agente (NO en el ETL):
  - dias_recencia = hoy - fecha_ultima_compra
  - gasto_historico = SUM(gasto_total) de todas las filas del cliente
"""

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client
import os
import math

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ─────────────────────────────────────────────
# Mapeo de columnas: Power BI CSV → Supabase
# Solo 9 columnas — lo mínimo necesario
# ─────────────────────────────────────────────
CSV_COLS = {
    'ClienteRelacionado': 'cliente_id',
    'Fecha_Fin_Mes': 'fecha_corte',
    'UltimaFactura': 'fecha_ultima_compra',
    'Facturas': 'num_facturas',
    'VentasTotales': 'gasto_total',
    'Segmento RFM seleccionada': 'segmento_rfm',
    'Recencia Seleccionada': 'seg_recencia',
    'Frecuencia Seleccionada': 'seg_frecuencia',
    'Monetario Seleccionada': 'seg_monetario',
}

# Columnas finales que se suben a Supabase
SUPABASE_COLS = [
    'cliente_id',
    'fecha_corte',
    'fecha_ultima_compra',
    'num_facturas',
    'gasto_total',
    'segmento_rfm',
    'seg_recencia',
    'seg_frecuencia',
    'seg_monetario',
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
    NO calcula segmentos — los importa directamente del DAX.
    """
    print("\n[Transform] Limpiando y mapeando columnas...")

    # Limpiar cabeceras (BOM, espacios)
    df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]

    # Verificar que las columnas necesarias existen
    missing = [c for c in CSV_COLS.keys() if c not in df.columns]
    if missing:
        for m in missing:
            found = [c for c in df.columns if m.lower() in c.lower()]
            if found:
                print(f"   [Fallback] '{m}' no encontrada, usando '{found[0]}'")
                df = df.rename(columns={found[0]: m})
            else:
                raise ValueError(f"Columna requerida no encontrada: '{m}'. Columnas disponibles: {list(df.columns)}")

    # Renombrar columnas
    df_clean = df.rename(columns=CSV_COLS)

    # Seleccionar solo las columnas que necesitamos
    df_clean = df_clean[SUPABASE_COLS].copy()

    # ── Limpieza de datos ──

    # Números: formato europeo + NaN/Inf
    df_clean['num_facturas'] = df_clean['num_facturas'].apply(convert_european_number).astype(int)
    df_clean['gasto_total'] = df_clean['gasto_total'].apply(convert_european_number)

    # Fechas: convertir a YYYY-MM-DD
    df_clean['fecha_corte'] = (
        pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )
    df_clean['fecha_ultima_compra'] = (
        pd.to_datetime(df_clean['fecha_ultima_compra'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )

    # Texto: limpiar etiquetas y segmentos
    df_clean['segmento_rfm'] = df_clean['segmento_rfm'].fillna('Sin Clasificar').str.strip()
    df_clean['seg_recencia'] = df_clean['seg_recencia'].fillna('INACTIVO').str.strip()
    df_clean['seg_frecuencia'] = df_clean['seg_frecuencia'].fillna('1 COMPRA').str.strip()
    df_clean['seg_monetario'] = df_clean['seg_monetario'].fillna('BRONCE 3').str.strip()

    # Limpieza final JSON (NaN → None)
    df_clean = df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0})

    # Deduplicar por cliente + fecha
    df_clean = df_clean.drop_duplicates(subset=['cliente_id', 'fecha_corte'])

    print(f"   Registros procesados: {len(df_clean):,}")
    print(f"   Clientes únicos: {df_clean['cliente_id'].nunique():,}")
    print(f"   Fechas de corte: {df_clean['fecha_corte'].nunique()}")
    print(f"   Segmentos encontrados: {df_clean['segmento_rfm'].unique().tolist()}")

    return df_clean


def load(df: pd.DataFrame, batch_size: int = 500):
    """Carga a Supabase con upsert por lotes."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan credenciales de Supabase en .env")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    records = df.to_dict('records')
    total = len(records)

    print(f"\n[Load] Subiendo {total:,} registros a Supabase...")

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
            print(f"   [Error] Lote {i // batch_size + 1}: {str(e)[:100]}")

    if errores:
        print(f"\n   ⚠️  {errores} lotes con error")
    else:
        print(f"\n   ✅ Carga completada sin errores")


def main():
    INPUT_FILE = "Segmento_RFM_raw.csv"
    PATH = INPUT_FILE if os.path.exists(INPUT_FILE) else os.path.join("ETL-Segmentador-Petramora", INPUT_FILE)

    print(f"\n{'=' * 60}")
    print(f"ETL PETRAMORA v3.1 — DAX Direct (UTF-8)")
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