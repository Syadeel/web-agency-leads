import psycopg2
import csv
import os
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

def main():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Get columns in leads table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'leads';
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print("Columns in 'leads' table:", columns)
        
        # Fetch all rows from leads
        cursor.execute("SELECT * FROM leads;")
        rows = cursor.fetchall()
        print(f"Total leads in database: {len(rows)}")
        
        csv_filepath = os.path.join(os.path.dirname(__file__), "all_leads_from_db.csv")
        
        with open(csv_filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
            
        print(f"Successfully exported {len(rows)} leads to {csv_filepath}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
