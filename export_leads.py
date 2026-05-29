"""
Export leads from Supabase to CSV.
Works with env vars (GitHub Actions) or .env file (local).
"""
import psycopg2
import csv
import os

try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv()
except ImportError:
    pass


def main():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("SUPABASE_DB", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            host=os.getenv("SUPABASE_HOST"),
            port=os.getenv("SUPABASE_PORT", "6543"),
        )
        cur = conn.cursor()

        # Get columns
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'leads'
            ORDER BY ordinal_position;
        """)
        columns = [row[0] for row in cur.fetchall()]

        # Fetch all rows
        cur.execute("SELECT * FROM leads ORDER BY id;")
        rows = cur.fetchall()

        # Write CSV
        base = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(base, "all_leads_from_db.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

        print(f"EXPORTED={len(rows)}")
        print(f"COLUMNS={len(columns)}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"EXPORT_ERROR={e}")
        raise


if __name__ == "__main__":
    main()
