# OS[Outreach Suit] Integration Plan

## Current State

The lead generation system now has a working pipeline:

```
scraper.py → leads.csv → load_leads_to_db.py → Supabase `leads` table → export_leads.py
```

**Pipeline status:** ✅ Full run completed. **22 leads scraped, 21 in DB.** 5 with phone numbers. Spans 12 niches.

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
| `follower_count` | integer | From enrichment |
| `follower_display` | varchar | Formatted follower display |
| `has_website` | boolean | Website presence flag |
| `website_status` | varchar | Website status |
| `website_url` | varchar | Business website |
| `business_type` | varchar | Type classification |
| `city` | varchar | Location |
| `country` | varchar | Country |
| `priority` | varchar | Lead priority |
| `enriched_at` | timestamptz | Last enrichment time |

---

## n8n on Hugging Face — Connection Guide

Your n8n is deployed on **Hugging Face Spaces**. Each Space gets a URL like `https://{username}-{space-name}.hf.space/`.

### How to Find Your n8n URL

1. Log in to [huggingface.co](https://huggingface.co)
2. Go to your profile → **Spaces**
3. Click on your n8n Space (the one linked to your Supabase)
4. Your n8n URL is displayed at the top of the Space page
5. It should look like: `https://yourusername-n8n.hf.space/`

> **Tip:** The Supabase credentials in your `.env` are the same ones your n8n Hugging Face Space uses. Your n8n Space's environment variables should have:
> - `DB_POSTGRESDB_HOST` = `aws-1-us-east-1.pooler.supabase.com`
> - `DB_POSTGRESDB_PORT` = `6543`
> - `DB_POSTGRESDB_USER` = `postgres.hrzyuchlqihbdllbcxlh`
> - `DB_POSTGRESDB_PASSWORD` = *your Supabase password*
> - `N8N_ENCRYPTION_KEY` = base64 random string

### n8n Hugging Face Limitations

| Factor | Limit |
|--------|-------|
| RAM | 16 GB (free tier) |
| CPU | 2 vCPU |
| Disk | 50 GB (non-persistent — DB must be external Supabase) |
| Sleep | Space sleeps after inactivity — wakes on HTTP request |
| Custom domain | Not supported on free tier (use `hf.space` subdomain) |

### Architecture

```
[Local Machine]                          [Hugging Face Cloud]
                                     ┌─────────────────────┐
scraper.py ────────┐                 │   n8n Instance       │
                   │                 │   (Hugging Face      │
load_leads_to_    ─┼─→ Supabase DB ──→    Space)            │
db.py              │   (PostgreSQL)  │   ┌───────────────┐  │
                   │                 │   │ Workflow:      │  │
export_leads.py ───┘                 │   │ Lead Scraper   │──┼──→ Email / WhatsApp
                                     │   └───────────────┘  │
                                     └─────────────────────┘
```

---

## Step 1: Connect n8n to Supabase and Fix Workflow

The existing "Google Dorking Lead Scraper" workflow (ID: `B8QU1MNXhRAXlRM8`) has 3 failed executions. Since n8n is on Hugging Face:

1. Open your n8n URL in a browser
2. Check the workflow execution logs for error details
3. Likely cause: The workflow had hardcoded credentials that expired or the HTTP node config was wrong
4. Create a new workflow (or fix the existing one) with these nodes:

**New workflow suggestion — "Process New Leads":**
- **Trigger:** Webhook (HTTP POST) OR Schedule (every hour)
- **Node 1:** Supabase — `SELECT * FROM leads WHERE status IS NULL OR status = ''`
- **Node 2:** IF phone != "Not Found" → SMS/WhatsApp branch
- **Node 3:** IF email NOT NULL → Email branch
- **Node 4:** Update lead `status = 'contacted'` in Supabase

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

## 24/7 Keep-Alive: Prevent Cold-Start Errors Forever

Hugging Face Spaces sleep after ~30 minutes of inactivity. When the Space is asleep, the n8n workflow times out on execution — that's what caused your 3 previous errors.

**A local `keep_alive.py` won't work** because it stops when your laptop goes to sleep. The solution is a **cloud-based ping** that runs 24/7 regardless of your laptop.

### Option A: GitHub Actions (Recommended) — FREE, 24/7

This runs on GitHub's servers every 5 minutes forever. Zero cost, zero setup once pushed.

**How to activate:**

1. Push this repo to GitHub
2. GitHub will automatically find `.github/workflows/keep-alive.yml` and start running it
3. That's it — no config, no secrets, no API keys

The workflow pings `https://Adeel020-brains-n8n.hf.space/healthz` every 5 minutes.

To push to GitHub:
```bash
# One-time setup
gh repo create web-agency-leads --public --source=. --remote=origin --push
# OR manually:
git remote add origin https://github.com/YOUR_USERNAME/web-agency-leads.git
git push -u origin master
```

### Option B: cron-job.org (Easier, no GitHub needed)

For a simpler solution that doesn't need GitHub:

1. Go to [cron-job.org](https://cron-job.org) and sign up (free)
2. Click **Create Cronjob**
3. Enter:
   - **Title:** `n8n Keep-Alive`
   - **URL:** `https://Adeel020-brains-n8n.hf.space/healthz`
   - **Execution interval:** Every 5 minutes
   - **Save**
4. Done. cron-job.org will ping your n8n Space from their servers every 5 minutes, 24/7

### Option C: UptimeRobot (Monitor + Keep-Alive)

1. Go to [UptimeRobot.com](https://uptimerobot.com) and sign up (free, 50 monitors)
2. Click **Add New Monitor**
3. Set type to **HTTP(s)**
4. URL: `https://Adeel020-brains-n8n.hf.space/healthz`
5. Interval: 5 minutes
6. Save

This also alerts you if n8n goes down.

### Why This Fixes the 3 Previous Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Exec #1: 21:53 - error (2s) | Space cold-start, request timed out | Keep-alive pings every 5 min → Space never sleeps |
| Exec #2: 22:01 - error (0.15s) | Cold-start again | Same fix |
| Exec #3: 22:37 - error (0.22s) | Cold-start again | Same fix |

The 3 executions all ran within ~45 minutes of each other, and each failed in under 2 seconds — classic Hugging Face cold-start behavior. Once keep-alive is running, the Space stays warm and workflows execute instantly.

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
