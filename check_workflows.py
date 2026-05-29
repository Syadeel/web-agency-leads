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
        
        # Check active status of workflows
        cursor.execute("SELECT id, name, active FROM workflow_entity;")
        rows = cursor.fetchall()
        print("--- Workflows ---")
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, Active: {row[2]}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error connecting to database:", e)

if __name__ == "__main__":
    main()
