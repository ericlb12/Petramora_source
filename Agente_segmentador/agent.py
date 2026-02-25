"""
Agente Segmentador - Petramora v4.0
Google GenAI SDK con FunctionDeclarations explícitas
- Esquema simplificado (10 columnas)
- Solo último mes + histórico anual
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
    get_segment_metrics,
    get_actionable_customers,
    get_customer_detail,
)

client = genai.Client(api_key=GOOGLE_API_KEY)

TOOLS_MAP = {
    "get_segment_distribution": get_segment_distribution,
    "get_segment_metrics": get_segment_metrics,
    "get_actionable_customers": get_actionable_customers,
    "get_customer_detail": get_customer_detail,
}

tool_declarations = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_segment_distribution",
            description=(
                "Distribución actual de clientes por segmento RFM. "
                "Usa para: '¿cuántos clientes hay?' o '¿cómo se distribuyen?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.FunctionDeclaration(
            name="get_segment_metrics",
            description=(
                "Métricas agregadas (gasto histórico) por segmento. "
                "Usa para: '¿cuánto gastan los Champions?' o '¿qué segmento genera más valor?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "segmento": {
                        "type": "string",
                        "description": "Filtrar por segmento. Sin especificar = todos."
                    }
                },
                "required": []
            }
        ),
        types.FunctionDeclaration(
            name="get_actionable_customers",
            description=(
                "HERRAMIENTA PRINCIPAL. Lista de clientes concretos que necesitan atención HOY. "
                "Prioriza Champions dormido. "
                "Usa para: '¿a quién llamo?', '¿a quién contactar?', '¿clientes en riesgo?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "criterio": {
                        "type": "string",
                        "description": (
                            "'today' (default), 'churn_risk', 'growth_potential', "
                            "'inactive_vip', 'new_high_value', 'top_historical'."
                        )
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Máximo de clientes (default: 10)"
                    }
                },
                "required": []
            }
        ),
        types.FunctionDeclaration(
            name="get_customer_detail",
            description=(
                "Detalle de un cliente específico: segmento, gasto por año (2024-2026). "
                "Usa para: '¿Por qué llamar a Beatriz?', 'Dime sobre X', '¿Cuánto gastó X en 2024?'"
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": "Nombre del cliente."
                    }
                },
                "required": ["cliente_id"]
            }
        ),
    ]
)


def log_interaction(session_id, user_message, agent_response, tools_called, model_used, latency_ms, error=None):
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


def save_session(session_id, history, user_id=None):
    try:
        supabase = get_supabase()
        supabase.table('agent_sessions').upsert({
            'session_id': session_id,
            'user_id': user_id,
            'history': _serialize_history(history),
            'updated_at': datetime.now().isoformat()
        }, on_conflict='session_id').execute()
    except Exception as e:
        print(f"   [Warning: No se pudo guardar sesión: {e}]")


def _serialize_history(history):
    serialized = []
    for item in history:
        if isinstance(item, types.Content):
            serialized.append({"role": item.role, "parts": [_serialize_part(p) for p in (item.parts or [])]})
        elif isinstance(item, dict):
            serialized.append(item)
        else:
            serialized.append({"role": "unknown", "parts": [{"text": str(item)}]})
    return serialized


def _serialize_part(part):
    if hasattr(part, 'text') and part.text:
        return {"text": part.text}
    if hasattr(part, 'function_call') and part.function_call:
        fc = part.function_call
        return {"function_call": {"name": fc.name, "args": dict(fc.args) if fc.args else {}}}
    if hasattr(part, 'function_response') and part.function_response:
        fr = part.function_response
        return {"function_response": {"name": fr.name, "response": fr.response if isinstance(fr.response, dict) else str(fr.response)}}
    return {"text": str(part)}


def load_session(session_id):
    try:
        supabase = get_supabase()
        response = supabase.table('agent_sessions').select('history').eq('session_id', session_id).execute()
        if response.data and response.data[0]['history']:
            return _deserialize_history(response.data[0]['history'])
    except Exception as e:
        print(f"   [Warning: No se pudo cargar sesión: {e}]")
    return []


def _deserialize_history(history_data):
    contents = []
    for item in history_data:
        if isinstance(item, dict) and 'role' in item and 'parts' in item:
            parts = []
            for p in item['parts']:
                if 'text' in p:
                    parts.append(types.Part.from_text(text=p['text']))
                elif 'function_call' in p:
                    fc = p['function_call']
                    parts.append(types.Part.from_function_call(name=fc['name'], args=fc.get('args', {})))
                elif 'function_response' in p:
                    fr = p['function_response']
                    parts.append(types.Part.from_function_response(name=fr['name'], response=fr.get('response', {})))
            if parts:
                contents.append(types.Content(role=item['role'], parts=parts))
    return contents


def execute_tool(tool_name, tool_args):
    if tool_name in TOOLS_MAP:
        try:
            result = TOOLS_MAP[tool_name](**tool_args)
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            return {"error": f"Error ejecutando {tool_name}: {str(e)}"}
    return {"error": f"Tool '{tool_name}' no encontrada"}


def call_model(model_name, history, config):
    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(multiplier=RETRY_DELAY, min=1, max=10), retry=retry_if_exception_type(Exception))
    def _call():
        return client.models.generate_content(model=model_name, contents=history, config=config)
    return _call()


def chat(user_message, session_id=None, history=None):
    start_time = time.time()
    if session_id is None:
        session_id = str(uuid.uuid4())
    if history is None:
        history = load_session(session_id)

    agent_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[tool_declarations],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.3,
    )

    history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    tools_called = []
    model_used = PRIMARY_MODEL
    error_msg = None

    try:
        response = call_model(PRIMARY_MODEL, history, agent_config)
    except Exception as e:
        print(f"   [Fallback: {PRIMARY_MODEL} falló, usando {FALLBACK_MODEL}]")
        try:
            response = call_model(FALLBACK_MODEL, history, agent_config)
            model_used = FALLBACK_MODEL
        except Exception as e2:
            error_msg = str(e2)
            latency_ms = int((time.time() - start_time) * 1000)
            log_interaction(session_id, user_message, "", tools_called, model_used, latency_ms, error_msg)
            return "Lo siento, estoy teniendo problemas técnicos. Intenta de nuevo."

    max_iterations = 10
    for iteration in range(max_iterations):
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            function_calls = [p for p in response.candidates[0].content.parts if hasattr(p, 'function_call') and p.function_call and p.function_call.name]

        if not function_calls:
            break

        history.append(response.candidates[0].content)
        function_response_parts = []

        for part in function_calls:
            fc = part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            print(f"   [Tool: {tool_name}({tool_args})]")
            tools_called.append({"name": tool_name, "args": tool_args})
            result = execute_tool(tool_name, tool_args)
            function_response_parts.append(types.Part.from_function_response(name=tool_name, response=result))

        history.append(types.Content(role="user", parts=function_response_parts))

        try:
            response = call_model(model_used, history, agent_config)
        except Exception as e:
            error_msg = str(e)
            break

    assistant_message = ""
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                assistant_message += part.text

    if not assistant_message.strip():
        assistant_message = "No pude generar una respuesta. ¿Podrías reformular?"
        error_msg = error_msg or "Respuesta vacía"

    if response.candidates and response.candidates[0].content:
        history.append(response.candidates[0].content)
    else:
        history.append(types.Content(role="model", parts=[types.Part.from_text(text=assistant_message)]))

    latency_ms = int((time.time() - start_time) * 1000)
    log_interaction(session_id, user_message, assistant_message, tools_called, model_used, latency_ms, error_msg)
    save_session(session_id, history)
    return assistant_message


def main():
    print("=" * 50)
    print("AGENTE SEGMENTADOR - PETRAMORA v4.0")
    print("=" * 50)
    print("Escribe 'salir' para terminar")
    print("Escribe 'nueva' para nueva sesión\n")

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
        print(chat(user_input, session_id, history))
        print()


if __name__ == "__main__":
    main()