import psycopg2
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
        
        # Check all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        tables = cursor.fetchall()
        print("--- Tables ---")
        for table in tables:
            print(table[0])
            
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
