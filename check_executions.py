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
        
        # Check executions
        cursor.execute("SELECT id, \"workflowId\", status, \"startedAt\", \"stoppedAt\" FROM execution_entity ORDER BY \"startedAt\" DESC LIMIT 10;")
        rows = cursor.fetchall()
        print("--- Executions ---")
        for row in rows:
            print(f"ID: {row[0]}, WorkflowID: {row[1]}, Status: {row[2]}, StartedAt: {row[3]}, StoppedAt: {row[4]}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
