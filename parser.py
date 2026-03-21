"""
Narius Parser v2 — умный парсер выгодных аккаунтов с FunPay
- Фильтрует стартовые и чистые аккаунты (AR < 30)
- Пропускает лоты с ценой 0
- Извлекает AR из метаданных лота
- Создаёт чистое название для сайта
- Сохраняет прямые ссылки на лоты
"""

import requests
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup

CATEGORIES = {
    "genshin": {"url": "https://funpay.com/lots/696/", "game": "genshin", "name": "Genshin Impact"},
    "hsr": {"url": "https://funpay.com/lots/858/", "game": "hsr", "name": "Honkai: Star Rail"},
    "wuwa": {"url": "https://funpay.com/lots/1162/", "game": "wuwa", "name": "Wuthering Waves"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# Средние цены — лоты дешевле этого попадают в выдачу
AVG_PRICES = {"genshin": 2000, "hsr": 1500, "wuwa": 1000}

# Слова-фильтры: если есть в названии — пропускаем (не аккаунты)
SKIP_WORDS = [
    'стартовый', 'starter', 'чистый', 'clean', 'reroll',
    'автовыдача карт', 'гайд', 'guide', 'boost', 'буст',
    'фарм', 'farm', 'twitch', 'drops', 'донат', 'кристалл',
    'crystal', 'genesis', 'прокачк', 'услуг', 'оптимизац',
    'hwid', 'teleport', 'map', 'карта', 'мод', 'чит',
]

def clean_title(raw_title):
    """Убирает лишние эмодзи и спецсимволы, оставляя читаемый текст."""
    # Убираем декоративные юникод-символы
    cleaned = re.sub(r'[⭐🔥💎✨🌟💗💖🎀⚡️🚀💥🌸🍀☀️🟢🟥🟧🟨🔷🔶⭕💜🤍❤️💙🌺🎲🍨⚫️🌈🎊🔮🦄📣🎴🉐💵🟦◻️💮🔆❄️🎈🌇♨️🏆📡✍️🌍💰🎖️🛡️🌙🎯📋📌📩🗑️💾⚙️🎀]+', '', raw_title)
    # Убираем специальные обрамления
    cleaned = re.sub(r'[【】「」『』〔〕▐█░▒▓║╔╗╚╝═─┌┐└┘│♥ﮩ٨ـ●◆▸•]', '', cleaned)
    # Убираем множественные пробелы
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Убираем начальные/конечные спецсимволы
    cleaned = re.sub(r'^[\s|,\-:]+|[\s|,\-:]+$', '', cleaned)
    return cleaned if len(cleaned) > 5 else raw_title[:100]


def extract_ar(text):
    """Извлекает Adventure Rank / Trailblaze Level из текста."""
    patterns = [
        r'AR\s*(\d+)', r'ar\s*(\d+)',
        r'TL\s*(\d+)', r'tl\s*(\d+)',
        r'UL\s*(\d+)', r'ul\s*(\d+)',
        r'(\d+)\s*AR', r'(\d+)\s*ar',
        r'ранг\s*(\d+)', r'rank\s*(\d+)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def should_skip(title_lower):
    """Проверяет нужно ли пропустить этот лот."""
    return any(w in title_lower for w in SKIP_WORDS)


def parse_category(name, config):
    """Парсит одну категорию FunPay."""
    print(f"[*] Парсинг {name}: {config['url']}")
    lots = []

    try:
        resp = requests.get(config["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        print(f"    HTTP {resp.status_code}, размер: {len(resp.text)} байт")
    except Exception as e:
        print(f"[!] Ошибка загрузки {name}: {e}")
        return lots

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("a.tc-item")
    print(f"    Найдено {len(items)} элементов на странице")

    for item in items:
        try:
            # Название
            desc_el = item.select_one(".tc-desc-text")
            if not desc_el:
                continue
            raw_title = desc_el.get_text(strip=True)

            # Пропускаем по ключевым словам
            if should_skip(raw_title.lower()):
                continue

            # Цена — ищем в разных местах
            price = 0
            price_el = item.select_one(".tc-price div")
            if price_el:
                price_text = price_el.get_text(strip=True)
                nums = re.findall(r'[\d]+[.,]?\d*', price_text.replace(' ', ''))
                if nums:
                    price = float(nums[0].replace(',', '.'))

            # Пропускаем бесплатные и слишком дешёвые (< 50 руб)
            if price < 50:
                continue

            # Извлекаем AR из названия и метаданных
            full_text = raw_title
            # Также смотрим в доп. инфо лота
            extra_els = item.select(".tc-desc div")
            for el in extra_els:
                full_text += " " + el.get_text(strip=True)

            ar = extract_ar(full_text)

            # Фильтр: пропускаем низкий AR (стартовые акки)
            if ar > 0 and ar < 25:
                continue

            # Ссылка
            url = item.get("href", "")
            if url and not url.startswith("http"):
                url = "https://funpay.com" + url

            # Проверяем выгодность
            avg = AVG_PRICES.get(config["game"], 1500)
            if price > avg:
                continue

            # Чистое название для сайта
            clean = clean_title(raw_title)
            if ar > 0:
                display_title = f"AR {ar} | {clean}" if config["game"] == "genshin" else f"{'TL' if config['game']=='hsr' else 'UL'} {ar} | {clean}"
            else:
                display_title = clean

            lots.append({
                "id": abs(hash(url)) % 10000000,
                "game": config["game"],
                "platform": "funpay",
                "title": display_title[:200],
                "price": int(price),
                "oldPrice": int(avg),
                "url": url,
                "time": 0,
            })

        except Exception as e:
            print(f"    [!] Ошибка обработки лота: {e}")
            continue

    print(f"    Выгодных лотов: {len(lots)}")
    return lots


def main():
    print("=" * 50)
    print(f"Narius Parser v2 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    all_signals = []

    for name, config in CATEGORIES.items():
        lots = parse_category(name, config)
        all_signals.extend(lots)
        time.sleep(3)

    # Сортируем по цене
    all_signals.sort(key=lambda x: x["price"])

    # Лимит 25
    all_signals = all_signals[:25]

    # Проставляем время
    for i, sig in enumerate(all_signals):
        sig["time"] = i * 2 + 1

    # Сохраняем
    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump(all_signals, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"[✓] Сохранено {len(all_signals)} лотов в signals.json")
    if all_signals:
        print(f"    Цены от {all_signals[0]['price']}₽ до {all_signals[-1]['price']}₽")
    print("=" * 50)


if __name__ == "__main__":
    main()
