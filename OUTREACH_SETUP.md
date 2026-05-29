# OS[Outreach Suit] Integration Plan

## Current State

The lead generation system now has a working pipeline:

```
scraper.py → leads.csv → load_leads_to_db.py → Supabase `leads` table → export_leads.py
```

### Leads Table Schema

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer (PK) | Auto-increment |
| `instagram_handle` | varchar | Unique — used for dedup |
| `name` | varchar | Business/shop name |
| `bio` | text | Instagram bio snippet |
| `email` | varchar | Currently empty (not scraped) |
| `phone` | varchar | Pakistani mobile number or "Not Found" |
| `niche` | varchar | E.g. "clothing brand", "restaurant" |
| `status` | varchar | Not yet used |
| `created_at` | timestamp | Auto-set on insert |

---

## The Bridge: Supabase DB as Central Hub

Since **n8n is not running locally** (port 5678 closed) and the only existing credential is a `supabaseApi` type for "Supabase account", the n8n workflow was clearly designed to pull from Supabase. The DB is the bridge.

**Architecture:**
```
[Scraper] → [Supabase leads table] → [n8n workflow (hosted elsewhere)] → [Outreach channels]
```

---

## Step 1: Find the n8n Instance

The n8n instance is hosted elsewhere (not on this machine). To find it:
1. Check the Supabase `settings` table for a `n8n.host` or `hostUrl` key
2. Check n8n's `workflow_entity` for any webhook URLs
3. Look for `webhook_entity` table — it may contain active webhook URLs that reveal the host
4. Check browser bookmarks or browser history

**Once found**, you can update the n8n workflow to:
- Listen for new rows in `leads` table (via Supabase trigger or polling)
- Process each lead through outreach stages

---

## Step 2: Add Outreach Columns to Leads Table

For cold outreach tracking, add these columns:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_date TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_notes TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS website VARCHAR(500);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS response VARCHAR(50) DEFAULT 'none';
```

**`outreach_status` values:** `pending` → `contacted` → `replied` → `converted` → `disqualified`

---

## Step 3: Choose Outreach Channels

### Option A: n8n Workflow (Recommended)
- **Pros**: Visual builder, retry logic, webhook support
- **Setup**: Once you locate the n8n URL, update the "Google Dorking Lead Scraper" workflow or create a new one
- **Nodes needed**: Supabase trigger → Email (SMTP) / WhatsApp / SMS

### Option B: Python Script (Direct)
- **Pros**: Run from local machine, no n8n dependency
- **Cons**: No visual workflow, manual scheduling
- **Quick start**: Can build a `outreach.py` script that:
  1. Reads leads with `outreach_status = 'pending'`
  2. Sends via SMTP (Gmail API or SendGrid)
  3. Updates lead status

### Option C: Use a SaaS Outreach Tool
- Connect Supabase directly to tools like **Lemlist**, **Instantly**, or **Smartlead**
- Export leads CSV and upload
- Most pragmatic for getting started fast

---

## Step 4: Recommended Cold Outreach Content

**SMS/WhatsApp Template for Pakistani Businesses:**
```
Hi [Name], I came across your Instagram page and love your work! 
We help local businesses in [City] grow their online presence with 
a professional website starting from Rs. XX,XXX. 
Would you be interested in a free consultation?
```

**Email Template:**
```
Subject: Helping [Shop Name] grow online

Hi [Name],

I saw your Instagram profile (@[handle]) and really like what 
you're doing with [niche].

We build professional websites for [niche] businesses in [City]. 
A simple landing page with contact info, gallery, and WhatsApp 
integration can help you get more customers.

Would you be open to a quick 10-min call this week?

Best,
[Your Name]
[Your Agency]
```

---

## Step 5: Roadmap

| Phase | Task | Priority |
|-------|------|----------|
| **Immediate** | Find n8n host URL | High |
| **Immediate** | Add outreach columns to leads table | High |
| **Week 1** | Build Python outreach script (SMTP/WhatsApp) | High |
| **Week 1** | Set up email sending (Gmail API / SendGrid) | High |
| **Week 2** | Enrich leads with website + email (manual or scraped) | Medium |
| **Week 2** | Set up n8n for auto-outreach on new leads | Medium |
| **Week 3** | Add response tracking and follow-up automation | Low |
| **Week 4** | Dashboard — lead pipeline + conversion tracking | Low |

---

## Immediate Next Action

Run this SQL in Supabase SQL editor to add outreach columns:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_date TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_notes TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS website VARCHAR(500);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS response VARCHAR(50) DEFAULT 'none';
```
