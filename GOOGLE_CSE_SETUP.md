# Google Custom Search API — Free Daily Leads Setup

## 5-Minute Setup (completely free)

Google Custom Search gives you **100 free searches per day** = **3,000 searches/month**.
Compare to SerpAPI's 250/month. This is 12x more for free.

### Step 1: Get an API Key

1. Go to https://console.cloud.google.com/apis/credentials
2. Click **Create Credentials** → **API Key**
3. Copy the key that appears
4. (Optional but recommended) Click **Restrict Key** → enable **"Custom Search API"** only

### Step 2: Create a Custom Search Engine

1. Go to https://cse.google.com/cse/all
2. Click **Add**
3. Under **Sites to search**, type: `instagram.com/*`
4. Name it: `Instagram Lead Finder`
5. Click **Create**
6. On the next page, click **Get Search engine ID** (CX)
7. Copy the CX string (looks like: `123456789abcdef`)

### Step 3: Save to .env (local)

Add these to `F:\Anitgravity Data\web_agency_business\.env`:

```env
GOOGLE_CSE_API_KEY=AIzaSy...
GOOGLE_CSE_CX=123456789abcdef
```

### Step 4: Add to GitHub Secrets

1. Go to https://github.com/Syadeel/web-agency-leads/settings/secrets/actions
2. Add two new secrets:
   - `GOOGLE_CSE_API_KEY` = your API key
   - `GOOGLE_CSE_CX` = your search engine ID

### Done!

From now on, the scraper uses Google Custom Search first (100 free/day = 3,000/month) and only falls back to SerpAPI when needed. You'll get daily leads without hitting any limit.
