"""
Web Agency — Lead Exporter
Reads enriched leads from Supabase, generates multi-CSV exports.
Run after n8n scraper completes: python export_to_csv.py
"""
import psycopg2, csv, os
from datetime import datetime

DB = dict(
   dbname="postgres", user="postgres.hrzyuchlqihbdllbcxlh",
   password="azCdSWTma3F8V6Sp", host="aws-1-us-east-1.pooler.supabase.com", port="6543"
)
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_leads(status_filter=None):
   conn = psycopg2.connect(**DB)
   cursor = conn.cursor()
   where = f"WHERE priority != 'skip' AND follower_count >= 1000000" if status_filter is None else f"WHERE priority = '{status_filter}' AND follower_count >= 1000000"
   cursor.execute(f"SELECT * FROM leads {where} ORDER BY follower_count DESC;")
   cols = [d[0] for d in cursor.description]
   rows = cursor.fetchall()
   cursor.close()
   conn.close()
   return cols, rows

def write_csv(filename, cols, rows):
   path = os.path.join(OUTPUT_DIR, filename)
   with open(path, 'w', newline='', encoding='utf-8-sig') as f:
       w = csv.writer(f)
       w.writerow(cols)
       w.writerows(rows)
   print(f"  {filename}: {len(rows)} leads")
   return path

def main():
   print("=== Web Agency Lead Export ===")
   print(f"Time: {datetime.now().isoformat()}")
   
   # 1. ALL enriched leads (non-skip, 1M+)
   cols, all_leads = fetch_leads()
   write_csv("all_enriched_leads.csv", cols, all_leads)
   
   # 2. HOT leads: no website, selling products/services
   hot_cols, hot_leads = fetch_leads("hot")
   write_csv("hot_leads.csv", hot_cols, hot_leads)
   
   # 3. WARM leads: link-in-bio only
   warm_cols, warm_leads = fetch_leads("warm")
   write_csv("warm_leads.csv", warm_cols, warm_leads)
   
   # 4. Summary stats
   conn = psycopg2.connect(**DB)
   cursor = conn.cursor()
   for metric in [
       "COUNT(*) AS total",
       "SUM(CASE WHEN priority='hot' THEN 1 ELSE 0 END) AS hot",
       "SUM(CASE WHEN priority='warm' THEN 1 ELSE 0 END) AS warm",
       "SUM(CASE WHEN business_type='service' THEN 1 ELSE 0 END) AS service",
       "SUM(CASE WHEN business_type='product' THEN 1 ELSE 0 END) AS product",
       "SUM(CASE WHEN business_type='digital' THEN 1 ELSE 0 END) AS digital",
       "SUM(CASE WHEN country='US' THEN 1 ELSE 0 END) AS us",
       "SUM(CASE WHEN country='UK' THEN 1 ELSE 0 END) AS uk",
       "SUM(CASE WHEN country='EU' THEN 1 ELSE 0 END) AS eu",
       "SUM(CASE WHEN country='CA' THEN 1 ELSE 0 END) AS canada"
   ]:
       cursor.execute(f"SELECT {metric} FROM leads WHERE follower_count >= 1000000 AND priority != 'skip';")
       r = cursor.fetchone()
       print(f"  {metric.split('AS ')[1].strip()}: {r[0]}")
   cursor.close()
   conn.close()

if __name__ == "__main__":
   main()
