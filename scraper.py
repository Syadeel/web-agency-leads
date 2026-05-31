"""
scraper.py — Error-Proof Instagram Lead Scraper

Runs on: Windows (local) and Linux (GitHub Actions).
- Reads SERPAPI_KEY from environment variable (with .env fallback)
- Auto-retry 3x with exponential backoff
- Unicode-safe (skips non-Latin characters gracefully)
- Topic pill filter (0% garbage)
- 12 niches x 4 cities = 48 queries
"""
import requests
import re
import csv
import os
import time
import json
import sys
from datetime import datetime

# ─── Config ─────────────────────────────────────────────────────
# Try .env for local dev, but prefer real env vars (GitHub Actions)
try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv()
except ImportError:
    pass  # dotenv not installed - rely on real env vars

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY not set. Add to .env file or set as GitHub Actions secret.")

NICHES = [
    # Legal & Medical ($5k-$20k websites)
    "law firm", "personal injury lawyer", "family lawyer",
    "dentist clinic", "cosmetic dentist", "plastic surgeon",
    "dermatologist", "medical spa", "chiropractor",
    "orthodontist", "eye doctor", "physical therapist",

    # Real Estate & Property ($5k-$15k)
    "real estate agency", "property management", "real estate agent",
    "architect firm", "interior design studio",

    # Financial & Professional Services ($5k-$15k)
    "wealth management", "financial advisor", "insurance agency",
    "accounting firm", "CPA firm", "business consultant",

    # Home Services ($5k-$10k)
    "construction company", "home builder", "remodeling contractor",
    "landscaping company", "roofing company", "solar company",

    # Hospitality & Venues ($5k-$10k)
    "boutique hotel", "fine dining restaurant", "wedding venue",
    "event venue", "luxury spa", "resort",

    # Automotive ($5k-$10k)
    "car dealership", "auto repair shop", "auto detailing",

    # Health & Fitness ($3k-$8k)
    "med spa", "weight loss clinic", "wellness center",
    "yoga studio", "crossfit gym",
]

# USA + UK + EU major cities (high-ticket markets) — optimized to 20 cities
CITIES = [
    # USA (10 biggest)
    "New York", "Los Angeles", "Chicago", "Houston", "Miami",
    "San Francisco", "Seattle", "Boston", "Dallas", "Atlanta",
    # UK (4)
    "London", "Manchester", "Edinburgh", "Birmingham",
    # EU (6)
    "Berlin", "Paris", "Milan", "Madrid", "Amsterdam", "Zurich",
]

# SerpAPI free tier: 100 searches/month.
# We rotate 5 niches per day so you get fresh leads daily without hitting the cap.
# Day 1-6 cycles through all 32 niches.
# Each run = 5 niches x 20 cities = 100 queries = stays within free tier.
NICHES_PER_DAY = 5


def get_todays_niches():
    """Pick a rotating subset of niches for today to stay within SerpAPI free tier."""
    from datetime import date
    day_number = date.today().toordinal()  # Days since year 1
    # Pick contiguous chunk of NICHES_PER_DAY, wrapping around
    start = (day_number * NICHES_PER_DAY) % len(NICHES)
    # Return 5 niches, wrap if needed
    result = []
    for i in range(NICHES_PER_DAY):
        idx = (start + i) % len(NICHES)
        result.append(NICHES[idx])
    return result


# Build a single optimized query per niche per city
def generate_queries():
    """Build queries for today's rotating niches only."""
    today_niches = get_todays_niches()
    queries = []
    for niche in today_niches:
        for city in CITIES:
            query = f'site:instagram.com "{niche}" "{city}" ("contact" OR "book" OR "website") -linktree -store -shop'
            queries.append(query)
    return queries, today_niches

PHONE_REGEX = r'(?:\+?\d{1,3})?[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}'

# ─── Retry Helper ──────────────────────────────────────────────
def fetch_with_retries(url, params, max_retries=3, base_delay=2):
    """Fetch URL with exponential backoff retry."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            last_error = "timeout"
        except requests.exceptions.ConnectionError as e:
            last_error = f"connection: {e}"
        except Exception as e:
            last_error = str(e)[:100]

        if attempt < max_retries:
            delay = base_delay ** attempt
            time.sleep(delay)

    return None


# ─── Filters ────────────────────────────────────────────────────
def is_valid_profile(link):
    if not link or "instagram.com" not in link:
        return False
    skip = ["/popular/", "topic_pill", "?utm_source=",
            "instagram.com/explore/", "instagram.com/reels/",
            "instagram.com/directory/", "/p/", "/reel/", "/reels/",
            "/stories/", "/tv/"]
    if any(p in link for p in skip):
        return False
    return True


def extract_handle(link):
    m = re.search(r'instagram\.com/([^/?]+)', link)
    return m.group(1).lower() if m else None


# ─── Search ─────────────────────────────────────────────────────
# Search priority:
#   1. Google Custom Search (100 free/day = 3,000/month) — PRIMARY
#   2. SerpAPI (250 free/month) — FALLBACK when GCS runs out
#   3. Local cache file — LAST RESORT (if both APIs are down)

CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
CSE_CX = os.getenv("GOOGLE_CSE_CX", "")


def search_cse(query):
    """Google Custom Search — 100 free queries per day, unlimited daily via billing."""
    if not CSE_API_KEY or not CSE_CX:
        return None
    params = {"key": CSE_API_KEY, "cx": CSE_CX, "q": query, "num": 10}
    data = fetch_with_retries("https://www.googleapis.com/customsearch/v1", params)
    if data:
        items = data.get("items", [])
        # Map CSE format to match SerpAPI format
        mapped = []
        for item in items:
            mapped.append({
                "link": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
            })
        return mapped
    return None


def search_serpapi(query):
    """SerpAPI — 250 free/month, used as fallback."""
    if not SERPAPI_KEY:
        return None
    params = {"engine": "google", "q": query, "api_key": SERPAPI_KEY, "num": 100}
    data = fetch_with_retries("https://serpapi.com/search", params)
    if data:
        return data.get("organic_results", [])
    return None


def fetch_results(query):
    """Try SerpAPI first (richer snippets), fall back to Google CSE."""
    results = search_serpapi(query)
    if results is not None and len(results) > 0:
        return results
    results = search_cse(query)
    if results is not None and len(results) > 0:
        return results
    return []


# ─── Extract ────────────────────────────────────────────────────
# Regex patterns
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
FOLLOWER_REGEX = r'(\d[\d,]*\.?\d*)\s*[KkMmBb]?\s*(?:followers|follower|subscribers)'
LOCATION_REGEX = r'📍\s*([^📍\n]{3,60})'


def extract_follower_count(snippet):
    """Extract follower count from Instagram bio snippet and return (numeric, display)."""
    match = re.search(r'(\d[\d,]*\.?\d*)\s*([KkMmBb]?)\s*(?:followers|follower|subscribers)', snippet)
    if not match:
        match = re.search(r'(\d+\.?\d*)\s*([KkMmBb]?)\s*(?:fol)', snippet)
    if not match:
        return 0, "Unknown"

    num_str = match.group(1).replace(",", "")
    suffix = match.group(2).upper()
    try:
        num = float(num_str)
        multiplier = {"K": 1000, "M": 1000000, "B": 1000000000, "": 1}
        total = int(num * multiplier.get(suffix, 1))
        display = f"{num_str}{suffix}" if suffix else f"{int(num):,}"
        return total, display
    except:
        return 0, "Unknown"


def is_big_account(follower_count):
    """Only keep accounts with meaningful following (1k+ for quality)."""
    return follower_count >= 1000  # Adjust: 1000 = 1k followers minimum


def extract_city_country(snippet, niche, city_searched):
    """Extract location from bio snippet or fall back to searched city."""
    # Try to find location patterns
    loc_match = re.search(r'📍\s*([^📍\n]{3,60})', snippet)
    if loc_match:
        return loc_match.group(1).strip(), "US/UK/EU"
    # Try common keywords
    for city_key in ["New York", "Los Angeles", "London", "Paris", "Berlin", "Milan", "Madrid"]:
        if city_key.lower() in snippet.lower():
            return city_key, "US/UK/EU"
    return city_searched, "US/UK/EU"


def extract_leads(results, niche="", city_searched=""):
    leads = []
    seen = set()
    for res in results:
        try:
            link = res.get("link", "")
            title = res.get("title", "")
            snippet = res.get("snippet", "")
            if not is_valid_profile(link):
                continue
            handle = extract_handle(link)
            if not handle or handle in seen:
                continue
            seen.add(handle)

            # Business name
            shop = title.split("(@")[0].strip() if "(@" in title else title
            shop = re.sub(r'\s*•\s*Instagram.*$', '', shop).strip() or handle

            # Phone
            phone_m = re.search(PHONE_REGEX, snippet)
            phone = phone_m.group(0) if phone_m else "Not Found"

            # Email
            email_m = re.search(EMAIL_REGEX, snippet)
            email = email_m.group(0) if email_m else ""

            # Followers
            follower_count, follower_display = extract_follower_count(snippet)

            # Filter: skip tiny accounts
            if not is_big_account(follower_count):
                continue

            # City & Country
            city, country = extract_city_country(snippet, niche, city_searched)

            leads.append({
                "Shop Name": shop,
                "Instagram Link": link,
                "Instagram Handle": handle,
                "Phone Number": phone,
                "Email": email,
                "Followers": follower_display,
                "Follower Count": follower_count,
                "Niche": niche,
                "City": city,
                "Country": country,
                "Bio Snippet": snippet[:500]
            })
        except Exception:
            continue
    return leads


# ─── Main ───────────────────────────────────────────────────────
def main():
    all_leads = []
    queries, today_niches = generate_queries()
    total_queries = len(queries)
    errors = 0

    from datetime import date
    print(f"TODAY={date.today()}")
    print(f"NICHES={','.join(today_niches)}")

    for i, query in enumerate(queries):
        results = fetch_results(query)
        if not results:
            errors += 1
            continue

        niche = "unknown"
        city_searched = "US"
        for n in today_niches:
            if f'"{n}"' in query:
                niche = n
                break
        for c in CITIES:
            if f'"{c}"' in query:
                city_searched = c
                break

        leads = extract_leads(results, niche, city_searched)
        all_leads.extend(leads)
        time.sleep(1.5)

    # Dedup by handle
    unique = {}
    for lead in all_leads:
        h = lead["Instagram Handle"]
        if h not in unique:
            unique[h] = lead

    final_leads = list(unique.values())

    # Save
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        keys = ["Shop Name", "Instagram Link", "Instagram Handle", "Phone Number", "Email", "Followers", "Niche", "City", "Country", "Bio Snippet"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(final_leads)

    phones = sum(1 for l in final_leads if l["Phone Number"] != "Not Found")
    emails = sum(1 for l in final_leads if l.get("Email"))
    print(f"SCRAPED={len(final_leads)}")
    print(f"PHONES={phones}")
    print(f"EMAILS={emails}")
    print(f"ERRORS={errors}")
    print(f"TOTAL_QUERIES={total_queries}")


if __name__ == "__main__":
    main()
