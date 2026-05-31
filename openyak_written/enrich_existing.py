import requests, re, os, time
from dotenv import load_dotenv
load_dotenv(r"F:\Anitgravity Data\web_agency_business\.env")
import psycopg2

conn = psycopg2.connect(dbname=os.getenv("SUPABASE_DB"), user=os.getenv("SUPABASE_USER"), password=os.getenv("SUPABASE_PASSWORD"), host=os.getenv("SUPABASE_HOST"), port=os.getenv("SUPABASE_PORT"))
cur = conn.cursor()
serpapi = os.getenv("SERPAPI_KEY")

cur.execute("SELECT id, instagram_handle FROM leads WHERE (email IS NULL OR email = '') AND instagram_handle IS NOT NULL AND instagram_handle != 'unknown' ORDER BY id LIMIT 100;")
leads = cur.fetchall()
print(f"Enriching {len(leads)} leads...")

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
FOLLOWER_REGEX = r"(\d[\d,]*\.?\d*)\s*[KkMmBb]?\s*(?:follower)"

count = 0
for lead_id, handle in leads:
    query = f'site:instagram.com "{handle}"'
    try:
        r = requests.get("https://serpapi.com/search", params={"engine":"google","q":query,"api_key":serpapi,"num":3}, timeout=15)
        r.raise_for_status()
        results = r.json().get("organic_results", [])
        for res in results:
            snippet = res.get("snippet", "")
            email_m = re.search(EMAIL_REGEX, snippet)
            fol_m = re.search(FOLLOWER_REGEX, snippet)
            email = email_m.group(0) if email_m else ""
            fol = fol_m.group(0) if fol_m else ""
            if email or fol:
                cur.execute("UPDATE leads SET email = %s, follower_display = %s WHERE id = %s AND (email IS NULL OR email = '');", (email, fol, lead_id))
                conn.commit()
                count += 1
                break
    except Exception as e:
        pass
    time.sleep(1)
    if count % 10 == 0:
        print(f"  Progress: {count}/{len(leads)}")

print(f"Done. Enriched {count} leads")
cur.close()
conn.close()
