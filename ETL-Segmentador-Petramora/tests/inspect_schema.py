
from config import get_supabase

def inspect_schema():
    supabase = get_supabase()
    try:
        # Get one row to see column names
        response = supabase.table('segmentacion_clientes_raw').select('*').limit(1).execute()
        if response.data:
            print("Columns found in segmentacion_clientes_raw:")
            for key in response.data[0].keys():
                print(f" - {key}")
        else:
            print("No data found in segmentacion_clientes_raw")
    except Exception as e:
        print(f"Error inspecting schema: {e}")

if __name__ == "__main__":
    inspect_schema()
