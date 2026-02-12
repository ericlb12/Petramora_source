"""
Agente Segmentador - Petramora
Implementado con Google ADK
"""

import os
import json
import time
import uuid
from datetime import datetime
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import (
    GOOGLE_API_KEY, 
    PRIMARY_MODEL, 
    FALLBACK_MODEL,
    MAX_RETRIES,
    RETRY_DELAY,
    MEMORY_FILE,
    get_supabase
)
from prompts import SYSTEM_PROMPT
from tools import (
    get_segment_distribution,
    get_segment_evolution,
    get_segment_metrics,
    save_to_memory
)

# Configurar cliente
client = genai.Client(api_key=GOOGLE_API_KEY)

# Mapeo de tools
TOOLS_MAP = {
    "get_segment_distribution": get_segment_distribution,
    "get_segment_evolution": get_segment_evolution,
    "get_segment_metrics": get_segment_metrics,
    "save_to_memory": save_to_memory
}

# Lista de tools para el agente
tools = list(TOOLS_MAP.values())


def load_memory() -> str:
    """Carga el archivo de memoria curada si existe"""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def get_system_prompt_with_memory() -> str:
    """Combina el system prompt con la memoria curada"""
    memory = load_memory()
    if memory:
        return f"{SYSTEM_PROMPT}\n\n## Memoria del contexto anterior\n{memory}"
    return SYSTEM_PROMPT


def log_interaction(session_id: str, user_message: str, agent_response: str, 
                    tools_called: list, model_used: str, latency_ms: int, error: str = None):
    """Guarda la interacción en Supabase"""
    try:
        supabase = get_supabase()
        supabase.table('agent_logs').insert({
            'session_id': session_id,
            'user_message': user_message,
            'agent_response': agent_response,
            'tools_called': tools_called,
            'model_used': model_used,
            'latency_ms': latency_ms,
            'error': error
        }).execute()
    except Exception as e:
        print(f"   [Warning: No se pudo guardar log: {e}]")


def save_session(session_id: str, history: list, user_id: str = None):
    """Guarda o actualiza la sesión en Supabase"""
    try:
        supabase = get_supabase()
        supabase.table('agent_sessions').upsert({
            'session_id': session_id,
            'user_id': user_id,
            'history': history,
            'updated_at': datetime.now().isoformat()
        }, on_conflict='session_id').execute()
    except Exception as e:
        print(f"   [Warning: No se pudo guardar sesión: {e}]")


def load_session(session_id: str) -> list:
    """Carga una sesión existente de Supabase"""
    try:
        supabase = get_supabase()
        response = supabase.table('agent_sessions') \
            .select('history') \
            .eq('session_id', session_id) \
            .execute()
        
        if response.data and response.data[0]['history']:
            return response.data[0]['history']
    except Exception as e:
        print(f"   [Warning: No se pudo cargar sesión: {e}]")
    
    return []


def execute_tool(tool_name: str, tool_args: dict) -> dict:
    """Ejecuta una tool y retorna el resultado"""
    if tool_name in TOOLS_MAP:
        try:
            return TOOLS_MAP[tool_name](**tool_args)
        except Exception as e:
            return {"error": f"Error ejecutando {tool_name}: {str(e)}"}
    return {"error": f"Tool '{tool_name}' no encontrada"}


def call_model(model_name: str, history: list, config: types.GenerateContentConfig):
    """Llama al modelo con reintentos"""
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY, min=1, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def _call():
        return client.models.generate_content(
            model=model_name,
            contents=history,
            config=config
        )
    
    return _call()


def chat(user_message: str, session_id: str = None, history: list = None) -> str:
    """
    Envía un mensaje al agente y retorna la respuesta.
    
    Args:
        user_message: Mensaje del usuario
        session_id: ID de sesión para persistencia
        history: Historial de conversación (opcional)
    
    Returns:
        Respuesta del agente
    """
    start_time = time.time()
    
    # Inicializar sesión si no existe
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    if history is None:
        history = load_session(session_id)
    
    # Configuración del agente con memoria
    agent_config = types.GenerateContentConfig(
        system_instruction=get_system_prompt_with_memory(),
        tools=tools,
        temperature=0.3,
    )
    
    # Agregar mensaje del usuario al historial
    history.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })
    
    tools_called = []
    model_used = PRIMARY_MODEL
    error_msg = None
    
    try:
        # Intentar con modelo principal
        response = call_model(PRIMARY_MODEL, history, agent_config)
        model_used = PRIMARY_MODEL
    except Exception as e:
        print(f"   [Fallback: {PRIMARY_MODEL} falló, usando {FALLBACK_MODEL}]")
        try:
            response = call_model(FALLBACK_MODEL, history, agent_config)
            model_used = FALLBACK_MODEL
        except Exception as e2:
            error_msg = f"Ambos modelos fallaron: {str(e2)}"
            latency_ms = int((time.time() - start_time) * 1000)
            log_interaction(session_id, user_message, "", tools_called, model_used, latency_ms, error_msg)
            return "Lo siento, estoy teniendo problemas técnicos. Por favor, intenta de nuevo en unos momentos."
    
    # Procesar respuesta (manejar múltiples tool calls)
    max_iterations = 10  # Prevenir loops infinitos
    iteration = 0
    
    while response.candidates and response.candidates[0].content.parts and iteration < max_iterations:
        iteration += 1
        
        # Verificar si hay function calls en cualquiera de los parts
        function_calls = [
            part.function_call 
            for part in response.candidates[0].content.parts 
            if hasattr(part, 'function_call') and part.function_call
        ]
        
        if not function_calls:
            break
        
        # Procesar todas las function calls
        model_parts = []
        user_parts = []
        
        for function_call in function_calls:
            tool_name = function_call.name
            tool_args = dict(function_call.args) if function_call.args else {}
            
            print(f"   [Tool: {tool_name}({tool_args})]")
            tools_called.append({"name": tool_name, "args": tool_args})
            
            # Ejecutar la tool
            result = execute_tool(tool_name, tool_args)
            
            # Preparar respuestas
            model_parts.append({"function_call": function_call})
            user_parts.append({
                "function_response": {
                    "name": tool_name,
                    "response": result
                }
            })
        
        # Agregar al historial
        history.append({
            "role": "model",
            "parts": model_parts
        })
        history.append({
            "role": "user",
            "parts": user_parts
        })
        
        # Continuar generación
        try:
            response = call_model(model_used, history, agent_config)
        except Exception as e:
            error_msg = f"Error en continuación: {str(e)}"
            break
    
    # Extraer texto de respuesta
    assistant_message = ""
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                assistant_message += part.text
    
    # Validar respuesta vacía
    if not assistant_message.strip():
        assistant_message = "No pude generar una respuesta. ¿Podrías reformular tu pregunta?"
        error_msg = "Respuesta vacía del modelo"
    
    # Agregar al historial
    history.append({
        "role": "model",
        "parts": [{"text": assistant_message}]
    })
    
    # Calcular latencia y guardar
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Guardar log e interacción
    log_interaction(session_id, user_message, assistant_message, tools_called, model_used, latency_ms, error_msg)
    save_session(session_id, history)
    
    return assistant_message


def main():
    """Loop interactivo para probar el agente"""
    print("="*50)
    print("AGENTE SEGMENTADOR - PETRAMORA")
    print("="*50)
    print("Escribe 'salir' para terminar")
    print("Escribe 'nueva' para iniciar nueva sesión")
    print("Escribe 'memoria' para ver la memoria actual\n")
    
    session_id = str(uuid.uuid4())
    history = []
    
    print(f"[Sesion: {session_id[:8]}...]\n")
    
    while True:
        user_input = input("Tu: ").strip()
        
        if user_input.lower() in ['salir', 'exit', 'quit']:
            print("Hasta luego!")
            break
        
        if user_input.lower() == 'nueva':
            session_id = str(uuid.uuid4())
            history = []
            print(f"\n[Nueva sesion: {session_id[:8]}...]\n")
            continue
        
        if user_input.lower() == 'memoria':
            memory = load_memory()
            print("\n" + "="*50)
            print("MEMORIA ACTUAL:")
            print("="*50)
            print(memory if memory else "(vacía)")
            print("="*50 + "\n")
            continue
        
        if not user_input:
            continue
        
        print("\nAgente: ", end="", flush=True)
        response = chat(user_input, session_id, history)
        print(response)
        print()


if __name__ == "__main__":
    main()