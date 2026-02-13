"""
Diagnóstico rápido - Captura el error exacto de la API de Gemini
Ejecutar: python diagnose.py
"""

from google import genai
from google.genai import types
from config import GOOGLE_API_KEY, PRIMARY_MODEL, FALLBACK_MODEL

client = genai.Client(api_key=GOOGLE_API_KEY)

# Tool declaration mínima para probar
tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_count",
            description="Returns the total number of clients",
            parameters_json_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]
)

config = types.GenerateContentConfig(
    system_instruction="Eres un asistente. Usa la tool get_count para responder.",
    tools=[tool],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    temperature=0.3,
)

contents = [
    types.Content(
        role="user",
        parts=[types.Part.from_text(text="¿Cuántos clientes hay?")]
    )
]

# ── Test 1: Llamada simple ──
print("=" * 60)
print(f"TEST 1: Llamada simple con {PRIMARY_MODEL}")
print("=" * 60)
try:
    response = client.models.generate_content(
        model=PRIMARY_MODEL,
        contents=contents,
        config=config
    )
    print(f"  OK - Finish reason: {response.candidates[0].finish_reason}")
    print(f"  Function calls: {response.function_calls}")
    if response.text:
        print(f"  Text: {response.text[:200]}")
        
    # Si hay function call, simular la respuesta y hacer segunda llamada
    if response.function_calls:
        print("\n  → Function call detectada, simulando respuesta...")
        
        # Agregar model content al historial
        model_content = response.candidates[0].content
        contents.append(model_content)
        
        # Agregar function response
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name="get_count",
                        response={"total_clientes": 1000}
                    )
                ]
            )
        )
        
        print("\n  TEST 1b: Segunda llamada (con function response)...")
        try:
            response2 = client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=contents,
                config=config
            )
            print(f"  OK - Finish reason: {response2.candidates[0].finish_reason}")
            if response2.text:
                print(f"  Text: {response2.text[:300]}")
        except Exception as e2:
            print(f"  ERROR en segunda llamada: {type(e2).__name__}: {e2}")

except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── Test 2: Mismo test con fallback model ──
print(f"\n{'=' * 60}")
print(f"TEST 2: Llamada simple con {FALLBACK_MODEL}")
print("=" * 60)

contents_fb = [
    types.Content(
        role="user",
        parts=[types.Part.from_text(text="¿Cuántos clientes hay?")]
    )
]

try:
    response = client.models.generate_content(
        model=FALLBACK_MODEL,
        contents=contents_fb,
        config=config
    )
    print(f"  OK - Finish reason: {response.candidates[0].finish_reason}")
    print(f"  Function calls: {response.function_calls}")
    if response.text:
        print(f"  Text: {response.text[:200]}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── Test 3: Sin tools (solo texto) ──
print(f"\n{'=' * 60}")
print(f"TEST 3: Sin tools, solo texto con {PRIMARY_MODEL}")
print("=" * 60)

config_no_tools = types.GenerateContentConfig(
    system_instruction="Responde en español brevemente.",
    temperature=0.3,
)

try:
    response = client.models.generate_content(
        model=PRIMARY_MODEL,
        contents="Hola, ¿cómo estás?",
        config=config_no_tools
    )
    print(f"  OK: {response.text[:200]}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── Test 4: Verificar versión de la SDK ──
print(f"\n{'=' * 60}")
print("TEST 4: Info del entorno")
print("=" * 60)
try:
    import importlib.metadata
    version = importlib.metadata.version('google-genai')
    print(f"  google-genai version: {version}")
except:
    print("  No se pudo obtener versión de google-genai")

print(f"  PRIMARY_MODEL: {PRIMARY_MODEL}")
print(f"  FALLBACK_MODEL: {FALLBACK_MODEL}")

print(f"\n{'=' * 60}")
print("Diagnóstico completado.")
print("=" * 60)