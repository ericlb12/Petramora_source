"""
ETL Segmentador Petramora (D.A.X. Sync Version 2.1)
Transforma datos de segmentación RFM usando los scores numéricos 'orden' de Power BI
y los carga a Supabase manejando limpieza de JSON (NaN/Inf).
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

# Mapeo de columnas: Power BI Export -> Supabase
CSV_COLS = {
    'ClienteRelacionado': 'cliente_id',
    'Fecha_Fin_Mes': 'fecha_corte',
    'UltimaFactura': 'fecha_ultima_compra',
    'RecenciaDias': 'dias_recencia',
    'Facturas': 'num_facturas',
    'VentasTotales': 'gasto_total',
    'Recencia seleccionada orden': 'score_r',
    'Frecuencia seleccionada orden': 'score_f',
    'Monetario seleccionada orden': 'score_m',
    'Recencia Seleccionada': 'label_r',
    'Frecuencia Seleccionada': 'label_f',
    'Monetario Seleccionada': 'label_m'
}

def convert_european_number(value):
    """Convierte numeros con formato europeo (coma decimal) a float limpio"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if not (math.isinf(value) or math.isnan(value)) else 0.0
    try:
        val_str = str(value).replace(',', '.')
        result = float(val_str)
        return result if not (math.isinf(result) or math.isnan(result)) else 0.0
    except:
        return 0.0

def calculate_segments(row):
    """Aplica la lógica de segmentación oficial de Petramora (Sincronizada con DAX)"""
    sr = int(row['score_r'])
    sf = int(row['score_f'])
    sm = int(row['score_m'])
    
    r_code = f"{sr}{sf}{sm}"
    score_rfm = int(r_code)
    
    # 1) Champion
    if r_code in ["444","445","454","455","544","545","554","555"]:
        segmento, grupo = "Champion", "1. Champions"
    # 2) Champions casi recurrente
    elif r_code in ["424","425","434","435","441","442","443","451","452","453",
                  "524","525","534","535","541","542","543","551","552","553"]:
        segmento, grupo = "Champions casi recurrente", "1. Champions"
    # 3) Champions dormido
    elif r_code in ["234","235","244","245","254","255","334","335","344","345","354","355"]:
        segmento, grupo = "Champions dormido", "1. Champions"
    # 4) Activo Básico
    elif r_code in ["421","422","423","431","432","433","521","522","523","531","532","533"]:
        segmento, grupo = "Activo Básico", "3. Oportunistas"
    # 5) Rico potencial
    elif r_code in ["314","315","414","415","514","515"]:
        segmento, grupo = "Rico potencial", "2. Ricos"
    # 6) Oportunista nuevo
    elif r_code in ["311","312","313","411","412","413","511","512","513"]:
        segmento, grupo = "Oportunista nuevo", "3. Oportunistas"
    # 7) Oportunista con potencial
    elif r_code in ["321","322","323","324","325","331","332","333","341","342","343","351","352","353"]:
        segmento, grupo = "Oportunista con potencial", "3. Oportunistas"
    # 8) Rico perdido
    elif r_code in ["114","115","124","125","134","135","144","145","154","155","214","215","224","225"]:
        segmento, grupo = "Rico perdido", "2. Ricos"
    else:
        segmento, grupo = "Oportunista perdido", "3. Oportunistas"
        
    return pd.Series([score_rfm, segmento, grupo])

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma los datos y limpia para JSON compliance"""
    print("\n[Transform] Limpiando datos y aplicando DAX...")
    df.columns = [c.lstrip('\ufeff').strip().replace('??', 'u') for c in df.columns]
    df_renamed = df.rename(columns=CSV_COLS)
    
    # Fallback para columnas faltantes
    for m in [k for k in CSV_COLS.keys() if k not in df.columns]:
        found = [c for c in df.columns if m in c]
        if found: df_renamed = df_renamed.rename(columns={found[0]: CSV_COLS[m]})

    # Seleccion y limpieza de NaNs/Infs
    df_clean = df_renamed[['cliente_id', 'fecha_corte', 'fecha_ultima_compra', 'dias_recencia', 'num_facturas', 'gasto_total']].copy()
    df_clean['num_facturas'] = df_clean['num_facturas'].apply(convert_european_number).astype(int)
    df_clean['gasto_total'] = df_clean['gasto_total'].apply(convert_european_number)
    df_clean['dias_recencia'] = df_clean['dias_recencia'].fillna(0).astype(int)
    
    # Etiquetas y scores
    df_clean['seg_recencia'] = df_renamed['label_r'].fillna('INACTIVO')
    df_clean['seg_frecuencia'] = df_renamed['label_f'].fillna('1 COMPRA')
    df_clean['seg_monetario'] = df_renamed['label_m'].fillna('BRONCE 3')
    
    temp_scores = df_renamed[['score_r', 'score_f', 'score_m']].apply(pd.to_numeric, errors='coerce').fillna(1).astype(int)
    df_clean[['score_rfm', 'segmento_rfm', 'grupo_segmento']] = temp_scores.apply(calculate_segments, axis=1)
    
    # Formateo fechas
    df_clean['fecha_corte'] = pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    df_clean['fecha_ultima_compra'] = pd.to_datetime(df_clean['fecha_ultima_compra'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Limpieza final para JSON (reemplazar NaNs por None/0)
    return df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0}).drop_duplicates(subset=['cliente_id', 'fecha_corte'])

def load(df: pd.DataFrame, batch_size: int = 500):
    """Carga a Supabase con upsert"""
    if not SUPABASE_URL or not SUPABASE_KEY: raise ValueError("Faltan credenciales")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    records = df.to_dict('records')
    total = len(records)
    print(f"\n[Load] Subiendo {total:,} registros...")
    for i in range(0, total, batch_size):
        batch = records[i:i+batch_size]
        try:
            supabase.table('segmentacion_clientes_raw').upsert(batch, on_conflict='cliente_id,fecha_corte').execute()
            if (i+batch_size) % 5000 == 0 or (i+batch_size) >= total:
                print(f"   - Progreso: {min(i+batch_size, total):,}/{total:,}")
        except Exception as e:
            print(f"   [Error] Lote {i//batch_size + 1}: {str(e)[:100]}")

def main():
    INPUT_FILE = "Segmento_RFM_raw.csv"
    PATH = INPUT_FILE if os.path.exists(INPUT_FILE) else os.path.join("ETL-Segmentador-Petramora", INPUT_FILE)
    print(f"\n{'='*60}\nETL PETRAMORA: SYNC DAX 2.1 (JSON Clean)\n{'='*60}")
    try:
        df = pd.read_csv(PATH, sep=';', encoding='latin-1', low_memory=False)
        load(transform(df))
    except Exception as e: print(f"\n[CRITICAL ERROR] {e}")

if __name__ == "__main__": main()