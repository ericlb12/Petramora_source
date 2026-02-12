"""
Configuración del Agente Segmentador
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Google AI - Modelos
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.0-flash"

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 1  # segundos (se multiplica con backoff exponencial)

# Rutas de memoria
MEMORY_FILE = "memory/MEMORY.md"

# Cliente Supabase (singleton)
_supabase_client = None


def get_supabase():
    """Retorna el cliente de Supabase"""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Faltan credenciales de Supabase en .env")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client
