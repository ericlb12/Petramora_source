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
COLUMN_MAPPING = {
    'ClienteRelacionado': 'cliente_id',
    'FinDeMes': 'fecha_corte',
    'UltimaFactura': 'fecha_ultima_compra',
    'RecenciaDias': 'dias_recencia',
    'Facturas_Acumuladas_Anual': 'num_facturas',
    'VentasTotales_Acumuladas_Anual': 'gasto_total',
    'Grupo R (recencia)': 'seg_recencia',
    'Grupo F (frecuencia)': 'seg_frecuencia',
    'Grupo M (Monetario)': 'seg_monetario',
    'RFM': 'score_rfm',
    'Segmento_RFM': 'segmento_rfm',
    'Grupo segemento RFM': 'grupo_segmento'
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

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma y filtra las columnas necesarias"""
    print("\nTransformando datos...")
    
    # 1. Seleccionar solo las columnas que necesitamos
    columns_to_keep = list(COLUMN_MAPPING.keys())
    df_filtered = df[columns_to_keep].copy()
    print(f"   Columnas filtradas: {len(columns_to_keep)} de {len(df.columns)}")
    
    # 2. Renombrar columnas segun el mapeo
    df_filtered = df_filtered.rename(columns=COLUMN_MAPPING)
    print(f"   Columnas renombradas: {list(df_filtered.columns)}")
    
    # 3. Convertir fechas
    df_filtered['fecha_corte'] = pd.to_datetime(df_filtered['fecha_corte'], dayfirst=True).dt.strftime('%Y-%m-%d')
    df_filtered['fecha_ultima_compra'] = pd.to_datetime(df_filtered['fecha_ultima_compra'], dayfirst=True).dt.strftime('%Y-%m-%d')
    print("   Fechas convertidas a formato ISO")
    
    # 4. Limpiar valores nulos y convertir numeros (formato europeo)
    df_filtered['num_facturas'] = df_filtered['num_facturas'].apply(convert_european_number).astype(int)
    df_filtered['gasto_total'] = df_filtered['gasto_total'].apply(convert_european_number)
    df_filtered['dias_recencia'] = df_filtered['dias_recencia'].fillna(0).astype(int)
    df_filtered['score_rfm'] = df_filtered['score_rfm'].fillna(0).astype(int)
    print("   Valores nulos limpiados y numeros convertidos")
    
    # 5. Reemplazar inf y nan
    df_filtered = df_filtered.replace([np.inf, -np.inf], 0)
    df_filtered = df_filtered.fillna(0)
    print("   Valores infinitos reemplazados")
    
    # 6. Eliminar duplicados (mismo cliente + misma fecha_corte)
    antes = len(df_filtered)
    df_filtered = df_filtered.drop_duplicates(subset=['cliente_id', 'fecha_corte'])
    despues = len(df_filtered)
    print(f"   Duplicados eliminados: {antes - despues:,}")
    
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