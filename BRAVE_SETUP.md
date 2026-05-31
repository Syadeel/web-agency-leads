# Brave Search API — Free 1,000 Searches/Month

Brave gives $5 in free credits/month = ~1,000 web searches.
Snippets are rich (emails, followers, city) — better than Google CSE.

## Setup (2 minutes)

1. Go to https://brave.com/search/api/
2. Click **"Get started"** → sign up with email
3. Once logged in, go to https://api-dashboard.search.brave.com/app/subscriptions
4. Choose **"Search"** plan ($0, free tier with $5 credits)
5. Go to https://api-dashboard.search.brave.com/app/api-keys
6. Click **"Create API Key"** → copy the key
7. Add to GitHub secrets:
   - Name: `BRAVE_API_KEY`
   - Value: the key you copied

## Priority

The scraper now uses:
1. **Brave API** (1,000/month) — PRIMARY, rich snippets
2. **SerpAPI** (250/month) — FALLBACK
3. **Google CSE** (100/day) — LAST RESORT
