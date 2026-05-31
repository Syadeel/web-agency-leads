from dotenv import load_dotenv
import os, psycopg2
load_dotenv()
conn = psycopg2.connect(dbname=os.getenv('SUPABASE_DB','postgres'), user=os.getenv('SUPABASE_USER'), password=os.getenv('SUPABASE_PASSWORD'), host=os.getenv('SUPABASE_HOST'), port=os.getenv('SUPABASE_PORT','6543'))
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM leads;")
print("Leads in DB:", cur.fetchone()[0])
cur.execute("SELECT id, instagram_handle, name, phone, niche FROM leads ORDER BY id DESC LIMIT 5;")
for r in cur.fetchall():
    print(f"ID={r[0]} @{r[1]} name={r[2]} phone={r[3]} niche={r[4]}")
conn.close()
