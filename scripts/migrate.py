"""
Run once to apply docs/schemas/db-schema.sql against Supabase.
Requires SUPABASE_SERVICE_ROLE_KEY and NEXT_PUBLIC_SUPABASE_URL in env.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "schemas" / "db-schema.sql"


def main() -> None:
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        print("ERROR: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    # Supabase exposes a Postgres connection string via the dashboard.
    # Use psycopg2 with the direct connection string from env if available.
    pg_url = os.environ.get("SUPABASE_DB_URL")
    if pg_url:
        try:
            import psycopg2  # type: ignore
        except ImportError:
            print("psycopg2 not installed. Run: pip install psycopg2-binary")
            sys.exit(1)

        conn = psycopg2.connect(pg_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("Migration applied via psycopg2.")
        return

    # Fallback: supabase-py rpc call (limited — for simple statements only).
    # For full DDL, prefer SUPABASE_DB_URL above.
    from supabase import create_client  # type: ignore

    client = create_client(url, key)
    # supabase-py does not expose raw SQL execution in the public API.
    # Paste db-schema.sql into the Supabase SQL editor if SUPABASE_DB_URL is unavailable.
    print(
        "SUPABASE_DB_URL not set. Please run the following SQL manually in the "
        "Supabase SQL editor:\n"
        f"  {SCHEMA_PATH.resolve()}"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
