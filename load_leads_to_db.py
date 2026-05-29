"""
Load leads from scraper CSV into the Supabase leads table.
Deduplicates by Instagram handle. Inserts only new leads.
Works with env vars (GitHub Actions) or .env file (local).
"""
import csv
import os
import psycopg2
from psycopg2.extras import execute_values

# Dotenv is optional — works with real env vars on GitHub Actions
try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv()
except ImportError:
    pass


def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT", "6543"),
    )


def read_leads_csv(csv_path="leads.csv"):
    if not os.path.exists(csv_path):
        return []
    leads = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)
    return leads


def insert_leads(leads):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM leads;")
    before = cur.fetchone()[0]

    rows = []
    for lead in leads:
        handle = lead.get("Instagram Handle", "").strip().lower()
        if not handle or handle == "unknown":
            continue
        rows.append((
            handle,
            (lead.get("Shop Name", "") or "").strip()[:255],
            (lead.get("Bio Snippet", "") or "")[:500],
            (lead.get("Phone Number", "") or "").strip(),
            (lead.get("Niche", "") or "").strip().lower(),
        ))

    if not rows:
        cur.close()
        conn.close()
        return 0, 0

    try:
        insert_sql = """
            INSERT INTO leads (instagram_handle, name, bio, phone, niche)
            VALUES %s
            ON CONFLICT (instagram_handle) DO NOTHING;
        """
        execute_values(cur, insert_sql, rows)
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise e

    cur.execute("SELECT COUNT(*) FROM leads;")
    after = cur.fetchone()[0]
    inserted = after - before
    skipped = len(rows) - inserted

    cur.close()
    conn.close()
    return inserted, skipped


def main():
    # Use absolute path for GitHub Actions
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "leads.csv")

    if not os.path.exists(csv_path):
        print("CSV_NOT_FOUND=1")
        return

    leads = read_leads_csv(csv_path)
    if not leads:
        print("LEADS_IN_CSV=0")
        return

    inserted, skipped = insert_leads(leads)
    print(f"INSERTED={inserted}")
    print(f"SKIPPED={skipped}")

    # Get total
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leads;")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"TOTAL_IN_DB={total}")


if __name__ == "__main__":
    main()
