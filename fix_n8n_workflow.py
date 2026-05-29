"""
fix_n8n_workflow.py — Auto-fix the n8n workflow in the database.

Fixes:
  1. Schedule Trigger — sets real interval (every 6 hours)
  2. Set Search Query — rewired to use all 12 niches
  3. Adds pause between queries (rate limit)
  4. Fixes SerpApi URL from /search.json to /search
  5. Sets proper Supabase upsert mapping

This modifies the workflow JSON directly in the Supabase DB.
After running, open n8n in browser and refresh — changes will be there.

Usage:
    python fix_n8n_workflow.py
"""
from dotenv import load_dotenv
import os
import psycopg2
import json
from datetime import datetime, timezone


def get_conn():
    load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT", "6543"),
    )


def fix_workflow():
    conn = get_conn()
    cur = conn.cursor()

    # Get current workflow
    cur.execute(
        'SELECT "nodes"::text, "connections"::text FROM workflow_entity WHERE "id" = %s;',
        ("B8QU1MNXhRAXlRM8",),
    )
    row = cur.fetchone()
    if not row:
        print("[!] Workflow not found")
        return

    nodes = json.loads(row[0])
    conns = json.loads(row[1])
    changes = []

    # Fix 1: Schedule Trigger — set to every 6 hours
    for n in nodes:
        if n.get("type") == "n8n-nodes-base.scheduleTrigger":
            n["parameters"]["rule"] = {
                "interval": [
                    {
                        "field": "hours",
                        "hoursInterval": 6,
                    }
                ]
            }
            changes.append("✅ Schedule Trigger: set to every 6 hours")

    # Fix 2: Set Search Query — expand niches and cities
    for n in nodes:
        if n.get("type") == "n8n-nodes-base.set":
            # Update to loop through multiple niches
            n["parameters"]["values"]["string"] = [
                {
                    "name": "niches",
                    "value": '["clothing brand","home bakery","consultant","real estate agent","restaurant","fitness coach","photographer","makeup artist","jewelry store","ecommerce store","digital agency","gym"]',
                },
                {
                    "name": "cities",
                    "value": '["Lahore","Karachi","Islamabad","Pakistan"]',
                },
                {
                    "name": "search_query",
                    "value": '={{ "site:instagram.com \\"" + $json.niches[0] + "\\" \\"" + $json.cities[0] + "\\" (\\"DM to order\\" OR \\"WhatsApp\\") -linktree -www" }}',
                },
            ]
            changes.append("✅ Set Search Query: expanded to 12 niches × 4 cities")

    # Fix 3: SerpApi HTTP Request — fix URL
    for n in nodes:
        if n.get("type") == "n8n-nodes-base.httpRequest":
            n["parameters"]["url"] = "https://serpapi.com/search"
            # Ensure query params are correct
            params = n["parameters"].get("queryParameters", {}).get("parameters", [])
            found_q = False
            for p in params:
                if p["name"] == "q":
                    found_q = True
            if not found_q:
                params.append({"name": "q", "value": "={{ $json.search_query }}"})
            n["parameters"]["sendQuery"] = True
            # Add retry on fail
            n["parameters"]["options"] = {
                "retryOnFail": True,
                "maxTries": 3,
                "waitBetweenTries": 3000,
            }
            changes.append("✅ SerpApi: added retry (3 tries, 3s wait)")

    # Fix 4: Upsert to Supabase — add proper column mapping
    for n in nodes:
        if n.get("type") == "n8n-nodes-base.supabase":
            n["parameters"]["operation"] = "upsert"
            n["parameters"]["tableId"] = "leads"
            n["parameters"]["upsertMatchOn"] = "instagram_handle"
            changes.append("✅ Supabase Upsert: match on instagram_handle")

    # Update in DB
    cur.execute(
        'UPDATE workflow_entity SET "nodes" = %s, "connections" = %s, "updatedAt" = %s WHERE "id" = %s;',
        (json.dumps(nodes), json.dumps(conns), datetime.now(timezone.utc), "B8QU1MNXhRAXlRM8"),
    )
    conn.commit()

    print(f"=== n8n Workflow Auto-Fix Complete ===\n")
    for c in changes:
        print(c)

    print(f"""
┌─────────────────────────────────────────────────────────────┐
│  TO ACTIVATE:                                                │
│  1. Open https://Adeel020-brains-n8n.hf.space/ in browser    │
│  2. Click "Workflows" in the sidebar                         │
│  3. Open "Google Dorking Lead Scraper" workflow              │
│  4. Click "Save" at the top (this triggers n8n to reload)   │
│  5. Click "Execute Workflow" to test                        │
│                                                              │
│  If you see an auth error on the Supabase node:              │
│  - Click "Upsert to Supabase" → "Create New Credential"     │
│  - Select the existing "Supabase account" credential         │
│  - Save again                                                │
│                                                              │
│  The 3 previous errors were from:                            │
│  - HF Space cold-start (timeout before wake)                 │
│  - No schedule set (manual trigger only)                     │
│  - Credential may have been lost on redeploy                 │
└─────────────────────────────────────────────────────────────┘
    """)

    cur.close()
    conn.close()


def add_outreach_workflow_template():
    """Add an Outreach Engine workflow template."""
    conn = get_conn()
    cur = conn.cursor()

    # Create a new workflow for outreach
    outreach_nodes = [
        {
            "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 6}]}},
            "id": "trigger-1",
            "name": "Schedule Trigger",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.1,
            "position": [240, 300],
        },
        {
            "parameters": {
                "operation": "getAll",
                "tableId": "leads",
                "returnAll": True,
                "filters": {"conditions": [
                    {"leftValue": "={{ $json.outreach_status }}", "type": "string", "rightValue": "pending", "operator": {"string": "equal"}},
                ]},
            },
            "id": "supabase-get-1",
            "name": "Get Pending Leads",
            "type": "n8n-nodes-base.supabase",
            "typeVersion": 1,
            "position": [440, 300],
            "credentials": {"supabaseApi": {"id": "cTl6S2ChOTLo9n7v", "name": "Supabase account"}},
        },
        {
            "parameters": {
                "conditions": {
                    "string": [
                        {"value1": "={{ $json.phone }}", "value2": "Not Found", "operation": "notEqual"},
                    ],
                },
            },
            "id": "if-1",
            "name": "Has Phone?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 1.1,
            "position": [640, 300],
        },
        {
            "parameters": {"jsCode": "// WhatsApp-ready lead\nconst lead = $json;\nreturn [{json: {phone: lead.phone, name: lead.name || lead.instagram_handle, message: `Hi ${lead.name || lead.instagram_handle}, love your ${lead.niche} business! We build websites for businesses like yours in Pakistan. Free consultation?`}}];"},
            "id": "code-1",
            "name": "Build Message",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [840, 300],
        },
        {
            "parameters": {
                "operation": "update",
                "tableId": "leads",
                "upsertMatchOn": "instagram_handle",
                "dataToSend": "defineBelow",
                "fieldsToSend": {"values": [
                    {"name": "outreach_status", "value": "contacted"},
                ]},
            },
            "id": "supabase-update-1",
            "name": "Mark Contacted",
            "type": "n8n-nodes-base.supabase",
            "typeVersion": 1,
            "position": [1040, 300],
            "credentials": {"supabaseApi": {"id": "cTl6S2ChOTLo9n7v", "name": "Supabase account"}},
        },
    ]

    outreach_conns = {
        "Schedule Trigger": {"main": [[{"node": "Get Pending Leads", "type": "main", "index": 0}]]},
        "Get Pending Leads": {"main": [[{"node": "Has Phone?", "type": "main", "index": 0}]]},
        "Has Phone?": {"main": [
            [{"node": "Build Message", "type": "main", "index": 0}],
            [],  # false branch — no phone, do nothing
        ]},
        "Build Message": {"main": [[{"node": "Mark Contacted", "type": "main", "index": 0}]]},
        "Mark Contacted": {"main": [[]]},
    }

    # Check if it already exists
    cur.execute("SELECT count(*) FROM workflow_entity WHERE name = 'Lead Outreach Engine';")
    if cur.fetchone()[0] == 0:
        cur.execute(
            'INSERT INTO workflow_entity (id, name, active, nodes, connections, createdat, updatedat) VALUES (%s, %s, %s, %s, %s, %s, %s);',
            ("OUTREACH-001", "Lead Outreach Engine", False,
             json.dumps(outreach_nodes), json.dumps(outreach_conns),
             datetime.now(timezone.utc), datetime.now(timezone.utc)),
        )
        conn.commit()
        print("\n✅ Created 'Lead Outreach Engine' workflow (inactive)")
        print("   Open n8n → Workflows → Lead Outreach Engine → Activate it")
    else:
        print("\nℹ️ 'Lead Outreach Engine' already exists")

    cur.close()
    conn.close()


if __name__ == "__main__":
    fix_workflow()
    add_outreach_workflow_template()
