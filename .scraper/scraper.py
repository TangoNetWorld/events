import requests
from bs4 import BeautifulSoup
import json
import time
import unicodedata
import re
import datetime
from difflib import SequenceMatcher

# 1. Koordinat ve URL Önbelleği (Aynı şeyleri tekrar sorgulamamak için)
coord_cache = {}
url_resolve_cache = {}

# Ayları sayısal değerlere eşleyen sözlük
months_map = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def parse_enjoy_en_date(date_str, year):
    """
    Sistem dilinden (locale) bağımsız olarak 'January 5' gibi metinleri
    güvenli bir şekilde 'YYYY-MM-DD' formatına çevirir.
    """
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


def parse_location_text(location_text):
    """
    '中国 上海｜Shanghai, China' metninden Şehir ve Ülke bilgisini ayıklar.
    """
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


def resolve_tangopolix_external_url(tangopolix_url):
    if not tangopolix_url:
        return ""
    if tangopolix_url in url_resolve_cache:
        return url_resolve_cache[tangopolix_url]
    try:
        time.sleep(1)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(tangopolix_url, headers=headers, timeout=5)
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


# --- GÜNCELLENEN ENJOY TANGO SCRAPER FONKSİYONU ---

def scrape_enjoy_tango():
    print("\n--- Enjoy Tango taranıyor ---")
    current_year = datetime.datetime.now().year
    current_timestamp_ms = int(time.time() * 1000)
    
    # Keşfettiğimiz API adresini dinamik parametrelerle oluşturuyoruz
    api_url = f"https://enjoytango.com/app/api/event_list.php?tid=2&date={current_year}&t={current_timestamp_ms}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://enjoytango.com/app/list.php?tid=2&city=',
    }
    
    events = []
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Enjoy Tango API'ye erişilemedi. Yanıt kodu: {response.status_code}")
            return []
            
        raw_events = response.json()
        for item in raw_events:
            title = clean_text(item.get('title', ''))
            if not title:
                continue
                
            # 1. Başlangıç Tarihi ve Yıl Çekimi (evtdate milisaniye damgasından)
            evt_timestamp = item.get('evtdate')
            year = current_year
            start_date = ""
            if evt_timestamp:
                start_dt = datetime.datetime.fromtimestamp(evt_timestamp / 1000)
                start_date = start_dt.strftime('%Y-%m-%d')
                year = start_dt.year
            else:
                start_date = parse_enjoy_en_date(item.get('timefrom_en'), year)
                
            # 2. Bitiş Tarihi Çekimi (timeto_en alanından)
            timeto_en = item.get('timeto_en')
            if timeto_en:
                end_date = parse_enjoy_en_date(timeto_en, year)
            else:
                end_date = start_date
                
            # 3. Konum Çekimi
            city_raw = item.get('city', '')
            city, country = parse_location_text(city_raw)
            
            # 4. Koordinat Çekimi (Zaten API'de mevcut)
            lat = float(item.get('latitude')) if item.get('latitude') else None
            lon = float(item.get('longitude')) if item.get('longitude') else None
            
            # 5. Orijinal URL Çekimi
            event_url = item.get('website', '').strip()
            if not event_url or not event_url.startswith('http'):
                relative_url = item.get('arcurl', '')
                if relative_url:
                    event_url = "https://enjoytango.com" + relative_url
                else:
                    event_url = f"https://enjoytango.com/app/show.php?aid={item.get('id')}"
            
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
            print(f"Çözüldü (Enjoy Tango): {title} -> {event_url} ({start_date})")
            
    except Exception as e:
        print("Enjoy Tango taranırken hata oluştu:", e)
        
    return events


def scrape_tangocat():
    print("\n--- Tangocat taranıyor ---")
    url = "https://tangocat.net"
    headers = {'User-Agent': 'Mozilla/5.0'}
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
            raw_date = date_el.text if date_el else ""
            clean_date = clean_text(raw_date)
            location_btn = li.find('button', class_='btn-tc-location')
            if location_btn:
                location_text = clean_text(list(location_btn.stripped_strings)[-1])
                if ',' in location_text:
                    country, city = [x.strip() for x in location_text.split(',', 1)]
                else:
                    country, city = location_text, ""
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
            print(f"Çözüldü (Tangocat): {title} -> {resolved_url}")
            print(f"Başarıyla İşlendi: {title} ({start_date} -> {end_date})")
    except Exception as e:
        print("Tangocat taranırken hata oluştu:", e)
    return events


def scrape_tangopolix():
    print("\n--- Tangopolix taranıyor ---")
    url = "https://www.tangopolix.com/tango-events-calendar"
    headers = {'User-Agent': 'Mozilla/5.0'}
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
                print(f"Çözüldü (Tangopolix): {item.get('title')} -> {actual_event_url}")
    except Exception as e:
        print("Tangopolix taranırken hata oluştu:", e)
    return events


# --- DEDUPLICATION (MÜKERRER ENGELLEME) YARDIMCI FONKSİYONLARI ---

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
    enjoy_events = scrape_enjoy_tango()  # Yeni kaynağımız entegre edildi
    
    combined_events = []
    
    # Tüm kaynaklardan gelen verileri tek bir havuzda birleştiriyoruz
    for new_event in polix_events + cat_events + enjoy_events:
        is_dup = False
        for existing_event in combined_events:
            if are_events_duplicate(new_event, existing_event):
                is_dup = True
                print(f"Mükerrer Tespit Edildi ve Elendi: '{new_event['eventName']}' (Kaynak URL: {new_event['eventUrl']})")
                break
        
        if not is_dup:
            combined_events.append(new_event)
            
    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=4)
        
    print(f"\n--- BİTTİ ---")
    print(f"Toplam benzersiz etkinlik sayısı: {len(combined_events)}")
    print("Veriler 'events.json' dosyasına başarıyla kaydedildi.")

if __name__ == "__main__":
    main()
