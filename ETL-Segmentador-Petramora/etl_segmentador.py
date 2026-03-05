"""
ETL Segmentador Petramora (v6.0 — Productos + Catálogo)
3 procesos independientes en un solo archivo:
  1. Segmentación RFM (v5.1 — ya existente)
  2. Líneas cliente-producto (NUEVO)
  3. Catálogo de productos (NUEVO)

Uso:
  python etl_segmentador.py                    # Ejecuta los 3 procesos
  python etl_segmentador.py --segmentacion     # Solo RFM
  python etl_segmentador.py --lineas           # Solo líneas cliente-producto
  python etl_segmentador.py --catalogo         # Solo catálogo
  python etl_segmentador.py --lineas --catalogo  # Combinaciones

Fuente de verdad: Power BI / DAX → CSVs exportados
"""

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client
import os
import sys
import math
import argparse

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ═════════════════════════════════════════════════════════════
# NORMALIZACIÓN DE FAMILIAS
# Unifica nombres duplicados o inconsistentes entre tablas.
# Clave = nombre en CSV, Valor = nombre normalizado en Supabase.
# Añadir aquí cualquier duplicidad futura.
# ═════════════════════════════════════════════════════════════

NORMALIZACION_FAMILIAS = {
    'Carnes': 'CARNE',
    # Añadir más si se detectan, por ejemplo:
    # 'Queso': 'QUESOS',
    # 'Bebida': 'BEBIDAS',
}

# ═════════════════════════════════════════════════════════════
# CLASIFICACIÓN MANUAL DE PRODUCTOS SIN CATEGORÍA
# Productos cuyo itemCategoryId está vacío en el ERP.
# Se aplica después de la transformación, solo a los "Sin Clasificar".
# Clave = codigo_producto, Valor = familia correcta.
# ═════════════════════════════════════════════════════════════

CLASIFICACION_MANUAL = {
    # PLATOS PREPARADOS
    '50105': 'PLATOS PREPARADOS',
    '50048': 'PLATOS PREPARADOS',
    '50019': 'PLATOS PREPARADOS',
    '50046': 'PLATOS PREPARADOS',
    '50116': 'PLATOS PREPARADOS',
    '50053': 'PLATOS PREPARADOS',
    '50115': 'PLATOS PREPARADOS',
    '50121': 'PLATOS PREPARADOS',
    '50124': 'PLATOS PREPARADOS',
    '50100': 'PLATOS PREPARADOS',
    '50131': 'PLATOS PREPARADOS',
    '50111': 'PLATOS PREPARADOS',
    '50050': 'PLATOS PREPARADOS',
    '50051': 'PLATOS PREPARADOS',
    '50060': 'PLATOS PREPARADOS',
    '50038': 'PLATOS PREPARADOS',
    # CARNE
    '10000281': 'CARNE',
    '10000282': 'CARNE',
    '10000278': 'CARNE',
    '10000279': 'CARNE',
    '10000219': 'CARNE',
    '50123': 'CARNE',
    '50128': 'CARNE',
    '50132': 'CARNE',
    # Ensaladas y verduras
    '50056': 'Ensaladas y verduras',
    '50110': 'Ensaladas y verduras',
    '50020': 'Ensaladas y verduras',
    '50022': 'Ensaladas y verduras',
    '50024': 'Ensaladas y verduras',
    '50045': 'Ensaladas y verduras',
    '50021': 'Ensaladas y verduras',
    '50055': 'Ensaladas y verduras',
    # Pastas, arroces y masas
    '50108': 'Pastas, arroces y masas',
    '50118': 'Pastas, arroces y masas',
    '50058': 'Pastas, arroces y masas',
    '50122': 'Pastas, arroces y masas',
    '50027': 'Pastas, arroces y masas',
    '50104': 'Pastas, arroces y masas',
    '50077': 'Pastas, arroces y masas',
    '50126': 'Pastas, arroces y masas',
    '50117': 'Pastas, arroces y masas',
    '50000706': 'Pastas, arroces y masas',
    '50125': 'Pastas, arroces y masas',
    '50000700': 'Pastas, arroces y masas',
    '50000699': 'Pastas, arroces y masas',
    '50000390': 'Pastas, arroces y masas',
    # Caldos, cremas y legumbres
    '50127': 'Caldos, cremas y legumbres',
    '50043': 'Caldos, cremas y legumbres',
    '50037': 'Caldos, cremas y legumbres',
    '50109': 'Caldos, cremas y legumbres',
    '50029': 'Caldos, cremas y legumbres',
    '50032': 'Caldos, cremas y legumbres',
    '50130': 'Caldos, cremas y legumbres',
    '50107': 'Caldos, cremas y legumbres',
    '50036': 'Caldos, cremas y legumbres',
    '50042': 'Caldos, cremas y legumbres',
    '50149': 'Caldos, cremas y legumbres',
    '50052': 'Caldos, cremas y legumbres',
    '50035': 'Caldos, cremas y legumbres',
    '50119': 'Caldos, cremas y legumbres',
    # PESCADOS Y MARISCOS
    '50039': 'PESCADOS Y MARISCOS',
    # DESPENSA
    '50098': 'DESPENSA',
    '45000453': 'DESPENSA',
    '45000452': 'DESPENSA',
    '50000759': 'DESPENSA',
    '50170': 'DESPENSA',
    # EMBUTIDOS
    '15000234': 'EMBUTIDOS',
    # QUESOS
    '20007': 'QUESOS',
    # BEBIDAS
    '60001393': 'BEBIDAS',
    # Menaje
    '60001392': 'Menaje',
    '65001404': 'Menaje',
    '65001977': 'Menaje',
    '65002044': 'Menaje',
    '65002054': 'Menaje',
    '65002043': 'Menaje',
    '65002184': 'Menaje',
    '65002185': 'Menaje',
}


# ═════════════════════════════════════════════════════════════
# UTILIDADES COMUNES
# ═════════════════════════════════════════════════════════════

def get_supabase():
    """Crea y retorna el cliente de Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan credenciales de Supabase en .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


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


def aplicar_clasificacion_manual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica CLASIFICACION_MANUAL a productos que quedaron 'Sin Clasificar'.
    Solo modifica filas donde familia == 'Sin Clasificar' y el código está en el diccionario.
    """
    mask = df['familia'] == 'Sin Clasificar'
    corregidos = 0
    for idx in df[mask].index:
        codigo = str(df.at[idx, 'codigo_producto']).strip()
        if codigo in CLASIFICACION_MANUAL:
            df.at[idx, 'familia'] = CLASIFICACION_MANUAL[codigo]
            corregidos += 1
    if corregidos > 0:
        print(f"   [Clasificación manual] {corregidos} productos reclasificados")
    return df


def load_to_supabase(df, table_name, conflict_cols, batch_size=500, delete_first=False):
    """
    Carga un DataFrame a Supabase.
    - delete_first=True: borra todos los registros antes de insertar (para catálogo)
    - delete_first=False: hace upsert (para líneas e histórico)
    """
    supabase = get_supabase()
    records = df.to_dict('records')
    total = len(records)

    if delete_first:
        print(f"\n[Load] Borrando datos existentes de '{table_name}'...")
        first_col = list(df.columns)[0]
        try:
            # Intento rápido: borrar todo de una vez
            supabase.table(table_name).delete().neq(first_col, '').execute()
            print(f"   ✅ Tabla limpiada")
        except Exception:
            # Fallback: TRUNCATE via RPC (tablas grandes que dan timeout en DELETE)
            print(f"   ⏳ Tabla grande, usando TRUNCATE via RPC...")
            try:
                supabase.rpc('truncate_lineas').execute()
                print(f"   ✅ Tabla limpiada (TRUNCATE)")
            except Exception as e2:
                print(f"   ⚠️  Error en TRUNCATE RPC: {str(e2)[:100]}")

    print(f"[Load] Subiendo {total:,} registros a '{table_name}'...")

    errores = 0
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        try:
            supabase.table(table_name).upsert(
                batch, on_conflict=conflict_cols
            ).execute()
            progreso = min(i + batch_size, total)
            if progreso % 50000 == 0 or progreso >= total:
                print(f"   Progreso: {progreso:,}/{total:,}", flush=True)
        except Exception as e:
            errores += 1
            if errores <= 5:  # Solo imprimir los primeros 5 errores
                print(f"   [Error] Lote {i // batch_size + 1}: {str(e)[:100]}", flush=True)

    if errores:
        print(f"\n   ⚠️  {errores} lotes con error", flush=True)
    else:
        print(f"\n   ✅ Carga completada sin errores", flush=True)


def find_file(filename, fallback_dirs=None):
    """Busca un archivo en el directorio actual y en directorios alternativos."""
    if os.path.exists(filename):
        return filename
    fallback_dirs = fallback_dirs or ['ETL-Segmentador-Petramora', 'data', '.']
    for d in fallback_dirs:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    return None


# ═════════════════════════════════════════════════════════════
# PROCESO 1: SEGMENTACIÓN RFM (v5.1 — sin cambios)
# ═════════════════════════════════════════════════════════════

# Mapeo de columnas: Power BI CSV → Supabase
CSV_COLS_SEGMENTACION = {
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

SEGMENTO_COL_PATTERN = 'ltimo global'

SUPABASE_COLS_SEGMENTACION = [
    'cliente_id', 'fecha_corte', 'fecha_ultima_compra', 'segmento_rfm',
    'ventas_2024', 'ventas_2025', 'ventas_2026',
    'facturas_2024', 'facturas_2025', 'facturas_2026',
    'gasto_total',
]


def transform_segmentacion(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma el CSV de segmentación RFM. Solo último mes."""
    print("\n[Segmentación] Transformando...")

    df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]

    # Buscar columna de segmento dinámicamente
    seg_col = None
    for c in df.columns:
        if SEGMENTO_COL_PATTERN in c and 'Segmento' in c:
            seg_col = c
            break
    if not seg_col:
        raise ValueError(f"No se encontró columna de segmento con patrón '{SEGMENTO_COL_PATTERN}'. "
                         f"Columnas: {list(df.columns)}")
    print(f"   Columna de segmento: '{seg_col}'")

    # Verificar columnas del mapeo
    missing = [c for c in CSV_COLS_SEGMENTACION.keys() if c not in df.columns]
    if missing:
        for m in missing:
            found = [c for c in df.columns if m.lower() in c.lower()]
            if found:
                print(f"   [Fallback] '{m}' → '{found[0]}'")
                df = df.rename(columns={found[0]: m})
            else:
                raise ValueError(f"Columna requerida no encontrada: '{m}'")

    df_clean = df.rename(columns=CSV_COLS_SEGMENTACION)
    df_clean = df_clean.rename(columns={seg_col: 'segmento_rfm'})
    df_clean = df_clean[SUPABASE_COLS_SEGMENTACION].copy()

    # Filtrar solo último mes
    df_clean['fecha_corte_dt'] = pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce')
    ultimo_mes = df_clean['fecha_corte_dt'].max()
    print(f"   Último mes: {ultimo_mes.strftime('%Y-%m-%d')}")
    df_clean = df_clean[df_clean['fecha_corte_dt'] == ultimo_mes].copy()
    df_clean = df_clean.drop(columns=['fecha_corte_dt'])

    # Limpieza numérica
    for col in ['ventas_2024', 'ventas_2025', 'ventas_2026', 'gasto_total']:
        df_clean[col] = df_clean[col].apply(convert_european_number)
    for col in ['facturas_2024', 'facturas_2025', 'facturas_2026']:
        df_clean[col] = df_clean[col].apply(convert_european_number).astype(int)

    # Limpieza de fechas
    df_clean['fecha_corte'] = (
        pd.to_datetime(df_clean['fecha_corte'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )
    df_clean['fecha_ultima_compra'] = (
        pd.to_datetime(df_clean['fecha_ultima_compra'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )

    df_clean['segmento_rfm'] = df_clean['segmento_rfm'].fillna('Sin Clasificar').str.strip()
    df_clean = df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0})
    df_clean = df_clean.drop_duplicates(subset=['cliente_id'])

    print(f"   Registros finales: {len(df_clean):,}")
    return df_clean


def proceso_segmentacion(filename="Segmento_RFM_raw.csv"):
    """Ejecuta el proceso completo de segmentación RFM."""
    print(f"\n{'─' * 60}")
    print(f"  PROCESO 1: SEGMENTACIÓN RFM")
    print(f"{'─' * 60}")

    path = find_file(filename)
    if not path:
        print(f"   [ERROR] Archivo no encontrado: {filename}")
        return False

    try:
        df = pd.read_csv(path, sep=';', encoding='utf-8-sig', low_memory=False)
        print(f"   [Extract] {len(df):,} filas, {len(df.columns)} columnas")
        df_clean = transform_segmentacion(df)
        load_to_supabase(
            df_clean,
            table_name='segmentacion_clientes_raw',
            conflict_cols='cliente_id,fecha_corte',
            delete_first=True
        )
        return True
    except Exception as e:
        print(f"   [CRITICAL ERROR] {e}")
        return False


# ═════════════════════════════════════════════════════════════
# PROCESO 2: LÍNEAS CLIENTE-PRODUCTO (NUEVO v6.0)
# ═════════════════════════════════════════════════════════════

CSV_COLS_LINEAS = {
    'ClienteRelacionado': 'cliente_id',
    'CodigoProducto': 'codigo_producto',
    'Descripcion': 'descripcion',
    'DocumentNo': 'document_no',
    'FechaCompra': 'fecha_compra',
    'Familia': 'familia',
    'Subfamilia': 'subfamilia',
    'VentasNetas': 'ventas_netas',
    'Cantidad': 'cantidad',
    'MargenProm': 'margen_prom',
    'DescuentoProm': 'descuento_prom',
}

SUPABASE_COLS_LINEAS = [
    'cliente_id', 'codigo_producto', 'descripcion', 'document_no',
    'fecha_compra', 'familia', 'subfamilia',
    'ventas_netas', 'cantidad', 'margen_prom', 'descuento_prom',
]


def transform_lineas(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma el CSV de líneas cliente-producto."""
    print("\n[Líneas] Transformando...")

    df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]

    # Verificar columnas y aplicar fallback si los nombres no coinciden exactamente
    for csv_col, supa_col in CSV_COLS_LINEAS.items():
        if csv_col not in df.columns:
            # Buscar coincidencia parcial (case-insensitive)
            found = [c for c in df.columns if csv_col.lower() in c.lower()]
            if found:
                print(f"   [Fallback] '{csv_col}' → '{found[0]}'")
                df = df.rename(columns={found[0]: csv_col})
            else:
                print(f"   [WARN] Columna '{csv_col}' no encontrada, se rellenará con NULL")
                df[csv_col] = None

    df_clean = df.rename(columns=CSV_COLS_LINEAS)

    # Seleccionar solo columnas necesarias
    for col in SUPABASE_COLS_LINEAS:
        if col not in df_clean.columns:
            df_clean[col] = None
    df_clean = df_clean[SUPABASE_COLS_LINEAS].copy()

    # ── Limpieza numérica (formato europeo) ──
    for col in ['ventas_netas', 'cantidad', 'margen_prom', 'descuento_prom']:
        df_clean[col] = df_clean[col].apply(convert_european_number)

    # ── Limpieza de fechas ──
    df_clean['fecha_compra'] = (
        pd.to_datetime(df_clean['fecha_compra'], dayfirst=True, errors='coerce')
        .dt.strftime('%Y-%m-%d')
    )

    # ── Limpieza de texto ──
    df_clean['familia'] = df_clean['familia'].fillna('Sin Clasificar').str.strip()
    df_clean['subfamilia'] = df_clean['subfamilia'].fillna('Sin Clasificar').str.strip()

    # ── Normalización de familias ──
    df_clean['familia'] = df_clean['familia'].replace(NORMALIZACION_FAMILIAS)

    # ── Clasificación manual de productos sin categoría ──
    df_clean = aplicar_clasificacion_manual(df_clean)

    df_clean['descripcion'] = df_clean['descripcion'].fillna('').str.strip()
    df_clean['codigo_producto'] = df_clean['codigo_producto'].astype(str).str.strip()
    df_clean['document_no'] = df_clean['document_no'].astype(str).str.strip()

    # ── Eliminar filas sin datos clave ──
    antes = len(df_clean)
    df_clean = df_clean.dropna(subset=['cliente_id', 'codigo_producto', 'document_no'])
    df_clean = df_clean[df_clean['cliente_id'].str.strip() != '']
    df_clean = df_clean[df_clean['codigo_producto'].str.strip() != '']
    despues = len(df_clean)
    if antes != despues:
        print(f"   Eliminadas {antes - despues:,} filas sin cliente/producto/factura")

    # ── Deduplicar por PK ──
    df_clean = df_clean.drop_duplicates(subset=['cliente_id', 'codigo_producto', 'document_no'])

    # ── Limpieza final ──
    df_clean = df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0})

    print(f"   Registros finales: {len(df_clean):,}")
    print(f"   Clientes únicos: {df_clean['cliente_id'].nunique():,}")
    print(f"   Productos únicos: {df_clean['codigo_producto'].nunique():,}")
    print(f"   Familias encontradas: {df_clean['familia'].nunique()} → {df_clean['familia'].unique().tolist()[:15]}")

    return df_clean


def proceso_lineas(filename="lineas_cliente_producto.csv"):
    """Ejecuta el proceso de carga de líneas cliente-producto."""
    print(f"\n{'─' * 60}")
    print(f"  PROCESO 2: LÍNEAS CLIENTE-PRODUCTO")
    print(f"{'─' * 60}")

    path = find_file(filename)
    if not path:
        print(f"   [ERROR] Archivo no encontrado: {filename}")
        return False

    try:
        df = pd.read_csv(path, sep=';', encoding='utf-8-sig', low_memory=False)
        print(f"   [Extract] {len(df):,} filas, {len(df.columns)} columnas")
        print(f"   Columnas detectadas: {list(df.columns)}")
        df_clean = transform_lineas(df)
        load_to_supabase(
            df_clean,
            table_name='lineas_cliente_producto',
            conflict_cols='cliente_id,codigo_producto,document_no',
            delete_first=True
        )
        return True
    except Exception as e:
        print(f"   [CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


# ═════════════════════════════════════════════════════════════
# PROCESO 3: CATÁLOGO DE PRODUCTOS (NUEVO v6.0)
# ═════════════════════════════════════════════════════════════

CSV_COLS_CATALOGO = {
    # Nombres del DAX Catalogo_Productos_Export
    'CodigoProducto': 'codigo_producto',
    'Descripcion': 'descripcion',
    'Familia': 'familia',
    'Subfamilia': 'subfamilia',
    'PrecioConIVA': 'precio_con_iva',
    'CosteUnitario': 'coste_unitario',
    'UnidadMedida': 'unidad_medida',
    'Stock': 'stock',
    'Bloqueado': 'bloqueado',
    'MargenTeoricoPct': 'margen_teorico_pct',
}

# Fallbacks: nombres originales de la tabla Productos (por si se exporta directo)
CSV_COLS_CATALOGO_FALLBACK = {
    'CODIGO_PRODUCTO': 'CodigoProducto',
    'DESCRIPCION_PRODUCTO': 'Descripcion',
    'GRUPO_PRODUCTO': 'Familia',
    'CATEGORIA_PRODUCTO': 'Subfamilia',
    'PRECIO UNITARIO CON IVA': 'PrecioConIVA',
    'COSTE UNITARIO': 'CosteUnitario',
    'UNIDAD_MEDIDA': 'UnidadMedida',
    'inventory': 'Stock',
    'blocked': 'Bloqueado',
}

SUPABASE_COLS_CATALOGO = [
    'codigo_producto', 'descripcion', 'familia', 'subfamilia',
    'precio_con_iva', 'coste_unitario', 'unidad_medida',
    'stock', 'bloqueado', 'margen_teorico_pct',
]


def transform_catalogo(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma el CSV de productos para el catálogo."""
    print("\n[Catálogo] Transformando...")

    df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]

    # Solo productos de inventario (excluir servicios) — aplica si viene de tabla Productos directa
    if 'type' in df.columns:
        antes = len(df)
        df = df[df['type'] == 'Inventory'].copy()
        print(f"   Filtro type=Inventory: {antes:,} → {len(df):,}")

    # ── Aplicar fallbacks: si tiene nombres originales de Productos, renombrar a nombres del DAX ──
    for old_name, new_name in CSV_COLS_CATALOGO_FALLBACK.items():
        if old_name in df.columns and new_name not in df.columns:
            print(f"   [Fallback] '{old_name}' → '{new_name}'")
            df = df.rename(columns={old_name: new_name})

    # Verificar y mapear columnas del DAX al esquema de Supabase
    for csv_col, supa_col in CSV_COLS_CATALOGO.items():
        if csv_col not in df.columns:
            found = [c for c in df.columns if csv_col.lower() in c.lower()]
            if found:
                print(f"   [Fallback] '{csv_col}' → '{found[0]}'")
                df = df.rename(columns={found[0]: csv_col})
            else:
                print(f"   [WARN] Columna '{csv_col}' no encontrada, se rellenará con valor por defecto")
                df[csv_col] = None

    df_clean = df.rename(columns=CSV_COLS_CATALOGO)

    # Seleccionar solo columnas necesarias
    for col in SUPABASE_COLS_CATALOGO:
        if col not in df_clean.columns:
            df_clean[col] = None
    df_clean = df_clean[SUPABASE_COLS_CATALOGO].copy()

    # ── Limpieza numérica ──
    df_clean['precio_con_iva'] = df_clean['precio_con_iva'].apply(convert_european_number)
    df_clean['coste_unitario'] = df_clean['coste_unitario'].apply(convert_european_number)
    df_clean['stock'] = df_clean['stock'].apply(convert_european_number).astype(int)
    df_clean['margen_teorico_pct'] = df_clean['margen_teorico_pct'].apply(convert_european_number).round(2)

    # ── Limpieza de booleano ──
    df_clean['bloqueado'] = df_clean['bloqueado'].apply(
        lambda x: True if str(x).strip().lower() in ['true', '1', 'yes', 'sí'] else False
    )

    # ── Limpieza de texto ──
    df_clean['codigo_producto'] = df_clean['codigo_producto'].astype(str).str.strip()
    df_clean['descripcion'] = df_clean['descripcion'].fillna('').str.strip()
    df_clean['familia'] = df_clean['familia'].fillna('Sin Clasificar').str.strip()
    df_clean['subfamilia'] = df_clean['subfamilia'].fillna('Sin Clasificar').str.strip()
    df_clean['unidad_medida'] = df_clean['unidad_medida'].fillna('').str.strip()

    # ── Normalización de familias ──
    df_clean['familia'] = df_clean['familia'].replace(NORMALIZACION_FAMILIAS)

    # ── Clasificación manual de productos sin categoría ──
    df_clean = aplicar_clasificacion_manual(df_clean)

    # ── Eliminar filas sin código ──
    antes = len(df_clean)
    df_clean = df_clean[df_clean['codigo_producto'].str.strip() != '']
    df_clean = df_clean.dropna(subset=['codigo_producto'])
    despues = len(df_clean)
    if antes != despues:
        print(f"   Eliminadas {antes - despues:,} filas sin código de producto")

    # ── Deduplicar por PK ──
    df_clean = df_clean.drop_duplicates(subset=['codigo_producto'])

    # ── Limpieza final ──
    df_clean = df_clean.replace({np.nan: None, np.inf: 0, -np.inf: 0})

    # ── Stats ──
    no_bloqueados = df_clean[~df_clean['bloqueado']].shape[0]
    con_precio = df_clean[df_clean['precio_con_iva'] > 0].shape[0]
    con_margen = df_clean[df_clean['margen_teorico_pct'] > 0].shape[0]

    print(f"   Productos totales: {len(df_clean):,}")
    print(f"   Activos (no bloqueados): {no_bloqueados:,}")
    print(f"   Con precio > 0: {con_precio:,}")
    print(f"   Con margen > 0: {con_margen:,}")
    print(f"   Familias: {df_clean['familia'].nunique()} → {df_clean['familia'].value_counts().head(10).to_dict()}")

    return df_clean


def proceso_catalogo(filename="catalogo_productos.csv"):
    """Ejecuta el proceso de carga del catálogo de productos."""
    print(f"\n{'─' * 60}")
    print(f"  PROCESO 3: CATÁLOGO DE PRODUCTOS")
    print(f"{'─' * 60}")

    path = find_file(filename)
    if not path:
        print(f"   [ERROR] Archivo no encontrado: {filename}")
        return False

    try:
        df = pd.read_csv(path, sep=';', encoding='utf-8-sig', low_memory=False)
        print(f"   [Extract] {len(df):,} filas, {len(df.columns)} columnas")
        df_clean = transform_catalogo(df)
        load_to_supabase(
            df_clean,
            table_name='catalogo_productos',
            conflict_cols='codigo_producto',
            delete_first=True
        )
        return True
    except Exception as e:
        print(f"   [CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='ETL Segmentador Petramora v6.0')
    parser.add_argument('--segmentacion', action='store_true', help='Ejecutar solo proceso de segmentación RFM')
    parser.add_argument('--lineas', action='store_true', help='Ejecutar solo proceso de líneas cliente-producto')
    parser.add_argument('--catalogo', action='store_true', help='Ejecutar solo proceso de catálogo de productos')
    parser.add_argument('--seg-file', default='Segmento_RFM_raw.csv', help='Archivo CSV de segmentación')
    parser.add_argument('--lineas-file', default='lineas_cliente_producto.csv', help='Archivo CSV de líneas')
    parser.add_argument('--catalogo-file', default='catalogo_productos.csv', help='Archivo CSV de catálogo')
    args = parser.parse_args()

    # Si no se especifica ningún flag, ejecutar todos
    ejecutar_todo = not (args.segmentacion or args.lineas or args.catalogo)

    print(f"\n{'=' * 60}")
    print(f"  ETL PETRAMORA v6.0")
    print(f"  Procesos: {'TODOS' if ejecutar_todo else ', '.join(filter(None, ['Segmentación' if args.segmentacion else '', 'Líneas' if args.lineas else '', 'Catálogo' if args.catalogo else '']))}")
    print(f"{'=' * 60}")

    resultados = {}

    if ejecutar_todo or args.segmentacion:
        resultados['segmentacion'] = proceso_segmentacion(args.seg_file)

    if ejecutar_todo or args.lineas:
        resultados['lineas'] = proceso_lineas(args.lineas_file)

    if ejecutar_todo or args.catalogo:
        resultados['catalogo'] = proceso_catalogo(args.catalogo_file)

    # ── Resumen ──
    print(f"\n{'=' * 60}")
    print(f"  RESUMEN")
    print(f"{'=' * 60}")
    for proceso, ok in resultados.items():
        status = "✅ OK" if ok else "❌ ERROR"
        print(f"   {proceso:20s} → {status}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()