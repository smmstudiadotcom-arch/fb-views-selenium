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
XS     = os.environ.get("FB_XS",     "23%3AUcW9QDH7Lw4OMA%3A2%3A1777366320%3A-1%3A-1%3A%3AAcxV4doD641eN1HEAQNfnkX0cE357pxRh9ixF-wCuA")
DATR   = os.environ.get("FB_DATR",   "gvGqaR00HB8BBQCtWvA_ZrBw")
FR     = os.environ.get("FB_FR",     "1BiHkrekV5y5wC9M4.AWcjA0M_D1BFpG4ArVdD9DEHJz1hf_Cp4e633bJFekyBL_WG64E.Bp8HUz..AAA.0.0.Bp8HUz.AWd2xaqh1GaCzn5odyasmAo3ovQ")
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
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")

    if os.path.exists(chrome_bin):
        options.binary_location = chrome_bin

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def set_cookies(driver):
    driver.get("https://www.facebook.com/")
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

        reels_url = f"https://www.facebook.com/{FB_PAGE_ID}/reels"
        log(f"🔄 Открываю (desktop): {reels_url}")
        driver.get(reels_url)
        time.sleep(10)

        # Закрываем cookie banner / попапы если есть
        try:
            close_buttons = driver.find_elements(By.CSS_SELECTOR, '[aria-label*="Close"], [aria-label*="Закрыть"], button[data-cookiebanner="accept_button"]')
            for btn in close_buttons[:3]:
                try:
                    btn.click()
                    time.sleep(1)
                except:
                    pass
        except:
            pass

        # Скроллим чтобы подгрузить контент
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Ищем все video элементы и кликаем на них
        urls = set()
        
        try:
            from selenium.webdriver.common.by import By
            
            # Пробуем селекторы для desktop версии
            selectors = [
                'a[href*="/reel/"]',
                'a[aria-label*="Reel"]',
                'div[role="link"]',
                'a[href*="/videos/"]',
                '[data-pagelet*="ProfileTilesFeed"]  a',
            ]
            
            video_elements = []
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        log(f"🔍 Селектор '{selector}': {len(elements)} элементов")
                        video_elements = elements
                        break
                except:
                    continue
            
            if not video_elements:
                log(f"⚠️  Ни один селектор не нашёл элементов")
                # Дебаг: сохраним HTML
                html = driver.page_source
                log(f"📄 HTML размер: {len(html)}, сохраняю первые 1000 символов...")
                log(f"HTML: {html[:1000]}")
                return []

            log(f"🔍 Всего найдено: {len(video_elements)}")

            for i, elem in enumerate(video_elements[:10]):  # Проверяем первые 10
                try:
                    # Скроллим к элементу
                    driver.execute_script("arguments[0].scrollIntoView();", elem)
                    time.sleep(1)
                    
                    # Используем JavaScript клик (обходит перекрытия)
                    driver.execute_script("arguments[0].click();", elem)
                    time.sleep(3)

                    # Получаем URL из адресной строки
                    current_url = driver.current_url
                    log(f"🔍 Клик #{i+1}: {current_url}")

                    # Проверяем что это видео/reel
                    if '/reel/' in current_url or '/video' in current_url or '/watch' in current_url:
                        urls.add(current_url)
                        log(f"✅ Reel #{i+1}: {current_url}")

                    # Возвращаемся назад
                    driver.back()
                    time.sleep(2)

                except Exception as e:
                    log(f"⚠️  Элемент #{i+1} ошибка: {e}")
                    # Пробуем вернуться назад если застряли
                    try:
                        driver.back()
                        time.sleep(1)
                    except:
                        pass
                    continue

        except Exception as e:
            log(f"❌ Ошибка поиска элементов: {e}")

        log(f"🎬 Найдено Reels: {len(urls)}")
        if urls:
            for u in list(urls)[:5]:
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
