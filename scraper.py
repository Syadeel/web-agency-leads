import requests
import re
import csv
import os
import time
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION
# ==========================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY not found in .env file")

NICHES = [
    "clothing brand",
    "home bakery",
    "consultant",
    "real estate agent",
    "restaurant",
    "fitness coach",
    "photographer",
    "makeup artist",
    "jewelry store",
    "ecommerce store",
    "digital agency",
    "gym"
]

CITIES = ["Lahore", "Karachi", "Islamabad", "Pakistan"]

# ==========================================
# REGEX PATTERNS
# ==========================================
# Matches Pakistani mobile numbers: +923001234567, 0300-1234567, 0300 1234567
PHONE_REGEX = r'(?:\+92|0)[3]\d{2}[-\s]?\d{7}'

def generate_queries():
    queries = []
    for niche in NICHES:
        for city in CITIES:
            # Dorking query: site:instagram.com "niche" "city" ("DM to order" OR "WhatsApp") -linktree -www
            query = f'site:instagram.com "{niche}" "{city}" ("DM to order" OR "WhatsApp") -linktree -www'
            queries.append(query)
    return queries

def try_fetch_serpapi(query):
    """Try SerpAPI first, return None if it fails."""
    print(f"[*] Searching: {query}")
    params = {
      "engine": "google",
      "q": query,
      "api_key": SERPAPI_KEY,
      "num": 100
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        response.raise_for_status()
        return response.json().get("organic_results", [])
    except Exception as e:
        print(f"[!] SerpAPI error: {e}")
        return None

def try_fetch_google_cse(query):
    """Fallback: try Google Custom Search (requires different API key)."""
    cse_key = os.getenv("GOOGLE_CSE_KEY", "")
    cse_cx = os.getenv("GOOGLE_CSE_CX", "")
    if not cse_key or not cse_cx:
        return []
    params = {"key": cse_key, "cx": cse_cx, "q": query, "num": 10}
    try:
        r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"[!] Google CSE error: {e}")
        return []

def fetch_search_results(query):
    """Fetch with SerpAPI, fallback to Google CSE."""
    results = try_fetch_serpapi(query)
    if results is not None:
        return results
    print("[*] Falling back to Google CSE...")
    return try_fetch_google_cse(query)

def is_topic_pill(link):
    """Detect Instagram topic pill / auto-generated pages — these are not real profiles."""
    skip_patterns = [
        "/popular/", "topic_pill", "?utm_source=",
        "instagram.com/explore/", "instagram.com/reels/",
        "instagram.com/directory/"
    ]
    return any(p in link for p in skip_patterns)

def is_valid_profile(link):
    """Only keep real Instagram profile URLs: instagram.com/username"""
    if not link or "instagram.com" not in link:
        return False
    if is_topic_pill(link):
        return False
    # Must be a profile: instagram.com/username (single path segment after domain)
    # Skip posts (/p/), reels (/reel/), stories (/stories/)
    skip_content = ["/p/", "/reel/", "/reels/", "/stories/", "/tv/"]
    if any(p in link for p in skip_content):
        return False
    return True

def extract_instagram_handle(link):
    """Extract Instagram username from profile URL."""
    match = re.search(r'instagram\.com/([^/?]+)', link)
    return match.group(1).lower() if match else "unknown"

def extract_lead_data(results, niche=""):
    leads = []
    seen_handles = set()
    
    for result in results:
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        
        # Skip topic pills and non-profile URLs
        if not is_valid_profile(link):
            continue
            
        # Extract Instagram handle
        handle = extract_instagram_handle(link)
        if not handle or handle in seen_handles:
            continue
        seen_handles.add(handle)
        
        # Extract Shop Name from Title (Usually format: "Name (@username) • Instagram photos...")
        shop_name = title.split("(@")[0].strip() if "(@" in title else title
        # Clean up IG suffix like "• Instagram photos and videos"
        shop_name = re.sub(r'\s*•\s*Instagram.*$', '', shop_name).strip()
        
        # Search for phone number in the snippet (bio preview)
        phone_match = re.search(PHONE_REGEX, snippet)
        phone_number = phone_match.group(0) if phone_match else "Not Found"
        
        leads.append({
            "Shop Name": shop_name,
            "Instagram Link": link,
            "Instagram Handle": handle,
            "Phone Number": phone_number,
            "Niche": niche,
            "Bio Snippet": snippet
        })
    return leads

def save_to_csv(leads, filename="leads.csv"):
    if not leads:
        print("[!] No leads found to save.")
        return
        
    keys = leads[0].keys()
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, "w", newline="", encoding="utf-8") as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(leads)
    
    print(f"[+] Saved {len(leads)} leads to {filepath}")

def main():
    if SERPAPI_KEY == "YOUR_SERPAPI_KEY_HERE":
        print("[!] PLEASE SET YOUR SERPAPI KEY IN THE SCRIPT BEFORE RUNNING.")
        return

    all_leads = []
    queries = generate_queries()
    
    for query in queries:
        # Extract niche and city from the query for metadata
        niche = [n for n in NICHES if n.lower().replace(" ", "") in query.lower().replace(" ", "")]
        niche_label = niche[0] if niche else "unknown"
        
        results = fetch_search_results(query)
        leads = extract_lead_data(results, niche=niche_label)
        all_leads.extend(leads)
        
        # Respect API rate limits
        time.sleep(1.5)
        
    # Remove duplicates based on Instagram link
    unique_leads = {lead["Instagram Link"]: lead for lead in all_leads}.values()
    
    save_to_csv(list(unique_leads))

if __name__ == "__main__":
    main()
