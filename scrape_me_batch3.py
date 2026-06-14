import json, urllib.request, csv, os, re, random

niches = [
    'gold shop','auto parts','bakery','nail salon','video production',
    'perfume','flowers','gifts','electronics','mobile accessories',
    'sports equipment','fishing gear','outdoor gear','toys','books',
    'furniture upholstery','curtains','carpets','kitchenware','tableware',
    'organic honey','dates','olive oil','incense','attar perfume'
]
cities = ['Dubai','Riyadh','Jeddah','Doha','Kuwait City','Manama','Muscat','Sharjah','Al Ain','Abu Dhabi','Ajman']

seen_handles = set()
known_file = 'cached_known_handles.json'
if os.path.exists(known_file):
    with open(known_file) as f:
        known = json.load(f)
        if isinstance(known, list):
            for h in known:
                if h:
                    seen_handles.add(h.lower().strip().lstrip('@'))

results = []
random.shuffle(niches)

for i in range(len(niches)):
    niche = niches[i]
    city = random.choice(cities)
    query = f'site:instagram.com "{niche}" "{city}" ("DM" OR "contact" OR "WhatsApp" OR "+971" OR "+966" OR "+974")'
    
    body = json.dumps({'query': query, 'search_depth': 'basic', 'max_results': 10}).encode()
    req = urllib.request.Request(
        'https://api.tavily.com/search', data=body,
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer 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'}
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        batch = 0
        for item in data.get('results', []):
            url = item.get('url', '')
            content = item.get('content', '')
            title = item.get('title', '')
            hm = re.search(r'instagram\.com\/([a-zA-Z0-9_\.]+)', url)
            if not hm:
                continue
            handle = hm.group(1)
            skip = ['p','reel','reels','explore','stories','tv','popular','accounts']
            if handle.lower() in skip:
                continue
            if handle in seen_handles:
                continue
            if len(handle) < 3:
                continue
            seen_handles.add(handle)
            batch += 1
            
            name = re.sub(r'\s*[•·]\s*Instagram.*$', '', title).strip() or handle
            
            phone = ''
            pm = re.search(r'(?:\+971|\+966|\+974|\+973|\+968|\+965|\+962|\+961)[-\s]?\d{1,4}[-\s]?\d{5,9}', content)
            if pm:
                phone = pm[0]
            
            email = ''
            em = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
            if em:
                email = em[0]
            
            fc = 0
            fm = re.search(r'([\d,]+)\s*(K|M|k|m)?\s*followers?', content)
            if fm:
                n = float(fm.group(1).replace(',', ''))
                s = (fm.group(2) or '').upper()
                fc = int(n * (1000000 if s == 'M' else 1000 if s == 'K' else 1))
            
            if fc > 0 and fc < 20000:
                continue
            
            web = ''
            wm = re.search(r'https?:\/\/[^\s]+\.(com|pk|ai|io|org|net)[^\s]*', content)
            if wm and 'instagram.com' not in wm.group(0):
                web = re.split(r'[\s,)\\/]+', wm.group(0))[0]
            
            results.append({
                'Instagram Handle': handle, 'Name': name, 'Bio': content[:300],
                'Phone': phone, 'Email': email, 'Website': web,
                'Niche': niche, 'City': city, 'Market': 'Middle East',
                'Follower Count': fc
            })
        
        print(f'[{i+1}/{len(niches)}] {niche:25s} / {city:15s} -> {batch:2d} leads')
    except Exception as e:
        print(f'[{i+1}/{len(niches)}] {niche:25s} / {city:15s} -> ERR: {str(e)[:60]}')

# Append to existing CSV
path = 'leads_middleeast.csv'
existing = {}
if os.path.exists(path):
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            existing[row['Instagram Handle'].lower().strip()] = row

new_count = 0
for r in results:
    h = r['Instagram Handle'].lower()
    if h not in existing:
        existing[h] = r
        new_count += 1

fieldnames = ['Instagram Handle','Name','Bio','Phone','Email','Website','Niche','City','Market','Follower Count']
with open(path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(existing.values())

print(f'\n=== Total: {len(existing)} leads (added {new_count} new to CSV) ===')

with open(known_file, 'w') as f:
    json.dump(list(seen_handles), f)
print(f'Cache: {len(seen_handles)} handles')
