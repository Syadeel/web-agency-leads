# n8n Hugging Face Workflow — Analysis

**URL:** https://huggingface.co/spaces/Adeel020/brains-n8n
**Workflow:** "Google Dorking Lead Scraper" (ID: `B8QU1MNXhRAXlRM8`)

---

## Current Workflow (6 Nodes)

```
Schedule Trigger ──→ Set Search Query ──→ SerpApi HTTP Request ──→ Parse & Clean (JS) ──→ Upsert to Supabase
Manual Trigger ────┘
```

### Node Breakdown

| Node | Type | What it does |
|------|------|-------------|
| **When clicking Execute** | Manual Trigger | For testing |
| **Schedule Trigger** | Schedule | Automation (interval, no timing set) |
| **Set Search Query** | Set | Hardcoded niche: **"fitness coach"**, query: `site:instagram.com "fitness coach" "DM for inquiries" -linktree -stan.store` |
| **SerpApi Google Search** | HTTP Request | Calls `serpapi.com/search.json` with your API key as query param |
| **Parse & Clean Leads** | Code (JS) | Extracts handle, cleans name, grabs email from bio |
| **Upsert to Supabase** | Supabase | Inserts/updates leads using the `supabaseApi` credential |

---

## Why the Workflow Failed (3 errors)

1. **Hardcoded niche** — only searches "fitness coach", ignores your 12 other niches
2. **Different query syntax** — uses `"DM for inquiries"` instead of `"DM to order" OR "WhatsApp"` — fewer results
3. **Hugging Face Space sleep** — Spaces go to sleep after inactivity, the HTTP request probably timed out
4. **SerpAPI rate limit** — same API key called from two places may have been exhausted

---

## The Good News

**Your local pipeline is already doing the scraping better.** Here's the comparison:

| Factor | n8n Workflow | Python Pipeline (local) |
|--------|-------------|----------------------|
| Niches searched | **1** (fitness coach) | **12** |
| Cities searched | None (blanket) | **4** (Lahore, Karachi, Islamabad, Pakistan) |
| Topic pill filter | Basic (only blocks p/reel/explore) | **Full** (blocks /popular/, topic_pill, utm_source, etc.) |
| Leads produced | **0** (all failed) | **21 in DB** ✅ |
| Filters | Minimal | Robust |

**Your DB already has 21 leads.** The n8n workflow was meant to scrape AND insert — but you can now **flip it around** to just read from Supabase and do outreach.

---

## Recommended: Rewire the Workflow

Instead of `Scrape → Insert`, change it to `Read → Process → Update`:

### New Workflow: "Outreach Engine"

```
Schedule Trigger (every 6h) 
        │
        ▼
Supabase: SELECT * FROM leads 
  WHERE outreach_status IS NULL 
     OR phone != 'Not Found'
        │
        ▼
IF phone != 'Not Found' ──→ Send WhatsApp/SMS
        │
        ▼
IF email != '' ──→ Send Email
        │
        ▼
Supabase: UPDATE leads 
  SET outreach_status = 'contacted', 
      outreach_date = NOW()
```

### Steps in n8n

1. **Keep the Schedule Trigger** — set to every 6 hours
2. **Replace Set Search Query** with a **Supabase Get Many** node:
   - Table: `leads`
   - Filter: `outreach_status` is `NULL` OR `outreach_status` = `''`
3. **Add IF node** — check if `phone != 'Not Found'`
4. **Add Email node** — Gmail/SMTP to send personalized outreach
5. **Add Supabase Update node** — mark lead as `contacted`

---

## Also: Update the Schedule Trigger

The current schedule is set to `interval: [{}]` which means it has no actual schedule configured — it won't run automatically. You need to set an actual interval (e.g. "Every 6 hours" or "Every day at 9 AM").
