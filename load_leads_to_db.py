"""
Load leads from scraper CSV into the Supabase leads table.
Deduplicates by Instagram handle. Inserts only new leads.
"""
import csv
import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


def get_conn():
    load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT", "6543")
    )


def read_leads_csv(csv_path="leads.csv"):
    """Read leads from scraper CSV output."""
    leads = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)
    return leads


def insert_leads(leads):
    """Insert leads into DB, skip duplicates by instagram_handle."""
    conn = get_conn()
    cur = conn.cursor()

    # Count existing before
    cur.execute("SELECT COUNT(*) FROM leads;")
    before = cur.fetchone()[0]

    # Prepare data for upsert
    rows = []
    for lead in leads:
        handle = lead.get("Instagram Handle", "").strip().lower()
        if not handle or handle == "unknown":
            continue

        rows.append((
            handle,
            lead.get("Shop Name", "").strip(),
            lead.get("Bio Snippet", "")[:500],  # bio field
            lead.get("Phone Number", "").strip(),
            lead.get("Niche", "").strip().lower(),
        ))

    if not rows:
        print("[!] No valid leads to insert.")
        cur.close()
        conn.close()
        return 0, 0

    insert_sql = """
        INSERT INTO leads (instagram_handle, name, bio, phone, niche)
        VALUES %s
        ON CONFLICT (instagram_handle) DO NOTHING;
    """
    execute_values(cur, insert_sql, rows)
    conn.commit()

    # Count inserted
    cur.execute("SELECT COUNT(*) FROM leads;")
    after = cur.fetchone()[0]
    inserted = after - before
    skipped = len(rows) - inserted

    cur.close()
    conn.close()
    return inserted, skipped


def main():
    csv_path = os.path.join(os.path.dirname(__file__), "leads.csv")
    if not os.path.exists(csv_path):
        print(f"[!] No leads.csv found at {csv_path}")
        print("[!] Run scraper.py first or provide the CSV file.")
        return

    print(f"[*] Reading leads from {csv_path}")
    leads = read_leads_csv(csv_path)
    print(f"[*] Found {len(leads)} leads in CSV")

    inserted, skipped = insert_leads(leads)
    print(f"[+] Inserted {inserted} new leads to database")
    print(f"[-] Skipped {skipped} duplicates")

    # Get total in DB
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leads;")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"[#] Total leads in database: {total}")


if __name__ == "__main__":
    main()
