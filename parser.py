"""
Narius Parser — парсер выгодных аккаунтов с FunPay
Собирает лоты из категорий Genshin Impact / HSR / Wuthering Waves,
находит выгодные предложения и сохраняет в signals.json

Использование:
  python parser.py

Для автоматического запуска каждые 10 минут — используй GitHub Actions
(см. README.md)
"""

import requests
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup

# Категории на FunPay (аккаунты)
CATEGORIES = {
    "genshin": {
        "url": "https://funpay.com/lots/696/",
        "game": "genshin"
    },
    "hsr": {
        "url": "https://funpay.com/lots/858/",
        "game": "hsr"
    },
    "wuwa": {
        "url": "https://funpay.com/lots/1162/",
        "game": "wuwa"
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Средние цены для определения выгодности (обновляй по мере необходимости)
AVG_PRICES = {
    "genshin": 1500,
    "hsr": 1200,
    "wuwa": 800,
}


def parse_category(name, config):
    """Парсит одну категорию FunPay и возвращает список лотов."""
    print(f"[*] Парсинг {name}: {config['url']}")
    lots = []

    try:
        resp = requests.get(config["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[!] Ошибка при загрузке {name}: {e}")
        return lots

    soup = BeautifulSoup(resp.text, "html.parser")

    # FunPay использует div.tc-item для каждого лота
    items = soup.select("a.tc-item")
    print(f"    Найдено {len(items)} лотов")

    for item in items:
        try:
            # Название лота
            title_el = item.select_one(".tc-desc-text")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            # Цена
            price_el = item.select_one(".tc-price div")
            if not price_el:
                continue
            price_text = price_el.get_text(strip=True)
            # Извлекаем число из цены (убираем ₽, пробелы и т.д.)
            price_num = re.sub(r'[^\d.]', '', price_text.replace(',', '.'))
            if not price_num:
                continue
            price = float(price_num)

            # Ссылка на лот
            url = item.get("href", "")
            if url and not url.startswith("http"):
                url = "https://funpay.com" + url

            # Определяем выгодность — цена ниже 70% от средней
            avg = AVG_PRICES.get(config["game"], 1000)
            is_deal = price < avg * 0.7

            if not is_deal:
                continue  # Показываем только выгодные

            lots.append({
                "id": hash(url) % 1000000,
                "game": config["game"],
                "platform": "funpay",
                "title": title[:200],
                "price": int(price),
                "oldPrice": int(avg),
                "url": url,
                "time": 0,
            })

        except Exception as e:
            continue

    return lots


def main():
    print("=" * 50)
    print(f"Narius Parser — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    all_signals = []

    for name, config in CATEGORIES.items():
        lots = parse_category(name, config)
        all_signals.extend(lots)
        time.sleep(2)  # Пауза между запросами

    # Сортируем по цене (дешёвые сначала)
    all_signals.sort(key=lambda x: x["price"])

    # Ограничиваем до 25 лотов
    all_signals = all_signals[:25]

    # Добавляем время (минуты назад)
    for i, sig in enumerate(all_signals):
        sig["time"] = i * 3 + 1

    # Сохраняем в JSON
    output_path = "signals.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_signals, f, ensure_ascii=False, indent=2)

    print(f"\n[✓] Сохранено {len(all_signals)} выгодных лотов в {output_path}")
    print("    Файл signals.json нужно положить рядом с narius.html")


if __name__ == "__main__":
    main()
