import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str | None = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase URL or Service Key not found in environment variables.")

# Use service key for backend operations (bypasses RLS)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_supabase() -> Client:
    """Dependency for Supabase client (Storage operations)."""
    return supabase_client


SupabaseClient = Annotated[Client, Depends(get_supabase)]
