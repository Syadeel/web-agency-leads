import psycopg2

conn = psycopg2.connect(
   dbname="postgres", user="postgres.hrzyuchlqihbdllbcxlh",
   password="azCdSWTma3F8V6Sp", host="aws-1-us-east-1.pooler.supabase.com", port="6543"
)
cursor = conn.cursor()

cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='leads';")
existing = set(r[0] for r in cursor.fetchall())
print("Existing columns:", existing)

columns = {
   "follower_count": "INTEGER",
   "follower_display": "VARCHAR(20)",
   "has_website": "BOOLEAN DEFAULT false",
   "website_status": "VARCHAR(50) DEFAULT 'unknown'",
   "website_url": "VARCHAR(500)",
   "business_type": "VARCHAR(50) DEFAULT 'other'",
   "city": "VARCHAR(100)",
   "country": "VARCHAR(10)",
   "priority": "VARCHAR(20) DEFAULT 'cold'",
   "enriched_at": "TIMESTAMP WITH TIME ZONE"
}

for col, dtype in columns.items():
   if col not in existing:
       cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {dtype};")
       print(f"Added: {col} ({dtype})")
   else:
       print(f"Exists: {col}")

cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='leads' ORDER BY ordinal_position;")
print("\nFinal schema:")
for r in cursor.fetchall():
   print(f"  {r[0]} ({r[1]})")

conn.commit()
cursor.close()
conn.close()
print("\nSchema migration complete!")
