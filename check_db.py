import psycopg2, json, os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
   dbname=os.getenv("SUPABASE_DB", "postgres"),
   user=os.getenv("SUPABASE_USER"),
   password=os.getenv("SUPABASE_PASSWORD"),
   host=os.getenv("SUPABASE_HOST"),
   port=os.getenv("SUPABASE_PORT", "6543")
)
cursor = conn.cursor()

cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
print("Tables:", [r[0] for r in cursor.fetchall()])

if "leads" in [r[0] for r in cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';") or []]:
   pass

cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='leads' ORDER BY ordinal_position;")
print("\nLeads cols:", [(r[0], r[1]) for r in cursor.fetchall()])

cursor.execute("SELECT COUNT(*) FROM leads;")
print("Lead count:", cursor.fetchone()[0])

cursor.execute("SELECT * FROM leads LIMIT 3;")
for r in cursor.fetchall():
   print(r)

cursor.execute("SELECT id, name, active FROM workflow_entity;")
print("\nWorkflows:")
for r in cursor.fetchall():
   print(r)

cursor.close()
conn.close()
