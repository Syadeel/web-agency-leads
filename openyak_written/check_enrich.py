from dotenv import load_dotenv
load_dotenv(r"F:\Anitgravity Data\web_agency_business\.env")
import os, psycopg2
conn = psycopg2.connect(dbname=os.getenv("SUPABASE_DB"), user=os.getenv("SUPABASE_USER"), password=os.getenv("SUPABASE_PASSWORD"), host=os.getenv("SUPABASE_HOST"), port=os.getenv("SUPABASE_PORT"))
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM leads;")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != '';")
emails = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM leads WHERE follower_count IS NOT NULL AND follower_count > 0;")
followers = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM leads WHERE city IS NOT NULL AND city != '';")
cities = cur.fetchone()[0]
print(f"Total leads: {total}")
print(f"With email: {emails}")
print(f"With followers: {followers}")
print(f"With city: {cities}")
cur.execute("SELECT id, instagram_handle, email, follower_count, city FROM leads ORDER BY id DESC LIMIT 5;")
for r in cur.fetchall():
    print(f"  {r[0]} @{r[1]} email={r[2]} fol={r[3]} city={r[4]}")
conn.close()
