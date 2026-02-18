"""
Agente Segmentador - Petramora
Implementado con Google GenAI SDK (google-genai)
Versión corregida: FunctionDeclarations explícitas + historial tipado
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
    get_supabase
)
from prompts import SYSTEM_PROMPT
from tools import (
    get_segment_distribution,
    get_segment_evolution,
    get_segment_metrics,
)

# ─────────────────────────────────────────────
# Cliente Google GenAI
# ─────────────────────────────────────────────
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─────────────────────────────────────────────
# Mapeo de funciones ejecutables
# ─────────────────────────────────────────────
TOOLS_MAP = {
    "get_segment_distribution": get_segment_distribution,
    "get_segment_evolution": get_segment_evolution,
    "get_segment_metrics": get_segment_metrics,
}

# ─────────────────────────────────────────────
# Declaración explícita de tools (FunctionDeclaration)
# Esto evita AFC y da control total sobre el schema
# ─────────────────────────────────────────────
tool_declarations = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_segment_distribution",
            description=(
                "Obtiene la distribución de clientes por segmento RFM para una fecha específica. "
                "Usa para preguntas como '¿cuántos clientes hay en cada segmento?' o "
                "'¿cómo se distribuyen los Champions?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "fecha_corte": {
                        "type": "string",
                        "description": (
                            "Fecha en formato YYYY-MM-DD. Si no se especifica, "
                            "usa la más reciente disponible."
                        )
                    },
                    "grupo": {
                        "type": "string",
                        "description": (
                            "Filtrar por grupo: '1. Champions', '2. Ricos', "
                            "'3. Oportunistas', 'Otros'. Si no se especifica, "
                            "retorna todos los grupos."
                        )
                    }
                },
                "required": []
            }
        ),
        types.FunctionDeclaration(
            name="get_segment_evolution",
            description=(
                "Obtiene la evolución temporal de un segmento o de todos los segmentos. "
                "Usa para preguntas como '¿cómo han evolucionado los Champions dormido?' "
                "o '¿tendencia de los últimos meses?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "segmento": {
                        "type": "string",
                        "description": (
                            "Nombre exacto del segmento RFM: 'Champion', 'Champions casi recurrente', "
                            "'Champions dormido', 'Rico potencial', 'Oportunista nuevo', "
                            "'Oportunista con potencial', 'Oportunista perdido', 'Rico perdido', "
                            "'Activo Básico', '0'. Si no se especifica, retorna todos."
                        )
                    },
                    "meses": {
                        "type": "integer",
                        "description": "Número de meses hacia atrás a consultar (default: 6)"
                    }
                },
                "required": []
            }
        ),
        types.FunctionDeclaration(
            name="get_segment_metrics",
            description=(
                "Obtiene métricas agregadas por segmento: gasto total, gasto promedio, "
                "recencia promedio, frecuencia promedio y porcentaje del gasto total. "
                "Usa para preguntas como '¿cuánto gastan los Champions?' o "
                "'¿qué segmento genera más ingresos?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "fecha_corte": {
                        "type": "string",
                        "description": (
                            "Fecha en formato YYYY-MM-DD. Si no se especifica, "
                            "usa la más reciente disponible."
                        )
                    },
                    "segmento": {
                        "type": "string",
                        "description": (
                            "Filtrar por segmento específico (ej: 'Champion', 'Rico perdido', "
                            "'Oportunista nuevo'). Si no se especifica, retorna todos."
                        )
                    }
                },
                "required": []
            }
        ),
    ]
)


# ─────────────────────────────────────────────
# Logging y sesiones en Supabase
# ─────────────────────────────────────────────

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
    """Guarda o actualiza la sesión en Supabase (serializa types.Content a dict)"""
    try:
        supabase = get_supabase()
        # Serializar historial de types.Content a dicts para JSON
        serializable_history = _serialize_history(history)
        supabase.table('agent_sessions').upsert({
            'session_id': session_id,
            'user_id': user_id,
            'history': serializable_history,
            'updated_at': datetime.now().isoformat()
        }, on_conflict='session_id').execute()
    except Exception as e:
        print(f"   [Warning: No se pudo guardar sesión: {e}]")


def _serialize_history(history: list) -> list:
    """Convierte lista de types.Content a lista de dicts serializables"""
    serialized = []
    for item in history:
        if isinstance(item, types.Content):
            serialized.append({
                "role": item.role,
                "parts": [_serialize_part(p) for p in (item.parts or [])]
            })
        elif isinstance(item, dict):
            serialized.append(item)
        else:
            serialized.append({"role": "unknown", "parts": [{"text": str(item)}]})
    return serialized


def _serialize_part(part) -> dict:
    """Convierte un types.Part a dict serializable"""
    if hasattr(part, 'text') and part.text:
        return {"text": part.text}
    if hasattr(part, 'function_call') and part.function_call:
        fc = part.function_call
        return {
            "function_call": {
                "name": fc.name,
                "args": dict(fc.args) if fc.args else {}
            }
        }
    if hasattr(part, 'function_response') and part.function_response:
        fr = part.function_response
        return {
            "function_response": {
                "name": fr.name,
                "response": fr.response if isinstance(fr.response, dict) else str(fr.response)
            }
        }
    return {"text": str(part)}


def load_session(session_id: str) -> list:
    """Carga una sesión existente de Supabase y la convierte a types.Content"""
    try:
        supabase = get_supabase()
        response = supabase.table('agent_sessions') \
            .select('history') \
            .eq('session_id', session_id) \
            .execute()
        
        if response.data and response.data[0]['history']:
            return _deserialize_history(response.data[0]['history'])
    except Exception as e:
        print(f"   [Warning: No se pudo cargar sesión: {e}]")
    
    return []


def _deserialize_history(history_data: list) -> list:
    """Convierte lista de dicts a lista de types.Content"""
    contents = []
    for item in history_data:
        if isinstance(item, dict) and 'role' in item and 'parts' in item:
            parts = []
            for p in item['parts']:
                if 'text' in p:
                    parts.append(types.Part.from_text(text=p['text']))
                elif 'function_call' in p:
                    fc = p['function_call']
                    parts.append(types.Part.from_function_call(
                        name=fc['name'],
                        args=fc.get('args', {})
                    ))
                elif 'function_response' in p:
                    fr = p['function_response']
                    parts.append(types.Part.from_function_response(
                        name=fr['name'],
                        response=fr.get('response', {})
                    ))
            if parts:
                contents.append(types.Content(role=item['role'], parts=parts))
    return contents


# ─────────────────────────────────────────────
# Ejecución de tools
# ─────────────────────────────────────────────

def execute_tool(tool_name: str, tool_args: dict) -> dict:
    """Ejecuta una tool y retorna el resultado como dict"""
    if tool_name in TOOLS_MAP:
        try:
            result = TOOLS_MAP[tool_name](**tool_args)
            # Asegurar que el resultado es serializable
            if isinstance(result, dict):
                return result
            return {"result": str(result)}
        except Exception as e:
            return {"error": f"Error ejecutando {tool_name}: {str(e)}"}
    return {"error": f"Tool '{tool_name}' no encontrada"}


# ─────────────────────────────────────────────
# Llamada al modelo con reintentos
# ─────────────────────────────────────────────

def call_model(model_name: str, history: list, config: types.GenerateContentConfig):
    """Llama al modelo con reintentos usando tenacity"""
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


# ─────────────────────────────────────────────
# Función principal del agente
# ─────────────────────────────────────────────

def chat(user_message: str, session_id: str = None, history: list = None) -> str:
    """
    Envía un mensaje al agente y retorna la respuesta.
    
    Args:
        user_message: Mensaje del usuario
        session_id: ID de sesión para persistencia
        history: Historial de conversación (lista de types.Content)
    
    Returns:
        Respuesta del agente como string
    """
    start_time = time.time()
    
    # Inicializar sesión
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    if history is None:
        history = load_session(session_id)
    
    # Configuración del agente
    # - tools: declaraciones explícitas (no funciones Python)
    # - automatic_function_calling: DESACTIVADO (lo manejamos nosotros)
    agent_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[tool_declarations],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.3,
    )
    
    # Agregar mensaje del usuario usando types.Content
    history.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        )
    )
    
    tools_called = []
    model_used = PRIMARY_MODEL
    error_msg = None
    
    # ── Primera llamada al modelo ──
    try:
        response = call_model(PRIMARY_MODEL, history, agent_config)
        model_used = PRIMARY_MODEL
    except Exception as e:
        print(f"   [Fallback: {PRIMARY_MODEL} falló ({type(e).__name__}: {e}), usando {FALLBACK_MODEL}]")
        try:
            response = call_model(FALLBACK_MODEL, history, agent_config)
            model_used = FALLBACK_MODEL
        except Exception as e2:
            error_msg = f"Ambos modelos fallaron: {type(e2).__name__}: {str(e2)}"
            print(f"   [ERROR: {error_msg}]")
            latency_ms = int((time.time() - start_time) * 1000)
            log_interaction(session_id, user_message, "", tools_called, model_used, latency_ms, error_msg)
            return "Lo siento, estoy teniendo problemas técnicos. Por favor, intenta de nuevo en unos momentos."
    
    # ── Loop de function calling ──
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Verificar si hay function calls en la respuesta
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            function_calls = [
                part for part in response.candidates[0].content.parts
                if hasattr(part, 'function_call') and part.function_call and part.function_call.name
            ]
        
        if not function_calls:
            break
        
        # Guardar el content completo del modelo en el historial
        # (preserva thought signatures y otros metadatos)
        model_content = response.candidates[0].content
        history.append(model_content)
        
        # Ejecutar cada function call y construir las respuestas
        function_response_parts = []
        
        for part in function_calls:
            fc = part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            
            print(f"   [Tool: {tool_name}({tool_args})]")
            tools_called.append({"name": tool_name, "args": tool_args})
            
            # Ejecutar la tool
            result = execute_tool(tool_name, tool_args)
            
            # Crear Part de function response
            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response=result
                )
            )
        
        # Agregar las respuestas de las tools al historial
        # El role para function responses es "user" en la API de Gemini
        history.append(
            types.Content(
                role="user",
                parts=function_response_parts
            )
        )
        
        # Continuar generación con el modelo
        try:
            response = call_model(model_used, history, agent_config)
        except Exception as e:
            error_msg = f"Error en continuación de function calling: {type(e).__name__}: {str(e)}"
            print(f"   [ERROR: {error_msg}]")
            break
    
    # ── Extraer texto de respuesta ──
    assistant_message = ""
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                assistant_message += part.text
    
    # Validar respuesta vacía
    if not assistant_message.strip():
        assistant_message = "No pude generar una respuesta. ¿Podrías reformular tu pregunta?"
        error_msg = error_msg or "Respuesta vacía del modelo"
    
    # Agregar respuesta final del modelo al historial
    if response.candidates and response.candidates[0].content:
        history.append(response.candidates[0].content)
    else:
        history.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=assistant_message)]
            )
        )
    
    # Calcular latencia y guardar
    latency_ms = int((time.time() - start_time) * 1000)
    
    log_interaction(session_id, user_message, assistant_message, tools_called, model_used, latency_ms, error_msg)
    save_session(session_id, history)
    
    return assistant_message


# ─────────────────────────────────────────────
# Loop interactivo
# ─────────────────────────────────────────────

def main():
    """Loop interactivo para probar el agente"""
    print("=" * 50)
    print("AGENTE SEGMENTADOR - PETRAMORA")
    print("=" * 50)
    print("Escribe 'salir' para terminar")
    print("Escribe 'nueva' para iniciar nueva sesión\n")
    
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
        
        if not user_input:
            continue
        
        print("\nAgente: ", end="", flush=True)
        response = chat(user_input, session_id, history)
        print(response)
        print()


if __name__ == "__main__":
    main()