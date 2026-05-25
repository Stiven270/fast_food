import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Ruta absoluta al archivo .env un nivel arriba
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '..', '.env')

# Cargamos explícitamente el archivo
load_dotenv(dotenv_path=env_path)

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Faltan las credenciales de Supabase en el archivo .env")

supabase: Client = create_client(url, key)