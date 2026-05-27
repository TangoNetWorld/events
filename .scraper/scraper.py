import os
import requests
from bs4 import BeautifulSoup
import json
import time
import unicodedata
import re
import datetime
from difflib import SequenceMatcher
import urllib.parse


HOY_EMAIL = os.environ.get('HOY_MILONGA_EMAIL')
HOY_PASSWORD = os.environ.get('HOY_MILONGA_PASSWORD')

coord_cache = {}
url_resolve_cache = {}

months_map = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def clean_text(text):
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.replace("–", "-").replace("—", "-").strip()


def get_coordinates(city, country):
    if not city or not country:
        return None, None
    query = f"{city}, {country}"
    if query in coord_cache:
        return coord_cache[query]
    try:
        time.sleep(1)
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
        headers = {'User-Agent': 'TangoGlobeScraper/1.0'}
        response = requests.get(url, headers=headers).json()
        if response:
            lat = float(response[0]['lat'])
            lon = float(response[0]['lon'])
            coord_cache[query] = (lat, lon)
            return lat, lon
    except Exception as e:
        print(f"Koordinat bulunamadı ({query}):", e)
    coord_cache[query] = (None, None)
    return None, None


def get_country_from_gps(lat, lon):
    if not lat or not lon:
        return ""
    try:
        time.sleep(1)
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
        res = requests.get(url, headers={'User-Agent': 'TangoGlobeScraper/1.0'}, timeout=10).json()
        if res and 'address' in res:
            return res['address'].get('country', '')
    except Exception:
        pass
    return ""


def resolve_tangopolix_external_url(tangopolix_url):
    if not tangopolix_url:
        return ""
    if tangopolix_url in url_resolve_cache:
        return url_resolve_cache[tangopolix_url]
    try:
        time.sleep(1)
        response = requests.get(tangopolix_url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return tangopolix_url
        soup = BeautifulSoup(response.text, 'html.parser')
        dt_el = soup.find('dt', string=lambda s: s and "event's website" in s.lower().strip())
        if dt_el:
            dd_el = dt_el.find_next('dd')
            if dd_el:
                actual_url = dd_el.text.strip()
                url_resolve_cache[tangopolix_url] = actual_url
                return actual_url
    except Exception as e:
        print(f"Tangopolix dış linki çözülemedi ({tangopolix_url}):", e)
    return tangopolix_url


def resolve_tangocat_url(relative_url):
    if not relative_url:
        return ""
    if relative_url.startswith("http") and "tangocat.net" not in relative_url:
        return relative_url
    full_redirect_url = "https://tangocat.net" + relative_url if relative_url.startswith("/") else relative_url
    if full_redirect_url in url_resolve_cache:
        return url_resolve_cache[full_redirect_url]
    try:
        response = requests.head(full_redirect_url, allow_redirects=True, timeout=5)
        real_url = response.url
        url_resolve_cache[full_redirect_url] = real_url
        return real_url
    except Exception as e:
        try:
            response = requests.get(full_redirect_url, allow_redirects=True, timeout=5, stream=True)
            real_url = response.url
            url_resolve_cache[full_redirect_url] = real_url
            return real_url
        except Exception as e2:
            print(f"Link çözülemedi ({full_redirect_url}):", e2)
            return full_redirect_url


def parse_tango_dates(date_str):
    if not date_str:
        return "", ""
    date_str = date_str.replace(",", " ").replace("\xa0", " ").strip()
    years = re.findall(r'\b(20\d{2})\b', date_str)
    year_found = False
    if years:
        year = int(years[0])
        year_found = True
        date_str = re.sub(r'\b20\d{2}\b', '', date_str).strip()
    else:
        year = datetime.datetime.now().year
    date_str = date_str.replace("–", "-").replace("—", "-")
    parts = [p.strip() for p in date_str.split('-') if p.strip()]

    def get_month_and_day(part):
        words = re.findall(r'[a-zA-Z]+', part)
        numbers = re.findall(r'\d+', part)
        month = None
        day = None
        if words:
            month_word = words[0].lower()
            if month_word in months_map:
                month = months_map[month_word]
        if numbers:
            day = int(numbers[0])
        return month, day

    start_year = year
    end_year = year
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        start_month, start_day = get_month_and_day(parts[0])
        end_month, end_day = start_month, start_day
    else:
        start_month, start_day = get_month_and_day(parts[0])
        end_month, end_day = get_month_and_day(parts[1])
        if end_month is None:
            end_month = start_month
        if start_month is None:
            start_month = end_month
        if start_month and end_month and start_month > end_month:
            if year_found:
                start_year = year - 1
                end_year = year
            else:
                start_year = year
                end_year = year + 1

    start_date_str = ""
    if start_month and start_day:
        start_date_str = f"{start_year:04d}-{start_month:02d}-{start_day:02d}"
    end_date_str = ""
    if end_month and end_day:
        end_date_str = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"
    return start_date_str, end_date_str


def parse_enjoy_en_date(date_str, year):
    if not date_str:
        return ""
    try:
        clean_str = date_str.lower().strip()
        month_match = re.search(r'([a-zA-Z]+)', clean_str)
        day_match = re.search(r'(\d+)', clean_str)
        if month_match and day_match:
            month_word = month_match.group(1)
            day_num = int(day_match.group(1))
            month_num = months_map.get(month_word, 1)
            return f"{year:04d}-{month_num:02d}-{day_num:02d}"
    except Exception:
        pass
    return ""


def parse_enjoy_location_text(location_text):
    city = ""
    country = ""
    if not location_text:
        return city, country
    if "｜" in location_text:
        eng_part = location_text.split("｜")[-1].strip()
    elif "|" in location_text:
        eng_part = location_text.split("|")[-1].strip()
    else:
        eng_part = location_text.strip()
    parts = [p.strip() for p in eng_part.split(',')]
    if len(parts) >= 2:
        city = parts[0]
        country = parts[1]
    elif len(parts) == 1:
        city = parts[0]
        country = parts[0]
    return city, country


def scrape_enjoy_tango():
    print("\n--- Enjoy Tango taranıyor ---")
    current_year = datetime.datetime.now().year
    current_timestamp_ms = int(time.time() * 1000)
    api_url = f"https://enjoytango.com/app/api/event_list.php?tid=2&date={current_year}&t={current_timestamp_ms}"
    
    headers = {
        'User-Agent': HEADERS['User-Agent'],
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://enjoytango.com/app/list.php?tid=2&city=',
    }
    events = []
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        raw_events = response.json()
        for item in raw_events:
            title = clean_text(item.get('title', ''))
            if not title:
                continue
            evt_timestamp = item.get('evtdate')
            year = current_year
            start_date = ""
            if evt_timestamp:
                start_dt = datetime.datetime.fromtimestamp(evt_timestamp / 1000)
                start_date = start_dt.strftime('%Y-%m-%d')
                year = start_dt.year
            else:
                start_date = parse_enjoy_en_date(item.get('timefrom_en'), year)
            timeto_en = item.get('timeto_en')
            end_date = parse_enjoy_en_date(timeto_en, year) if timeto_en else start_date
            
            city, country = parse_enjoy_location_text(item.get('city', ''))
            lat = float(item.get('latitude')) if item.get('latitude') else None
            lon = float(item.get('longitude')) if item.get('longitude') else None
            
            event_url = item.get('website', '').strip()
            if not event_url or not event_url.startswith('http'):
                relative_url = item.get('arcurl', '')
                event_url = "https://enjoytango.com" + relative_url if relative_url else f"https://enjoytango.com/app/show.php?aid={item.get('id')}"
            
            events.append({
                "eventName": title,
                "startDate": start_date,
                "endDate": end_date,
                "city": city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "eventUrl": event_url,
            })
            print(f"İşlendi (Enjoy Tango): {title} ({start_date})")
    except Exception as e:
        print("Enjoy Tango taranırken hata oluştu:", e)
    return events


def login_to_hoy_milonga(session, email, password):
    if not email or not password or "@ornek.com" in email:
        print("[!] Giriş bilgileri tanımlanmadığı için misafir olarak devam ediliyor.")
        return False
    login_page_url = "https://hoy-milonga.com/buenos-aires/en/login"
    login_api_url = "https://hoy-milonga.com/guideAPI/web/2.0/loginUser"
    try:
        session.get(login_page_url, headers=HEADERS, timeout=10)
        payload_dict = {"userID": email, "password": password, "langCode": "en"}
        payload = {"objFromClientAsString": json.dumps(payload_dict)}
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://hoy-milonga.com/buenos-aires/en/login',
        }
        response = session.post(login_api_url, data=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            api_response = response.json()
            user_data = api_response.get('result', {}).get('data', {})
            user_id = user_data.get('HMUserID')
            access_token = user_data.get('HMAccessToken')
            if user_id and access_token:
                cookie_data = {
                    "HMUserID": int(user_id),
                    "HMAccessToken": str(access_token),
                    "said": 1,
                    "userLangCode": "en",
                    "userCurrCode": None
                }
                compact_json = json.dumps(cookie_data, separators=(',', ':'))
                encoded_cookie_value = urllib.parse.quote(compact_json)
                session.cookies.set('HMC', encoded_cookie_value, domain='hoy-milonga.com', path='/')
                session.headers.update({'HMUserID': str(user_id), 'HMAccessToken': str(access_token)})
                print("[+] Hoy Milonga girişi başarılı. Kilitler açıldı.")
                return True
    except Exception as e:
        print("[HATA] Hoy Milonga otomatik girişi başarısız:", e)
    return False


def parse_hoy_date(date_str):
    if not date_str:
        return ""
    try:
        clean_str = date_str.lower().replace(',', ' ').replace('\n', ' ').strip()
        parts = clean_str.split()
        year_num = None
        for part in parts:
            if part.isdigit() and len(part) == 4 and part.startswith('20'):
                year_num = int(part)
                break
        if not year_num:
            year_num = datetime.datetime.now().year
        month_num = None
        for part in parts:
            part_short = part[:3]
            if part_short in months_map:
                month_num = months_map[part_short]
                break
        day_num = None
        for part in parts:
            if part.isdigit() and len(part) <= 2:
                day_num = int(part)
                break
        if month_num and day_num:
            return f"{year_num:04d}-{month_num:02d}-{day_num:02d}"
    except Exception:
        pass
    return ""


def extract_hoy_dates_from_text(text):
    if not text:
        return "", ""
    text = text.replace('\n', ' ').strip()
    match_range = re.search(r'From\s+(.*?)\s+to\s+(.*)', text, re.IGNORECASE)
    if match_range:
        start_raw = match_range.group(1)
        end_raw = match_range.group(2)
        return parse_hoy_date(start_raw), parse_hoy_date(end_raw)
    single_date = parse_hoy_date(text)
    return single_date, single_date


def parse_hoy_detail(session, detail_url):
    try:
        time.sleep(1)
        response = session.get(detail_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        title_el = soup.find('h1')
        title = clean_text(title_el.text) if title_el else ""
        lat, lon = None, None
        directions_link = soup.find('a', id='entity-header-directions')
        if directions_link and directions_link.has_attr('href'):
            href = directions_link['href']
            coords_match = re.search(r'daddr=([-\d.]+)\s*,\s*([-\d.]+)', href)
            if coords_match:
                lat = float(coords_match.group(1))
                lon = float(coords_match.group(2))
        country = get_country_from_gps(lat, lon)
        event_url = ""
        fb_link = soup.find('a', id='contact-options-facebook')
        ig_link = soup.find('a', id='contact-options-instagram')
        wa_link = soup.find('a', id='contact-options-whatsapp')
        if fb_link and fb_link.has_attr('href'):
            event_url = fb_link['href']
        elif ig_link and ig_link.has_attr('href'):
            event_url = ig_link['href']
        elif wa_link and wa_link.has_attr('href'):
            event_url = wa_link['href']
        else:
            event_url = detail_url
        return {"eventName": title, "latitude": lat, "longitude": lon, "country": country, "eventUrl": event_url}
    except Exception:
        return None


def scrape_hoy_milonga():
    print("\n--- Hoy Milonga taranıyor ---")
    base_url = "https://hoy-milonga.com"
    list_url = "https://hoy-milonga.com/buenos-aires/en/encuentros"
    session = requests.Session()
    login_to_hoy_milonga(session, HOY_EMAIL, HOY_PASSWORD)
    events = []
    try:
        response = session.get(list_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('a', class_=lambda c: c and 'item-interactive-animation' in c)
        
        for card in cards:
            relative_url = card.get('href', '')
            if not relative_url:
                continue
            detail_url = base_url + relative_url if relative_url.startswith('/') else relative_url
            card_title_el = card.find('h3')
            card_title = clean_text(card_title_el.text) if card_title_el else ""
            city = ""
            location_icon = card.find('svg', attrs={'name': 'svgId:location-icon'})
            if location_icon:
                parent_div = location_icon.find_parent('div')
                city = clean_text(parent_div.text) if parent_div else ""
            calendar_icon = card.find('svg', attrs={'name': 'svgId:calendar'})
            start_date, end_date = "", ""
            if calendar_icon:
                parent_div = calendar_icon.find_parent('div')
                if parent_div:
                    start_date, end_date = extract_hoy_dates_from_text(parent_div.text)
                    
            detail_data = parse_hoy_detail(session, detail_url)
            final_title = (detail_data["eventName"] if detail_data and detail_data["eventName"] else card_title)
            lat = detail_data["latitude"] if detail_data else None
            lon = detail_data["longitude"] if detail_data else None
            country = detail_data["country"] if detail_data else ""
            event_url = detail_data["eventUrl"] if detail_data else detail_url
            
            events.append({
                "eventName": final_title,
                "startDate": start_date,
                "endDate": end_date,
                "city": city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "eventUrl": event_url
            })
            print(f"İşlendi (Hoy Milonga): {final_title} ({start_date})")
    except Exception as e:
        print("Hoy Milonga taranırken hata:", e)
    return events


def scrape_tangopolix():
    print("\n--- Tangopolix taranıyor ---")
    url = "https://www.tangopolix.com/tango-events-calendar"
    headers = {'User-Agent': HEADERS['User-Agent']}
    events = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        calendar_div = soup.find('div', attrs={'data-controller': 'calendar'})
        if calendar_div and calendar_div.has_attr('data-calendar-events-value'):
            raw_events = json.loads(calendar_div['data-calendar-events-value'])
            for item in raw_events:
                city = item.get('city')
                country = item.get('country_name')
                lat, lon = get_coordinates(city, country)
                relative_url = item.get('url', '')
                tangopolix_subpage = "https://www.tangopolix.com" + relative_url if relative_url else ""
                actual_event_url = resolve_tangopolix_external_url(tangopolix_subpage)
                events.append({
                    "eventName": item.get('title'),
                    "startDate": item.get('start'),
                    "endDate": item.get('end'),
                    "city": city,
                    "country": country,
                    "latitude": lat,
                    "longitude": lon,
                    "eventUrl": actual_event_url,
                })
                print(f"İşlendi (Tangopolix): {item.get('title')} ({item.get('start')})")
    except Exception as e:
        print("Tangopolix taranırken hata oluştu:", e)
    return events


def scrape_tangocat():
    print("\n--- Tangocat taranıyor ---")
    url = "https://tangocat.net"
    headers = {'User-Agent': HEADERS['User-Agent']}
    events = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        event_lis = soup.find_all('li', class_=lambda x: x and 'p-3' in x)
        for li in event_lis:
            title_el = li.find('p', class_='mb-1')
            if not title_el:
                continue
            title = clean_text(title_el.text)
            date_el = li.find('p', class_='small mb-1')
            clean_date = clean_text(date_el.text) if date_el else ""
            location_btn = li.find('button', class_='btn-tc-location')
            if location_btn:
                location_text = clean_text(list(location_btn.stripped_strings)[-1])
                country, city = [x.strip() for x in location_text.split(',', 1)] if ',' in location_text else (location_text, "")
            else:
                country, city = "", ""
            link_el = li.find('a', class_='btn-tc-link')
            raw_url = link_el['href'] if link_el else ""
            resolved_url = resolve_tangocat_url(raw_url)
            start_date, end_date = parse_tango_dates(clean_date)
            lat, lon = get_coordinates(city, country)
            events.append({
                "eventName": title,
                "startDate": start_date,
                "endDate": end_date,
                "city": city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "eventUrl": resolved_url,
            })
            print(f"İşlendi (Tangocat): {title} ({start_date})")
    except Exception as e:
        print("Tangocat taranırken hata oluştu:", e)
    return events


def normalize_text_for_comparison(text):
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    return normalized.strip().lower()


def normalize_url_for_comparison(url):
    if not url:
        return ""
    url = url.strip().lower().rstrip('/')
    url = re.sub(r'^https?://(www\.)?', '', url)
    return url


def are_events_duplicate(event1, event2):
    if event1.get('startDate') != event2.get('startDate'):
        return False
    country1 = normalize_text_for_comparison(event1.get('country', ''))
    country2 = normalize_text_for_comparison(event2.get('country', ''))
    if country1 != country2:
        return False
    city1 = normalize_text_for_comparison(event1.get('city', ''))
    city2 = normalize_text_for_comparison(event2.get('city', ''))
    if city1 != city2:
        return False
    url1 = normalize_url_for_comparison(event1.get('eventUrl', ''))
    url2 = normalize_url_for_comparison(event2.get('eventUrl', ''))
    if not url1 or not url2 or url1 != url2:
        return False
    name1 = normalize_text_for_comparison(event1.get('eventName', ''))
    name2 = normalize_text_for_comparison(event2.get('eventName', ''))
    match = SequenceMatcher(None, name1, name2).find_longest_match(0, len(name1), 0, len(name2))
    if match.size < 10:
        return False
    return True


def main():
    polix_events = scrape_tangopolix()
    cat_events = scrape_tangocat()
    enjoy_events = scrape_enjoy_tango()
    hoy_events = scrape_hoy_milonga()
    
    combined_events = []
    
    for new_event in polix_events + cat_events + enjoy_events + hoy_events:
        is_dup = False
        for existing_event in combined_events:
            if are_events_duplicate(new_event, existing_event):
                is_dup = True
                print(f"Mükerrer Elendi: '{new_event['eventName']}'")
                break
        if not is_dup:
            combined_events.append(new_event)
            
    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=4)
        
    print(f"\n--- BÜTÜNLEŞİK SÜREÇ BİTTİ ---")
    print(f"Toplam benzersiz küresel etkinlik sayısı: {len(combined_events)}")
    print("Sonuçlar başarıyla 'events.json' dosyasına kaydedildi.")


if __name__ == "__main__":
    main()
