"""
Migration runner for agents.blakelinde.com
Run from the /agent directory:
    .\.venv\Scripts\python.exe run_migration.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the /agent directory (which has a copy of the root .env)
load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not found in .env — check your environment file.")
    sys.exit(1)

# Supabase requires SSL — append if not already present
if "sslmode" not in db_url:
    db_url = db_url + "?sslmode=require"

# Read the SQL migration file
migration_path = Path(__file__).parent.parent / "supabase" / "migrations" / "001_initial_schema.sql"
if not migration_path.exists():
    print(f"❌ Migration file not found at: {migration_path}")
    sys.exit(1)

sql = migration_path.read_text()
print(f"📄 Running migration: {migration_path.name}")
print(f"🔗 Connecting to: {db_url[:40]}...")

try:
    import psycopg2
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Migration complete — all tables created in Supabase.")
except Exception as e:
    print(f"❌ Migration failed: {e}")
    print()
    print("💡 If you see a connection/dns error, go to your Supabase dashboard:")
    print("   Project Settings → Database → Connection string → Session Pooler (port 5432)")
    print("   Replace DATABASE_URL in your .env with the Session Pooler URL.")
    sys.exit(1)
