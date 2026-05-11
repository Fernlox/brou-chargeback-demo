"""Supabase client bootstrap for backend services."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

_supabase_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client configured from environment variables."""
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    missing_vars = [
        var_name
        for var_name, var_value in (
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", supabase_service_role_key),
        )
        if not var_value
    ]
    if missing_vars:
        missing = ", ".join(missing_vars)
        raise RuntimeError(f"Missing required Supabase env vars: {missing}")

    _supabase_client = create_client(supabase_url, supabase_service_role_key)
    return _supabase_client
