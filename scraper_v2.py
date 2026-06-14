# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
scraper_v2.py - Enhanced Instagram Lead Scraper v2 (AHS FIXED — COST-FREE)

Runs on: Local PC + GitHub Actions
API Rotation: CSE (100/day) → Brave (1k/mo) → SerpAPI (250/mo)

FIXED in this version:
- API rotation and quota tracking to NEVER run out of free tier
- CSE used first (daily reset) to preserve monthly Brave/SerpAPI budgets
- Quota tracker saves/loads from quota_cache.json
- Instagram enrichment: uses instagram_lookup v3 (instagrapi + snippet fallback)
- Market split: half queries for local (Pakistan), half for international
- Proper snippet extraction for follower counts
- Better error handling for all APIs
"""

import requests, re, csv, os, time, json, sys
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Config ─────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

# ─── Quota Tracker (cost-free rotation) ─────────────────────────
QUOTA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quota_cache.json")

def load_quota():
    if os.path.exists(QUOTA_FILE):
        try:
            with open(QUOTA_FILE) as f:
                return json.load(f)
        except: pass
    return {
        "brave": {"used": 0, "limit": 1000, "period": "monthly", "note": "$5 free credits = 1000 calls at $5/1000 (Search plan)", "updated": None},
        "serpapi": {"used": 0, "limit": 250, "period": "monthly", "updated": None},
        "cse": {"used": 0, "limit": 100, "period": "daily", "updated": None},
        "total_calls": 0,
        "last_reset": None
    }

def save_quota(q):
    q["last_reset"] = datetime.now(timezone.utc).isoformat()
    with open(QUOTA_FILE, "w") as f:
        json.dump(q, f, indent=2)

def reset_quota_if_needed(q):
    now = datetime.now(timezone.utc)
    for api, info in q.items():
        if not isinstance(info, dict): continue
        last_str = info.get("updated")
        if not last_str: continue
        last = datetime.fromisoformat(last_str)
        if info.get("period") == "daily" and (now - last).days >= 1:
            info["used"] = 0
            info["updated"] = now.isoformat()
        elif info.get("period") == "monthly" and (now - last).days >= 28:
            info["used"] = 0
            info["updated"] = now.isoformat()

def count_call(api_key):
    """Record one API call in quota cache."""
    q = load_quota()
    reset_quota_if_needed(q)
    api_map = {"brave": "brave", "serpapi": "serpapi", "cse": "cse"}
    key = api_map.get(api_key, api_key.lower())
    if key in q and isinstance(q[key], dict):
        q[key]["used"] = q[key].get("used", 0) + 1
        q[key]["updated"] = datetime.now(timezone.utc).isoformat()
    q["total_calls"] = q.get("total_calls", 0) + 1
    save_quota(q)

def get_remaining(api_key):
    """Get remaining calls for an API."""
    q = load_quota()
    reset_quota_if_needed(q)
    key_map = {"brave": "brave", "serpapi": "serpapi", "cse": "cse"}
    key = key_map.get(api_key, api_key.lower())
    info = q.get(key, {"used": 0, "limit": 0})
    return info["limit"] - info["used"]

def print_quota_status():
    """Print the current quota status for all APIs."""
    q = load_quota()
    reset_quota_if_needed(q)
    print("\n  ─── API Quota Status ───")
    # Display quota status
    q = load_quota()
    print(f"  {'Brave':12s}: {max(0, q.get('brave', {}).get('limit', 0) - q.get('brave', {}).get('used', 0)):>4d} remaining")
    b_remaining = q.get('brave', {}).get('used', 0)
    est_spend = round(b_remaining * 0.005, 2)
    remaining_dollars = round(5.00 - est_spend, 2)
    print(f"  {'Spend':12s}: ${remaining_dollars:.2f} / $5.00 free credits left ({est_spend:.2f} used)")
    print(f"  Total API calls: {q.get('total_calls', 0)}")

# ─── Niches ─────────────────────────────────────────────────────

INTL_NICHES = [
    # ─── SERVICE BUSINESSES (high website need) ──────────────────
    "fitness coach", "life coach", "business coach", "executive coach",
    "career coach", "health coach", "relationship coach", "leadership coach",
    "online course creator", "digital marketing agency", "seo agency",
    "social media agency", "pr agency", "creative agency",
    "web design agency", "branding agency", "advertising agency",
    "video production", "content creator", "copywriter", "ghostwriter",
    "public speaker", "consultant", "business consultant",

    # ─── MEDICAL & DENTAL ─────────────────────────────────────────
    "dentist clinic", "orthodontist", "cosmetic dentist",
    "plastic surgeon", "dermatologist", "med spa",
    "weight loss clinic", "hormone clinic", "anti aging clinic",
    "laser hair removal", "skin care clinic",

    # ─── LEGAL ───────────────────────────────────────────────────
    "law firm", "immigration lawyer", "personal injury lawyer",
    "family lawyer", "real estate attorney", "criminal defense lawyer",
    "corporate lawyer", "estate planning",

    # ─── REAL ESTATE & CONSTRUCTION ──────────────────────────────
    "real estate agency", "real estate agent", "property management",
    "architect firm", "interior design", "interior decorator",
    "construction company", "general contractor", "remodeling contractor",
    "home builder", "landscaping", "pool builder",

    # ─── FINANCIAL ──────────────────────────────────────────────
    "wealth management", "financial advisor", "financial planner",
    "tax consultant", "accountant", "cpa", "bookkeeping service",
    "insurance agency", "mortgage broker", "investment advisor",

    # ─── FOOD & HOSPITALITY ─────────────────────────────────────
    "boutique hotel", "fine dining", "wedding venue",
    "restaurant", "cafe", "bakery", "catering business",
    "food truck", "brewery", "winery", "meal prep service",

    # ─── WELLNESS & BEAUTY ──────────────────────────────────────
    "luxury spa", "wellness center", "yoga studio",
    "personal trainer", "nutritionist", "pilates studio",
    "meditation center", "cryotherapy", "iv therapy clinic",
    "makeup artist", "hair stylist", "barber shop",
    "nail salon", "lash studio", "tattoo studio",

    # ─── CREATIVE PROFESSIONALS ─────────────────────────────────
    "photographer", "videographer", "wedding photographer",
    "portrait photographer", "real estate photographer",
    "event planner", "wedding planner", "party planner",
    "graphic designer", "fashion designer", "jewelry designer",

    # ─── HOME SERVICES ─────────────────────────────────────────
    "cleaning service", "pest control", "hvac contractor",
    "plumber", "electrician", "roofing contractor",
    "painting contractor", "flooring contractor", "moving company",
    "lawn care service", "window cleaning",

    # ─── EDUCATION & ARTS ──────────────────────────────────────
    "music school", "dance studio", "art school",
    "tutoring service", "test prep", "language school",
    "cooking class", "pottery studio", "fitness studio",
    "martial arts studio", "swimming school",

    # ─── RETAIL & ECOMMERCE ────────────────────────────────────
    "boutique", "clothing brand", "jewelry store",
    "furniture store", "home decor", "gift shop",
    "flower shop", "pet store", "toy store",
    "bookstore", "record store", "vintage shop",
    "organic grocery", "farmers market",

    # ─── AUTOMOTIVE ──────────────────────────────────────────────
    "car dealership", "auto repair", "detailing service",
    "car wrap", "tire shop", "auto body shop",

    # ─── PETS ───────────────────────────────────────────────────
    "pet grooming", "dog training", "pet sitting",
    "veterinary clinic", "pet boutique",

    # ─── OTHER PROFITABLE ──────────────────────────────────────
    "travel agency", "event venue", "escape room",
    "axe throwing", "virtual reality arcade",
    "coworking space", "photography studio",
    "massage therapy", "acupuncture", "chiropractor",
    "physical therapy", "speech therapy", "occupational therapy",
]

INTL_CITIES = [
    # ─── USA (ALL 50 STATES - MAJOR CITIES) ─────────────────────
    # Northeast
    "New York", "Boston", "Philadelphia", "Washington DC",
    "Baltimore", "Pittsburgh", "Buffalo", "Rochester",
    # Southeast
    "Miami", "Atlanta", "Orlando", "Tampa", "Charlotte",
    "Nashville", "Jacksonville", "Raleigh", "Richmond",
    "Birmingham", "Charleston", "Memphis", "Louisville",
    # Midwest
    "Chicago", "Detroit", "Indianapolis", "Columbus",
    "Cincinnati", "Cleveland", "Kansas City", "St. Louis",
    "Milwaukee", "Minneapolis", "Des Moines", "Omaha",
    # South Central
    "Houston", "Dallas", "San Antonio", "Austin",
    "Fort Worth", "Oklahoma City", "Tulsa", "New Orleans",
    # Mountain
    "Denver", "Phoenix", "Las Vegas", "Salt Lake City",
    "Albuquerque", "Boise", "Colorado Springs",
    # West Coast
    "Los Angeles", "San Francisco", "San Diego", "Seattle",
    "Portland", "Sacramento", "San Jose", "Oakland",
    "Orange County", "Long Beach", "Fresno",
    # Pacific
    "Honolulu", "Anchorage",

    # ─── UK (ALL MAJOR CITIES) ──────────────────────────────────
    "London", "Manchester", "Birmingham", "Leeds",
    "Glasgow", "Liverpool", "Edinburgh", "Bristol",
    "Cardiff", "Belfast", "Newcastle", "Nottingham",
    "Sheffield", "Leicester", "Southampton", "Portsmouth",
    "Brighton", "Oxford", "Cambridge", "York",
    "Aberdeen", "Dundee", "Coventry", "Hull",
    "Stoke-on-Trent", "Wolverhampton", "Plymouth",
    "Derby", "Northampton", "Norwich", "Swansea",

    # ─── EU (MAJOR CITIES) ─────────────────────────────────────
    # Germany
    "Berlin", "Munich", "Hamburg", "Frankfurt",
    "Cologne", "Stuttgart", "Dusseldorf", "Leipzig",
    "Dresden", "Nuremberg", "Hannover", "Bremen",
    # France
    "Paris", "Lyon", "Marseille", "Toulouse",
    "Nice", "Bordeaux", "Lille", "Strasbourg",
    "Montpellier", "Nantes", "Rennes",
    # Italy
    "Milan", "Rome", "Naples", "Turin",
    "Florence", "Bologna", "Venice", "Verona",
    # Spain
    "Madrid", "Barcelona", "Valencia", "Seville",
    "Malaga", "Bilbao", "Palma", "Zaragoza",
    # Netherlands
    "Amsterdam", "Rotterdam", "The Hague", "Utrecht",
    "Eindhoven", "Groningen",
    # Belgium
    "Brussels", "Antwerp", "Ghent", "Bruges",
    # Switzerland
    "Zurich", "Geneva", "Basel", "Bern", "Lausanne",
    # Sweden
    "Stockholm", "Gothenburg", "Malmo", "Uppsala",
    # Denmark
    "Copenhagen", "Aarhus", "Odense",
    # Norway
    "Oslo", "Bergen", "Stavanger",
    # Finland
    "Helsinki", "Tampere", "Turku",
    # Austria
    "Vienna", "Salzburg", "Innsbruck", "Graz",
    # Ireland
    "Dublin", "Cork", "Galway", "Limerick",
    # Portugal
    "Lisbon", "Porto", "Faro", "Braga",
    # Poland
    "Warsaw", "Krakow", "Wroclaw", "Gdansk",
    "Poznan", "Lodz", "Katowice",
    # Czech Republic
    "Prague", "Brno", "Ostrava",
    # Other EU
    "Budapest", "Vienna", "Athens", "Luxembourg",
    "Monaco", "Reykjavik", "Tallinn", "Riga",
    "Vilnius", "Bratislava", "Ljubljana", "Zagreb",
    "Helsinki", "Oslo", "Stockholm", "Copenhagen",
    "Dublin", "Lisbon", "Madrid", "Barcelona",
    "Rome", "Milan", "Berlin", "Munich",
    "Amsterdam", "Brussels", "Zurich", "Vienna",
    "Prague", "Budapest", "Warsaw", "Athens",
]

# ─── REMOVE DUPLICATES ──────────────────────────────────────────
# Deduplicate while preserving order
_seen = set()
INTL_NICHES = [x for x in INTL_NICHES if not (x.lower() in _seen or _seen.add(x.lower()))]
_seen = set()
INTL_CITIES = [x for x in INTL_CITIES if not (x.lower() in _seen or _seen.add(x.lower()))]

PAKISTANI_NICHES = [
    # 👗 FASHION & CLOTHING (high priority)
    "clothing brand", "designer wear", "embroidered dresses",
    "boutique", "pret wear", "unstitched dress",
    "wedding dress", "bridal wear", "traditional wear",
    "kids clothing", "baby clothes", "party wear",
    "winter collection", "summer collection",

    # 💍 JEWELRY & ACCESSORIES (high priority)
    "jewelry store", "gold jewelry", "fashion jewelry",
    "bridal jewelry", "handmade jewelry", "perfume shop",
    "bags shop", "shoe store", "watch store",

    # 💄 BEAUTY & COSMETICS
    "makeup artist", "cosmetics shop", "skincare brand",
    "beauty salon", "nail art", "hair stylist",

    # 🏠 HOME & LIFESTYLE
    "home decor", "furniture store", "luxury furniture",
    "kitchenware", "home textile", "cushion covers",

    # 🍰 FOOD & DINING
    "bakeries", "dessert shop", "fine dining",
    "cafe", "restaurant", "chaat house",

    # 💪 HEALTH & FITNESS
    "fitness coach", "weight loss clinic", "wellness center",
    "yoga studio", "nutritionist",

    # 📦 OTHER PROFITABLE
    "organic products", "gift shop", "handicrafts",
    "party decorations", "leather goods", "toy store",
    "stationery shop", "flower shop",
]

PAKISTANI_CITIES = [
    "Karachi", "Lahore", "Islamabad", "Faisalabad",
    "Rawalpindi", "Multan", "Hyderabad", "Peshawar",
    "Quetta", "Sialkot", "Gujranwala", "Gujrat",
    "Sargodha", "Bahawalpur", "Sahiwal", "Nawabshah",
    "Mardan", "Abbottabad", "Murree", "Sukkur",
    "Sheikhupura", "Jhelum", "Rahim Yar Khan",
]

# ─── MIDDLE EAST ─────────────────────────────────────────────────
MIDDLE_EAST_NICHES = [
    # 👗 LUXURY FASHION
    "luxury boutique", "designer brand", "gold jewelry",
    "fashion boutique", "abaya store", "hijab fashion",
    "luxury watches", "handbags", "high heels",

    # 💍 JEWELRY & GOLD
    "gold shop", "diamond jewelry", "luxury jewelry",
    "arabic gold", "bridal jewelry",

    # 👃 PERFUMES & BEAUTY
    "perfume brand", "oud perfume", "arabic perfume",
    "makeup artist", "beauty clinic", "skincare clinic",
    "hair salon", "laser hair removal", "cosmetic clinic",

    # 🏠 REAL ESTATE & LUXURY
    "real estate agency", "luxury real estate", "property developer",
    "interior design", "luxury furniture", "home decor",

    # 🚗 LUXURY AUTOMOTIVE
    "luxury cars", "car dealership", "supercar rental",
    "car detailing", "luxury auto",

    # 🍽️ FINE DINING & HOSPITALITY
    "fine dining", "luxury restaurant", "cafe",
    "hotel", "resort", "spa",

    # 💪 FITNESS & WELLNESS
    "fitness coach", "personal trainer", "weight loss clinic",
    "yoga studio", "wellness center",

    # 📸 PHOTOGRAPHY & EVENTS
    "photographer", "wedding planner", "event planner",
    "photo studio", "videographer",
]

MIDDLE_EAST_CITIES = [
    # UAE
    "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah",
    "Fujairah", "Umm Al Quwain",
    # Saudi Arabia
    "Riyadh", "Jeddah", "Dammam", "Khobar", "Mecca", "Medina",
    "Tabuk", "Abha", "Al Khobar",
    # Qatar
    "Doha", "Al Wakrah", "Al Khor",
    # Kuwait
    "Kuwait City", "Hawalli", "Salmiya",
    # Oman
    "Muscat", "Salalah", "Sohar",
    # Bahrain
    "Manama", "Muharraq", "Riffa",
    # Turkey (business hub for ME)
    "Istanbul", "Ankara", "Izmir", "Antalya",
]

QUERIES_PER_RUN = 6
# Split across 3 markets: 2 Pakistan + 2 Middle East + 2 International

def get_pakistan_queries():
    return 1

def get_intl_queries():
    return 2

def get_middle_east_queries():
    return 3

MIN_FOLLOWERS = 20000

# ─── Fresh Leads Cache (filter known handles BEFORE search) ─────
KNOWN_HANDLES_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_handles.json")
QUERY_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "query_history.json")

class FreshLeadsCache:
    """Persistent set of all Instagram handles ever found.
    Syncs with Google Sheet on startup, filters at search time.
    """
    def __init__(self):
        self.handles = set()
        self.load()
    
    def load(self):
        if os.path.exists(KNOWN_HANDLES_CACHE):
            try:
                with open(KNOWN_HANDLES_CACHE) as f:
                    data = json.load(f)
                    self.handles = set(data.get("handles", []))
                    print(f"\n  [Cache] Loaded {len(self.handles)} known handles")
            except: 
                self.handles = set()
    
    def save(self):
        with open(KNOWN_HANDLES_CACHE, "w") as f:
            json.dump({"handles": sorted(self.handles), "updated": datetime.now(timezone.utc).isoformat()}, f, indent=2)
    
    def sync_from_sheet(self):
        """Pull handles from Google Sheet so we never re-find them."""
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            import concurrent.futures
            creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_sheets_creds.json")
            if os.path.exists(creds_path):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    fut = ex.submit(self._do_sync, creds_path)
                    fut.result(timeout=15)  # 15 second max
        except Exception as e:
            print(f"  [Cache] Sheet sync skipped ({e})")
    
    def _do_sync(self, creds_path):
        from google.oauth2.service_account import Credentials
        import gspread
        creds = Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key("1zeyBwZLkJJSnPjikzmbpEX6rvOF6IBCCMGNHQ85re0c")
        for ws in sh.worksheets():
            vals = ws.get_all_values()
            for row in vals[1:]:
                if len(row) > 3 and row[3].strip():
                    self.handles.add(row[3].strip().lower())
        self.save()
        print(f"  [Cache] Synced from sheet: {len(self.handles)} total known handles")
    
    def is_known(self, handle):
        return handle.lower().strip() in self.handles
    
    def add(self, handle):
        self.handles.add(handle.lower().strip())
    
    def __len__(self):
        return len(self.handles)

class QueryHistory:
    """Tracks which (niche, city, market) combos were searched.
    Never repeats the same combo within 7 days.
    """
    def __init__(self):
        self.history = {}  # key: "niche|city|market" -> date string
        self.load()
    
    def load(self):
        if os.path.exists(QUERY_HISTORY_FILE):
            try:
                with open(QUERY_HISTORY_FILE) as f:
                    self.history = json.load(f)
            except: 
                self.history = {}
    
    def save(self):
        with open(QUERY_HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def was_searched_recently(self, niche, city, market, days=7):
        key = f"{niche.lower().strip()}|{city.lower().strip()}|{market.lower().strip()}"
        if key not in self.history:
            return False
        last = datetime.fromisoformat(self.history[key]).date()
        return (date.today() - last).days < days
    
    def mark_searched(self, niche, city, market):
        key = f"{niche.lower().strip()}|{city.lower().strip()}|{market.lower().strip()}"
        self.history[key] = date.today().isoformat()
        self.save()
    
    def get_fresh_niches(self, niches, cities, market, count, days=7):
        """Return (niche, city) pairs that haven't been searched recently."""
        import random
        random.shuffle(niches)
        result = []
        tried_cities = set()
        for niche in niches:
            available = [c for c in cities if not self.was_searched_recently(niche, c, market, days)]
            if not available:
                # All cities searched for this niche — reset freshness
                available = cities
            city = random.choice(available)
            result.append((niche, city))
            tried_cities.add(city)
            if len(result) >= count:
                break
        # If we couldn't find enough fresh combos, allow repeats but log it
        if len(result) < count:
            remaining = count - len(result)
            extra = random.sample([(random.choice(niches), random.choice(cities)) for _ in range(remaining)], remaining)
            result.extend(extra)
        return result

# ─── Filters ────────────────────────────────────────────────────

def is_valid_profile(link, snippet=""):
    """Check if a search result can yield a usable Instagram handle.
    Accepts both Instagram URLs and web pages that mention Instagram handles.
    """
    if not link:
        return False
    
    # Direct Instagram profile link
    if "instagram.com" in link:
        skip = ["/popular/", "topic_pill", "?utm_source=",
                "instagram.com/explore/", "instagram.com/reels/",
                "instagram.com/directory/", "/p/", "/reel/", "/reels/",
                "/stories/", "/tv/"]
        if any(p in link for p in skip):
            return False
        return True
    
    # Non-Instagram page that mentions an Instagram handle
    # Will extract handle from snippet
    if snippet and re.search(r'@?[a-zA-Z]\w{2,29}', snippet):
        return True
    
    return False

def extract_handle(link, snippet=""):
    """Extract Instagram handle from link or snippet."""
    # Direct link extraction
    m = re.search(r'instagram\.com/([^/?]+)', link)
    if m:
        return m.group(1).lower()
    # Snippet extraction (for non-Instagram pages)
    if snippet:
        m = re.search(r'@?([a-zA-Z]\w{2,29})', snippet)
        if m:
            return m.group(1).lower().lstrip("@")
    return None

PHONE_REGEX = r'(?:\+?\d{1,3})?[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}'
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# ─── Search APIs ───────────────────────────────────────────────

def fetch_with_retries(url, params, max_retries=2, headers=None):
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=25)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception:
            return None
    return None

def search_brave(query):
    """Brave Search API (1000 free/month — MONTHLY backup)."""
    if not BRAVE_API_KEY:
        return None
    if get_remaining("brave") <= 0:
        print("    [!] Brave quota exhausted this month")
        return None
    params = {"q": query, "count": 10, "safesearch": "off"}
    headers = {
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept": "application/json",
    }
    data = fetch_with_retries(
        "https://api.search.brave.com/res/v1/web/search",
        params, headers=headers
    )
    if data:
        count_call("brave")
        if "web" in data and data["web"].get("results"):
            return [
                {"link": r.get("url",""), "title": r.get("title",""),
                 "snippet": r.get("description","")}
                for r in data["web"]["results"]
            ]
    print("    [!] Brave returned no results")
    return None

def search_serpapi(query):
    """SerpAPI (250 free/month — MONTHLY backup)."""
    if not SERPAPI_KEY:
        return None
    if get_remaining("serpapi") <= 0:
        print("    [!] SerpAPI quota exhausted this month")
        return None
    data = fetch_with_retries("https://serpapi.com/search", {
        "engine": "google", "q": query,
        "api_key": SERPAPI_KEY, "num": 100
    })
    if data:
        count_call("serpapi")
        return data.get("organic_results", [])
    return None

def search_cse(query):
    """Google CSE (100 free/day — DAILY PRIMARY, resets every day)."""
    if not CSE_API_KEY or not CSE_CX:
        return None
    if get_remaining("cse") <= 0:
        print("    [!] CSE quota exhausted for today (resets daily)")
        return None
    data = fetch_with_retries(
        "https://www.googleapis.com/customsearch/v1", {
            "key": CSE_API_KEY, "cx": CSE_CX, "q": query, "num": 10
        }
    )
    if data:
        count_call("cse")
        return [
            {"link": i.get("link",""), "title": i.get("title",""),
             "snippet": i.get("snippet","")}
            for i in data.get("items", [])
        ]
    return None

def fetch_results(query):
    """
    Try APIs in rotation: Brave ($5/mo, $5/1000 calls) is the ONLY working API.
    
    SerpAPI: Exhausted (0/250 this month, resets July).
    Google CSE: Google restricted access — API shows 'Enabled' but returns 403.
    """
    apis = [
        ("Brave", search_brave),  # $5/1000 = $0.005/call with free $5 credit
    ]
    for name, fn in apis:
        try:
            results = fn(query)
            if results and len(results) > 0:
                return results
        except Exception as e:
            continue
    return []

# ─── Query Generation ──────────────────────────────────────────

def build_intl_queries(count=5, qh=None):
    """Build international queries (US/UK/EU only — excludes India)."""
    import random
    if qh:
        pairs = qh.get_fresh_niches(INTL_NICHES, INTL_CITIES, "intl", count)
        queries = []
        for niche, city in pairs:
            q = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "book" OR "link") -linktree -shop -store -India'
            queries.append((q, niche, city, "intl"))
        return queries
    niches = random.sample(INTL_NICHES, min(count, len(INTL_NICHES)))
    queries = []
    for niche in niches:
        city = random.choice(INTL_CITIES)
        q = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "book" OR "link") -linktree -shop -store -India'
        queries.append((q, niche, city, "intl"))
    return queries

def build_pakistani_queries(count=5, qh=None):
    """Build Pakistani market queries (Pakistan only — excludes India)."""
    import random
    if qh:
        pairs = qh.get_fresh_niches(PAKISTANI_NICHES, PAKISTANI_CITIES, "pakistan", count)
        queries = []
        for niche, city in pairs:
            q = f'site:instagram.com "{niche}" "{city}" ("030" OR "031" OR "+92" OR "WhatsApp") Pakistan -India'
            queries.append((q, niche, city, "pakistan"))
        return queries
    niches = random.sample(PAKISTANI_NICHES, min(count, len(PAKISTANI_NICHES)))
    queries = []
    for niche in niches:
        city = random.choice(PAKISTANI_CITIES)
        q = f'site:instagram.com "{niche}" "{city}" ("030" OR "031" OR "+92" OR "WhatsApp") Pakistan -India'
        queries.append((q, niche, city, "pakistan"))
    return queries

def build_middle_east_queries(count=2, qh=None):
    """Build Middle East market queries (UAE, KSA, Qatar, Kuwait, Oman, Bahrain, etc.)."""
    import random
    if qh:
        pairs = qh.get_fresh_niches(MIDDLE_EAST_NICHES, MIDDLE_EAST_CITIES, "middleeast", count)
        queries = []
        for niche, city in pairs:
            q = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "book" OR "link" OR "واتساب" OR "+971" OR "+966") -linktree'
            queries.append((q, niche, city, "middleeast"))
        return queries
    niches = random.sample(MIDDLE_EAST_NICHES, min(count, len(MIDDLE_EAST_NICHES)))
    queries = []
    for niche in niches:
        city = random.choice(MIDDLE_EAST_CITIES)
        q = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "book" OR "واتساب" OR "+971" OR "+966") -linktree'
        queries.append((q, niche, city, "middleeast"))
    return queries

# ─── Enrichment ─────────────────────────────────────────────────

# Instagram follower count via HTTP (lightweight, no login)
FOLLOWER_CACHE = {}
def fetch_instagram_followers(handle):
    """Fetch real follower count from Instagram's public profile page.
    Uses a fast HTTP request with minimal timeout — returns 0 on failure.
    """
    if handle in FOLLOWER_CACHE:
        return FOLLOWER_CACHE[handle]
    
    try:
        url = f"https://www.instagram.com/{handle}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        }
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        
        if r.status_code == 200:
            html = r.text
            
            # Method 1: og:description meta tag
            # <meta property="og:description" content="X Followers, Y Following, Z Posts" />
            m = re.search(r'(\d[\d,]*\.?\d*)\s*(?:[KkMmBb]?\s*)?Follower', html)
            if m:
                raw = m.group(1).replace(",", "")
                # Convert if it has K/M suffix nearby
                context = html[m.start():m.start()+50]
                suffix_m = re.search(rf'{re.escape(m.group(1))}\s*([KkMmBb])', context)
                if suffix_m:
                    s = suffix_m.group(1).upper()
                    mult = {"K": 1000, "M": 1000000, "B": 1000000000}
                    count = int(float(raw) * mult.get(s, 1))
                else:
                    count = int(float(raw))
                
                FOLLOWER_CACHE[handle] = count
                return count
            
            # Method 2: JSON-LD interactionStatistic
            # {"userInteractionCount": "X"}
            jm = re.search(r'"userInteractionCount"\s*:\s*"(\d+)"', html)
            if jm:
                count = int(jm.group(1))
                FOLLOWER_CACHE[handle] = count
                return count
            
            # Method 3: window.__INITIAL_STATE__ JSON
            im = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
            if im:
                import json as _json
                try:
                    data = _json.loads(im.group(1))
                    # Navigate to follower count in the complex JSON structure
                    edge = data.get("data", {}).get("user", {})
                    if edge:
                        count = edge.get("edge_followed_by", {}).get("count", 0)
                        if count > 0:
                            FOLLOWER_CACHE[handle] = count
                            return count
                except:
                    pass
    
    except requests.exceptions.RequestException:
        pass
    except Exception:
        pass
    
    FOLLOWER_CACHE[handle] = 0
    return 0

# Updated: import from instagram_lookup v3 (snippet fallback + instagrapi)
try:
    from instagram_lookup import enrich_profile as lookup_enrich
except ImportError:
    def lookup_enrich(handle, snippet="", session_path=None):
        # Minimal fallback
        return {"handle": handle, "follower_count": 0, "source": "none"}

SESSION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "instagram_session.json"
)

# ─── Lead Processing ───────────────────────────────────────────

def process_lead(res, niche, city_searched, market, known_cache=None):
    """Process a single search result into a lead record with enrichment.
    Skips known handles immediately — no wasted API calls.
    """
    link = res.get("link", "")
    snippet = res.get("snippet", "") or res.get("title", "")

    if not is_valid_profile(link, snippet):
        return None

    handle = extract_handle(link, snippet)
    if not handle:
        return None

    # SKIP known handles BEFORE any enrichment — saves API quota
    if known_cache and known_cache.is_known(handle):
        return None

    title = res.get("title", "")
    shop = title.split("(@")[0].strip() if "(@" in title else title
    shop = re.sub(r'\s*•\s*Instagram.*$', '', shop).strip() or handle

    phone_m = re.search(PHONE_REGEX, snippet)
    phone = phone_m.group(0) if phone_m else ""

    email_m = re.search(EMAIL_REGEX, snippet)
    email = email_m.group(0) if email_m else ""

    # Enrich using instagram_lookup (snippet mode by default, instagrapi if session exists)
    # Timeout: max 10 seconds to avoid hanging on Instagram rate limits
    enriched = {"handle": handle, "follower_count": 0, "source": "none"}
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(lookup_enrich, handle, snippet, SESSION_PATH)
            enriched = future.result(timeout=10)
    except TimeoutError:
        print(f"    [!] Enrichment timeout for {handle}")
    except Exception:
        pass

    follower_count = enriched.get("follower_count", 0)
    engagement_quality = enriched.get("engagement_quality", "unknown")
    website_status = enriched.get("website_status", "unknown")
    external_url = enriched.get("external_url", "")

    # Also try extracting follower count from snippet if enrichment returned 0
    if follower_count == 0 and snippet:
        fm = re.search(r'(\d[\d,]*\.?\d*)\s*([KkMmBb]?)\s*(?:followers|follower)', snippet)
        if fm:
            num_str = fm.group(1).replace(",", "")
            suffix = fm.group(2).upper()
            try:
                num = float(num_str)
                multiplier = {"K": 1000, "M": 1000000, "B": 1000000000}
                follower_count = int(num * multiplier.get(suffix, 1))
            except ValueError:
                pass
    
    # If still 0, try Instagram HTTP lookup (lightweight, no login)
    if follower_count == 0:
        follower_count = fetch_instagram_followers(handle)
        if follower_count > 0:
            print(f"    [IG] {handle}: {follower_count:,} followers")

    # FILTERS
    if follower_count < MIN_FOLLOWERS:
        return None  # below threshold OR unknown (0) — reject
    
    # Exclude Indian leads (phone prefix +91, .in domains, Indian cities)
    if phone and phone.strip().startswith("+91"):
        return None
    if external_url and external_url.strip().endswith(".in"):
        return None
    city_lower = (enriched.get("location") or city_searched or "").lower()
    indian_cities = {"mumbai", "delhi", "bangalore", "bengaluru", "chennai", "kolkata",
                     "hyderabad", "pune", "ahmedabad", "jaipur", "lucknow", "india"}
    if city_lower in indian_cities:
        return None

    if website_status == "has_site":
        return None

    if engagement_quality == "low":
        return None

    return {
        "Date": date.today().isoformat(),
        "Market": market,
        "Shop Name": shop,
        "Instagram Handle": handle,
        "Instagram Link": link,
        "Phone": phone,
        "Email": email,
        "Follower Count": follower_count,
        "Niche": niche,
        "City": enriched.get("location") or city_searched,
        "Country": "Pakistan" if market == "pakistan" else "UAE/KSA/Qatar" if market == "middleeast" else "US/UK/EU",
        "Website Status": website_status,
        "External URL": external_url,
        "Engagement Quality": engagement_quality,
        "Full Name": enriched.get("full_name", ""),
        "Bio Snippet": snippet[:300],
        "Lead Status": "new",
    }

def fmt(n):
    if isinstance(n, (int, float)):
        return f"{int(n):,}"
    return str(n)

# ─── Main ──────────────────────────────────────────────────────

def main(markets=None):
    """
    markets: list of 'intl', 'pakistan', or None for both
    Split: Pakistan gets 7 queries, International gets 3 (Pakistani focus)
    """
    if markets is None:
        markets = ["intl", "pakistan"]

    # ─── Initialize fresh-leads cache ─────────────────────────
    known_cache = FreshLeadsCache()
    known_cache.sync_from_sheet()
    qh = QueryHistory()
    
    print(f"\n  Known handles: {len(known_cache)} (will skip these in search results)")
    print(f"  Fresh query combos available: checking...")
    
    # Count available fresh queries for each market
    market_niches = {"intl": INTL_NICHES, "pakistan": PAKISTANI_NICHES, "middleeast": MIDDLE_EAST_NICHES}
    market_cities = {"intl": INTL_CITIES, "pakistan": PAKISTANI_CITIES, "middleeast": MIDDLE_EAST_CITIES}
    for m in markets:
        niches = market_niches.get(m, INTL_NICHES)
        cities = market_cities.get(m, INTL_CITIES)
        fresh = sum(1 for n in niches for c in cities if not qh.was_searched_recently(n, c, m, 7))
        print(f"    {m.title()}: {fresh} fresh niche+city combos available")

    all_queries = []
    query_counts = []
    pak_q = get_pakistan_queries()
    intl_q = get_intl_queries()
    me_q = get_middle_east_queries()
    if "pakistan" in markets:
        pak_queries = build_pakistani_queries(pak_q, qh)
        all_queries.extend(pak_queries)
        query_counts.append(f"Pakistan: {len(pak_queries)}")
    if "intl" in markets:
        intl_queries = build_intl_queries(intl_q, qh)
        all_queries.extend(intl_queries)
        query_counts.append(f"Intl: {len(intl_queries)}")
    if "middleeast" in markets:
        me_queries = build_middle_east_queries(me_q, qh)
        all_queries.extend(me_queries)
        query_counts.append(f"Middle East: {len(me_queries)}")

    all_leads = []
    seen_handles = set()
    errors = 0

    print(f"{'='*60}")
    print(f"SCRAPER V2  |  {date.today()}")
    print(f"Markets: {', '.join(query_counts)}")
    print(f"Min Followers: {MIN_FOLLOWERS:,}")
    print(f"{'='*60}")

    for i, (query, niche, city, market) in enumerate(all_queries):
        print(f"\n  [{i+1}/{len(all_queries)}] {market.upper()} | {niche} | {city}")
        print(f"    Q: {query[:80]}...")

        results = fetch_results(query)
        if not results:
            errors += 1
            print(f"    [!] No results")
            continue

        print(f"    [+] {len(results)} raw results")
        print(f"    [Cache] {sum(1 for r in results if known_cache.is_known(extract_handle(r.get('link',''), r.get('snippet','') or r.get('title','')) or ''))} already known — skipping")

        found = 0
        for res in results:
            try:
                lead = process_lead(res, niche, city, market, known_cache)
                if lead and lead["Instagram Handle"] not in seen_handles:
                    seen_handles.add(lead["Instagram Handle"])
                    known_cache.add(lead["Instagram Handle"])
                    all_leads.append(lead)
                    found += 1
            except Exception:
                continue
        
        # Mark this query as searched so we don't repeat it this week
        qh.mark_searched(niche, city, market)
        qh.save()

        print(f"    → {found} leads after filtering")

        time.sleep(1.5)

    # ─── Save results ──────────────────────────────────────────
    keys = [
        "Date", "Market", "Shop Name", "Instagram Handle", "Instagram Link",
        "Phone", "Email", "Follower Count", "Niche", "City", "Country",
        "Website Status", "External URL", "Engagement Quality",
        "Full Name", "Bio Snippet", "Lead Status"
    ]

    output_dir = os.path.dirname(os.path.abspath(__file__))

    # Save combined
    csv_path = os.path.join(output_dir, "leads_v2.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(all_leads)

    # Save per market
    for market in markets:
        market_leads = [l for l in all_leads if l["Market"] == market]
        if market_leads:
            suffix = market  # "pakistan", "intl", or "middleeast"
            mp = os.path.join(output_dir, f"leads_{suffix}.csv")
            with open(mp, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(market_leads)

    # Push to Google Sheets if service account is configured
    if "--csv-only" not in sys.argv:
        try:
            from google_sheets import append_leads
            for m in markets:
                print(f"\n  Pushing {m} leads to Google Sheets...")
                append_leads(m)
        except Exception as e:
            print(f"\n  [!] Google Sheets push skipped: {e}")
            print(f"  [!] Set up service account: python google_sheets.py --setup")
    else:
        print("\n  [--csv-only] Skipping Google Sheets push")
    
    # Save updated known handles cache
    known_cache.save()

    phones = sum(1 for l in all_leads if l.get("Phone"))
    emails = sum(1 for l in all_leads if l.get("Email"))
    no_site = sum(1 for l in all_leads if l.get("Website Status") == "no_site")
    high_q = sum(1 for l in all_leads if l.get("Engagement Quality") == "high")

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Total Leads: {len(all_leads)}")
    for market in markets:
        count = sum(1 for l in all_leads if l["Market"] == market)
        print(f"  {market.title()}: {count}")
    print(f"  With Phones: {phones}")
    print(f"  With Emails: {emails}")
    print(f"  No Website: {no_site}")
    print(f"  High Quality: {high_q}")
    print(f"  Saved to: {csv_path}")
    print(f"\n  Per-market files: leads_intl.csv, leads_pakistan.csv, leads_middleeast.csv")
    print(f"{'='*60}")

    return all_leads


if __name__ == "__main__":
    import sys
    # Filter out flags, keep only market names
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    markets = args if args else ["intl", "pakistan", "middleeast"]
    main(markets)
