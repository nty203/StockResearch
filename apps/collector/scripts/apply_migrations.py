"""Apply pending Supabase migrations via SUPABASE_DB_URL.

Each file is run inside its own transaction. Idempotent migrations
(IF NOT EXISTS / ON CONFLICT) are safe to re-run.

Usage:
  uv run python -m scripts.apply_migrations  003 004 005 006 006b
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def find_migration(prefix: str) -> Path:
    matches = sorted(MIGRATIONS_DIR.glob(f"{prefix}_*.sql")) + sorted(MIGRATIONS_DIR.glob(f"{prefix}*.sql"))
    if not matches:
        raise FileNotFoundError(f"No migration file matching prefix '{prefix}' under {MIGRATIONS_DIR}")
    return matches[0]


def apply(prefixes: list[str]) -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set", file=sys.stderr)
        sys.exit(2)

    files = [find_migration(p) for p in prefixes]
    print("Connecting to Supabase...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        for f in files:
            sql = f.read_text(encoding="utf-8")
            print(f"\n-- Applying {f.name} ({len(sql)} bytes)...")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                print(f"  [OK] {f.name} applied")
            except Exception as e:
                conn.rollback()
                print(f"  [FAIL] {f.name}: {e}", file=sys.stderr)
                raise
    finally:
        conn.close()
    print("\nAll migrations applied successfully.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: uv run python -m scripts.apply_migrations 003 004 005 006 006b")
        sys.exit(1)
    apply(args)
