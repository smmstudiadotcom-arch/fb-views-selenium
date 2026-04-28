import random
import time
import os
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import requests

# ══════════════════════════════════════
#  JAP
# ══════════════════════════════════════
JAP_API_KEY = "ec2fb6c8f5a4ea7ba6cf532e87a09895"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

# ══════════════════════════════════════
#  FACEBOOK REELS
# ══════════════════════════════════════
FB_PAGE_ID     = "100081997113052"
FB_SERVICE     = 9604
FB_QTY_MIN     = 500
FB_QTY_MAX     = 1000
CHECK_INTERVAL = 3600  # каждый час

# Cookies
C_USER = os.environ.get("FB_C_USER", "61553351803414")
XS     = os.environ.get("FB_XS",     "8%3AeGYkn8717BMe-g%3A2%3A1774503965%3A-1%3A-1%3A%3AAcw0XpXFaM1nyL4JOlFdYs_Ud6Y079Nz9FGx2eBrLs8")
DATR   = os.environ.get("FB_DATR",   "gvGqaR00HB8BBQCtWvA_ZrBw")
FR     = os.environ.get("FB_FR",     "1fXp7RjNu6E4tlLeA.AWc5dZieQn71hppDlUvFZLqzKA5QYrGNQzKXlgvHvbeVm7zLhgs.Bp6coy..AAA.0.0.Bp6coy.AWeEM5yj4-p0pnZr32HrLye4l9I")
SB     = os.environ.get("FB_SB",     "hfGqaZIWmBX2PQV9iqh9Tr1V")

STATE_FILE = "processed_reels.txt"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [FB-Reels] {msg}", flush=True)

def load_processed():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed(data):
    with open(STATE_FILE, "w") as f:
        for item in data:
            f.write(f"{item}\n")

def check_balance():
    try:
        resp = requests.post(JAP_API_URL, data={"key": JAP_API_KEY, "action": "balance"}, timeout=10)
        if resp.text.strip():
            data = resp.json()
            if "balance" in data:
                log(f"💰 Баланс: ${data['balance']} {data.get('currency', '')}")
    except Exception as e:
        log(f"❌ Ошибка баланса: {e}")

def create_jap_order(link):
    quantity = random.randint(FB_QTY_MIN, FB_QTY_MAX)
    payload = {"key": JAP_API_KEY, "action": "add", "service": FB_SERVICE, "link": link, "quantity": quantity}
    try:
        log(f"📤 Заказ: service={FB_SERVICE}, qty={quantity}")
        resp = requests.post(JAP_API_URL, data=payload, timeout=15)
        log(f"📥 JAP: {resp.status_code} | {repr(resp.text[:150])}")
        if not resp.text.strip():
            log("❌ Пустой ответ JAP")
            return
        data = resp.json()
        if "order" in data:
            log(f"✅ Заказ! ID: {data['order']} | Кол-во: {quantity}")
        elif "error" in data:
            log(f"❌ JAP ошибка: {data['error']}")
    except Exception as e:
        log(f"❌ Ошибка заказа: {e}")

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=414,896")
    options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")

    if os.path.exists(chrome_bin):
        options.binary_location = chrome_bin

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def set_cookies(driver):
    driver.get("https://m.facebook.com/")
    time.sleep(2)

    cookies = [
        {"name": "c_user", "value": C_USER, "domain": ".facebook.com"},
        {"name": "xs", "value": XS, "domain": ".facebook.com"},
        {"name": "datr", "value": DATR, "domain": ".facebook.com"},
        {"name": "fr", "value": FR, "domain": ".facebook.com"},
        {"name": "sb", "value": SB, "domain": ".facebook.com"},
    ]
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            log(f"⚠️  Cookie {cookie['name']}: {e}")

    log("🍪 Cookies установлены")

def fetch_reels():
    driver = None
    try:
        driver = create_driver()
        set_cookies(driver)

        reels_url = f"https://m.facebook.com/profile.php?id={FB_PAGE_ID}&sk=reels"
        log(f"🔄 Открываю: {reels_url}")
        driver.get(reels_url)
        time.sleep(8)

        # Скроллим чтобы подгрузить контент
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        html = driver.page_source
        log(f"📥 HTML: {len(html)} символов")

        # Дебаг: ищем video ID разными способами
        # 1. data-store с video info
        data_stores = re.findall(r'data-store="([^"]*video[^"]*)"', html, re.IGNORECASE)
        log(f"🔍 data-store с video: {data_stores[:3]}")

        # 2. data-uri или data-href
        data_uris = re.findall(r'data-(?:uri|href|url|src)="([^"]*)"', html)
        video_uris = [u for u in data_uris if 'video' in u.lower() or 'reel' in u.lower() or 'watch' in u.lower()]
        log(f"🔍 data-uri/href с video: {video_uris[:5]}")

        # 3. story-photo блоки — ищем data-store рядом
        story_blocks = re.findall(r'data-store="([^"]*)"[^>]*data-testid="story-photo', html)
        log(f"🔍 story-photo data-store: {story_blocks[:3]}")

        # 4. Ищем все числовые ID в data-store
        all_data_stores = re.findall(r'data-store="([^"]*)"', html)
        log(f"🔍 Всего data-store: {len(all_data_stores)}")
        for ds in all_data_stores[:5]:
            log(f"   → {ds[:150]}")

        # 5. Ищем в onclick обработчиках
        onclicks = re.findall(r'onclick="([^"]*video[^"]*)"', html, re.IGNORECASE)
        log(f"🔍 onclick с video: {onclicks[:3]}")

        # 6. Ищем JSON в script тегах с video_id
        scripts = re.findall(r'<script[^>]*>([^<]*video_id[^<]*)</script>', html, re.IGNORECASE)
        for s in scripts[:2]:
            ids = re.findall(r'"video_id"\s*:\s*"?(\d{10,})"?', s)
            log(f"🔍 script video_ids: {ids[:5]}")

        # 7. Ищем все href вообще (первые 10)
        all_hrefs = re.findall(r'href="(/[^"]{10,})"', html)
        log(f"🔍 Все href ({len(all_hrefs)}), первые 5:")
        for h in all_hrefs[:5]:
            log(f"   → {h}")

        urls = set()

        urls = set()

        # Паттерн 1: /reel/ID
        for match in re.finditer(r'/reel/(\d{10,})', html):
            urls.add(f"https://www.facebook.com/reel/{match.group(1)}")

        # Паттерн 2: video_id
        for match in re.finditer(r'"video_id":"(\d{10,})"', html):
            urls.add(f"https://www.facebook.com/reel/{match.group(1)}")

        # Паттерн 3: /videos/ID
        for match in re.finditer(r'/videos/(\d{10,})', html):
            urls.add(f"https://www.facebook.com/reel/{match.group(1)}")

        # Паттерн 4: watch/?v=ID
        for match in re.finditer(r'watch/\?v=(\d{10,})', html):
            urls.add(f"https://www.facebook.com/reel/{match.group(1)}")

        # Паттерн 5: href с reel
        for match in re.finditer(r'href="[^"]*reel[^"]*?(\d{10,})', html):
            urls.add(f"https://www.facebook.com/reel/{match.group(1)}")

        # Дебаг
        reel_count = len(re.findall(r'reel', html, re.IGNORECASE))
        video_count = len(re.findall(r'video', html, re.IGNORECASE))
        log(f"🔍 Слово 'reel' в HTML: {reel_count}, 'video': {video_count}")
        log(f"🎬 Найдено Reels: {len(urls)}")

        if urls:
            for u in list(urls)[:3]:
                log(f"   → {u}")

        return list(urls)

    except Exception as e:
        log(f"❌ Selenium ошибка: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def main():
    log("🚀 Facebook Reels бот запущен (Selenium)!")
    log(f"📘 Страница: {FB_PAGE_ID} | Услуга: {FB_SERVICE} | {FB_QTY_MIN}-{FB_QTY_MAX}")
    check_balance()

    processed = load_processed()

    if not processed:
        log("📌 Первый запуск — запоминаю существующие Reels...")
        reels = fetch_reels()
        if reels:
            processed.update(reels)
            save_processed(processed)
            log(f"📌 Запомнено {len(reels)} Reels. Жду новые...")
        else:
            log("⚠️  Reels не найдены при первом запуске")

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            reels = fetch_reels()
            new_reels = [url for url in reels if url not in processed]

            if new_reels:
                log(f"🆕 Новых Reels: {len(new_reels)}")
                for reel_url in new_reels:
                    log(f"🆕 {reel_url}")
                    create_jap_order(reel_url)
                    processed.add(reel_url)
                    time.sleep(2)
                save_processed(processed)
            else:
                log("🔍 Нет новых Reels")
        except Exception as e:
            log(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
