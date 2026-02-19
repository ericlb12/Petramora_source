"""
ETL Segmentador Petramora
Transforma datos de segmentacion RFM y los carga a Supabase
"""

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client
import os
from datetime import datetime
import math

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Mapeo de columnas: Excel -> Supabase
# Se usan las columnas estrictamente mensuales del CSV (Facturas, VentasTotales)
COLUMN_MAPPING = {
    'ClienteRelacionado': 'cliente_id',
    'FinDeMes': 'fecha_corte',
    'UltimaFactura': 'fecha_ultima_compra',
    'RecenciaDias': 'dias_recencia',
    'Facturas': 'num_facturas',
    'VentasTotales': 'gasto_total'
}

def extract(file_path: str) -> pd.DataFrame:
    """Lee el CSV de origen"""
    print(f"Leyendo archivo: {file_path}")
    df = pd.read_csv(file_path, encoding='utf-8-sig', sep=';', low_memory=False)
    print(f"   Filas leidas: {len(df):,}")
    print(f"   Columnas: {len(df.columns)}")
    return df

def convert_european_number(value):
    """Convierte numeros con formato europeo (coma decimal) a float"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        if math.isinf(value) or math.isnan(value):
            return 0.0
        return float(value)
    try:
        result = float(str(value).replace(',', '.'))
        if math.isinf(result) or math.isnan(result):
            return 0.0
        return result
    except:
        return 0.0

def clean_record(record):
    """Limpia un registro para asegurar que sea JSON-compatible"""
    cleaned = {}
    for key, value in record.items():
        if value is None:
            cleaned[key] = None
        elif isinstance(value, float):
            if math.isinf(value) or math.isnan(value):
                cleaned[key] = 0.0
            else:
                cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned

def calculate_segments(row):
    """Aplica la lógica de segmentación oficial de Petramora"""
    r = row['dias_recencia']
    f = row['num_facturas']
    m = row['gasto_total']
    
    # 1. Segmento Recencia
    if r < 30: seg_r = "RECURRENTE"
    elif r < 90: seg_r = "ACTIVOS"
    elif r < 180: seg_r = "REGULARES"
    elif r < 365: seg_r = "DORMIDOS"
    else: seg_r = "INACTIVOS"
    
    # 2. Segmento Frecuencia
    if f >= 20: seg_f = "SUPERLEALES"
    elif f >= 10: seg_f = "LEALES"
    elif f >= 4: seg_f = "BUENOS"
    elif f >= 2: seg_f = "REGULARES"
    else: seg_f = "1 COMPRA"
    
    # 3. Segmento Monetario
    if m > 277: seg_m = "ORO"
    elif m >= 138: seg_m = "PLATA"
    elif m >= 68: seg_m = "BRONCE 1"
    elif m >= 41: seg_m = "BRONCE 2"
    else: seg_m = "BRONCE 3"
    
    # 4. Segmento RFM y Grupo (Lógica simplificada para el Agente)
    # Se puede expandir según necesitemos mapear nombres exactos de Champion, etc.
    # Por ahora mantenemos los segmentos base para coherencia.
    segmento = f"{seg_r} {seg_f} {seg_m}"
    
    # Mapeo a grupos generales
    if seg_m == "ORO" or (seg_f in ["SUPERLEALES", "LEALES"] and seg_r == "RECURRENTE"):
        grupo = "1. Champions"
    elif seg_m == "PLATA":
        grupo = "2. Ricos"
    else:
        grupo = "3. Oportunistas"
        
    return pd.Series([seg_r, seg_f, seg_m, segmento, grupo])

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma y filtra las columnas necesarias"""
    print("\nTransformando datos...")
    
    # 1. Seleccionar solo las columnas que necesitamos
    columns_to_keep = list(COLUMN_MAPPING.keys())
    df_filtered = df[columns_to_keep].copy()
    
    # Validad que las columnas existen
    missing = [c for c in columns_to_keep if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el CSV: {missing}")
        
    print(f"   Columnas filtradas: {len(columns_to_keep)} de {len(df.columns)}")
    
    # 2. Renombrar columnas segun el mapeo
    df_filtered = df_filtered.rename(columns=COLUMN_MAPPING)
    
    # 3. Convertir fechas
    df_filtered['fecha_corte'] = pd.to_datetime(df_filtered['fecha_corte'], dayfirst=True).dt.strftime('%Y-%m-%d')
    df_filtered['fecha_ultima_compra'] = pd.to_datetime(df_filtered['fecha_ultima_compra'], dayfirst=True).dt.strftime('%Y-%m-%d')
    
    # 4. Limpiar valores y convertir numeros
    df_filtered['num_facturas'] = df_filtered['num_facturas'].apply(convert_european_number).astype(int)
    df_filtered['gasto_total'] = df_filtered['gasto_total'].apply(convert_european_number)
    df_filtered['dias_recencia'] = df_filtered['dias_recencia'].fillna(0).astype(int)
    
    # 5. Calcular Segmentos RFM en Python
    print("   Calculando nuevas reglas de segmentación...")
    df_filtered[['seg_recencia', 'seg_frecuencia', 'seg_monetario', 'segmento_rfm', 'grupo_segmento']] = \
        df_filtered.apply(calculate_segments, axis=1)
    
    # 6. Score RFM (opcional, como string)
    df_filtered['score_rfm'] = 0 # Opcional: implementar score 111-555 si se requiere
    
    # 7. Eliminar duplicados
    df_filtered = df_filtered.drop_duplicates(subset=['cliente_id', 'fecha_corte'])
    
    print(f"\nRegistros listos para cargar: {len(df_filtered):,}")
    return df_filtered

def load(df: pd.DataFrame, batch_size: int = 1000):
    """Carga los datos a Supabase en batches"""
    print(f"\nConectando a Supabase...")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan credenciales. Revisa el archivo .env")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("   Conexion establecida")
    
    # Convertir DataFrame a lista de diccionarios y limpiar cada registro
    records = [clean_record(r) for r in df.to_dict('records')]
    total = len(records)
    
    print(f"\nCargando {total:,} registros en batches de {batch_size}...")
    
    loaded = 0
    errors = 0
    
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        try:
            response = supabase.table('segmentacion_clientes_raw').upsert(
                batch,
                on_conflict='cliente_id,fecha_corte'
            ).execute()
            loaded += len(batch)
            print(f"   Progreso: {loaded:,}/{total:,} ({100*loaded/total:.1f}%)")
        except Exception as e:
            errors += len(batch)
            print(f"   Error en batch {i//batch_size + 1}: {str(e)[:100]}")
    
    print(f"\n{'='*50}")
    print(f"Carga completada")
    print(f"   Registros cargados: {loaded:,}")
    print(f"   Errores: {errors:,}")
    print(f"{'='*50}")

def main():
    """Ejecuta el ETL completo"""
    print("="*50)
    print("ETL SEGMENTADOR PETRAMORA")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # Configuracion
    INPUT_FILE = "segmentacion_clientes_raw.csv"
    
    # ETL
    df_raw = extract(INPUT_FILE)
    df_transformed = transform(df_raw)
    load(df_transformed, batch_size=500)
    
    print(f"\nFin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()