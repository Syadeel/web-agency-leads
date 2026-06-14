import json, urllib.request, csv, os, sys, re, random

# Middle East niches and cities
me_niches = [
    'arabic gold jewelry', 'perfume store', 'luxury clothing',
    'real estate agency', 'fitness coach', 'beauty salon',
    'interior design', 'photographer', 'event planner',
    'cafe', 'restaurant', 'organic products',
    'skincare clinic', 'hair salon', 'handicrafts',
    'fashion boutique', 'jewelry design', 'home decor',
    'digital marketing', 'wedding planner',
    'gym', 'yoga studio', 'spa', 'nail salon',
    'car rental', 'travel agency', 'hotel',
    'ecommerce', 'online store', 'dropshipping',
    'makeup artist', 'hair stylist', 'barber',
    'catering', 'bakery', 'dessert shop',
    'kids clothing', 'baby store', 'toy store',
    'electronics store', 'mobile shop', 'watch store',
    'furniture store', 'carpet store', 'lighting store'
]

me_cities = ['Dubai', 'Abu Dhabi', 'Riyadh', 'Jeddah', 'Doha', 'Kuwait City', 'Manama', 'Muscat', 'Sharjah', 'Ajman', 'Al Ain', 'Dammam', 'Khobar', 'Medina', 'Makkah', 'Salamiyah']

results = []
seen_handles = set()

# Load existing known handles
known_file = 'cached_known_handles.json'
if os.path.exists(known_file):
    with open(known_file) as f:
        known = json.load(f)
        if isinstance(known, list):
            for h in known:
                if h:
                    seen_handles.add(h.lower().strip().lstrip('@'))
    print(f'Loaded {len(seen_handles)} known handles')

random.shuffle(me_niches)

total_insta = 0
for i in range(min(30, len(me_niches))):
    niche = me_niches[i]
    city = random.choice(me_cities)
    
    query = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "WhatsApp" OR "+971" OR "+966" OR "+974")'
    
    body = json.dumps({
        'query': query,
        'search_depth': 'basic',
        'max_results': 10
    }).encode()
    
    req = urllib.request.Request(
        'https://api.tavily.com/search',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer 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'
        }
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        
        batch_insta = 0
        for item in data.get('results', []):
            url = item.get('url', '')
            content = item.get('content', '')
            title = item.get('title', '')
            
            hm = re.search(r'instagram\.com\/([a-zA-Z0-9_\.]+)', url)
            if not hm: continue
            handle = hm.group(1)
            
            skip = ['p','reel','reels','explore','stories','tv','popular','accounts']
            if handle.lower() in skip: continue
            if handle in seen_handles: continue
            if len(handle) < 3: continue
            
            batch_insta += 1
            seen_handles.add(handle)
            
            name = re.sub(r'\s*[•·]\s*Instagram.*$', '', title).strip() or handle
            
            phone = ''
            pm = re.search(r'(?:\+971|\+966|\+974|\+973|\+968|\+965|\+962|\+961)[-\s]?\d{1,4}[-\s]?\d{5,9}', content)
            if pm: phone = pm[0]
            if not phone:
                pm2 = re.search(r'(?:0|00)5\d{2,3}[-\s]?\d{3}[-\s]?\d{4}', content)
                if pm2: phone = pm2[0]
            
            em = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
            email = em.group(0) if em else ''
            
            fc = 0
            fm = re.search(r'([\d,]+)\s*(K|M|k|m)?\s*followers?', content)
            if fm:
                n = float(fm.group(1).replace(',',''))
                s = (fm.group(2) or '').upper()
                fc = int(n * (1000000 if s == 'M' else 1000 if s == 'K' else 1))
            
            if fc > 0 and fc < 20000: continue
            
            web = ''
            wm = re.search(r'https?:\/\/[^\s]+\.(com|pk|ai|io|org|net)[^\s]*', content)
            if wm and 'instagram.com' not in wm.group(0):
                web = re.split(r'[\s,)\\/]+', wm.group(0))[0]
            
            results.append({
                'Instagram Handle': handle,
                'Name': name,
                'Bio': content[:300],
                'Phone': phone,
                'Email': email,
                'Website': web,
                'Niche': niche,
                'City': city,
                'Market': 'Middle East',
                'Follower Count': fc
            })
        
        total_insta += batch_insta
        print(f'[{i+1}/15] {niche:30s} / {city:15s} -> {batch_insta:2d} insta profiles')
        
    except Exception as e:
        print(f'[{i+1}/15] {niche:30s} / {city:15s} -> ERROR: {str(e)[:80]}')

# Save results
path = 'leads_middleeast.csv'
if results:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Instagram Handle','Name','Bio','Phone','Email','Website','Niche','City','Market','Follower Count'])
        w.writeheader()
        w.writerows(results)
    print(f'\n=== SAVED {len(results)} Middle East leads to leads_middleeast.csv ===')
else:
    print('\n=== NO LEADS FOUND ===')

# Update handle cache
with open(known_file, 'w') as f:
    json.dump(list(seen_handles), f)
print(f'Handle cache: {len(seen_handles)} total')
