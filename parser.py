import json
import re
import time
import httpx
from bs4 import BeautifulSoup

CHANNEL = "umacity"
TELETYPE_URL = "https://teletype.media/@pwrdbysnow/allcomics"

DEFAULT_NAMES = {
    "tokai_teio": "Токай Тейо",
    "maruzensky": "Марузенски",
    "silence_suzuka": "Сайленс Судзука",
    "symboli_rudolf": "Символи Рудольф",
    "oguri_cap": "Огури Кэп",
    "special_week": "Спешиал Вик",
    "mejiro_mcqueen": "Меджиро Маккуин",
    "gold_ship": "Голд Шип",
    "daiwa_scarlet": "Дайва Скарлет",
    "vodka": "Водка",
    "sakura_chiyono_o": "Сакура Чиёно О",
    "rice_shower": "Райс Шауэр",
    "twin_turbo": "Твин Турбо",
    "manhattan_cafe": "Манхэттен Кафе",
    "agnes_tachyon": "Агнес Тахион",
    "tamamo_cross": "Тамамо Кросс",
    "super_creek": "Супер Крик",
    "mayano_top_gun": "Маяно Топ Ган",
    "mejiro_ardan": "Меджиро Ардан",
    "satono_diamond": "Сатоно Даймонд",
    "kitasan_black": "Китасан Блэк"
}

def get_teletype_titles(client):
    titles = {}
    try:
        res = client.get(TELETYPE_URL)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                m = re.search(r"t\.me/umacity/(\d+)", a["href"])
                if m:
                    title = a.get_text().strip().lstrip("•-—* ")
                    if len(title) > 1:
                        titles[int(m.group(1))] = title
    except Exception as e:
        print(f"Teletype error: {e}")
    return titles

def extract_fallback_title(text, char_name, msg_id):
    if not text:
        return char_name or f"Перевод #{msg_id}"
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines:
        if line.startswith('#') or line.startswith('http://') or line.startswith('https://'):
            continue
        if re.match(r'^(автор|арт|оригинал|source|artist):', line, re.IGNORECASE):
            continue
        if re.match(r'^@\w+', line):
            continue
        clean = re.sub(r'#[A-Za-z0-9_а-яА-ЯёЁ]+', '', line).strip('«"\'--— ')
        if len(clean) > 1:
            return clean
    return char_name or f"Перевод #{msg_id}"

def main():
    client = httpx.Client(headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
    }, follow_redirects=True, timeout=20.0)

    teletype_titles = get_teletype_titles(client)

    before_id = None
    comics = []
    characters = {}

    # Скачиваем последние 10 страниц канала
    for _ in range(10):
        url = f"https://t.me/s/{CHANNEL}?before={before_id}" if before_id else f"https://t.me/s/{CHANNEL}"
        res = client.get(url)
        if res.status_code != 200:
            break

        soup = BeautifulSoup(res.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message")
        if not messages:
            break

        oldest = None
        for msg in messages:
            post_attr = msg.get("data-post", "")
            if not post_attr:
                continue
            msg_id = int(post_attr.split("/")[-1])
            if oldest is None or msg_id < oldest:
                oldest = msg_id

            text_el = msg.find("div", class_="tgme_widget_message_text")
            text = text_el.get_text(separator="\n").strip() if text_el else ""

            # Извлечение всех картинок
            photos = []
            for p in msg.find_all("a", class_="tgme_widget_message_photo_wrap"):
                style = p.get("style", "")
                m = re.search(r"background-image:url\('([^']+)'\)", style)
                if m:
                    photos.append(m.group(1))

            if not photos:
                continue

            if "#переводы" in text.lower() or "#перевод" in text.lower():
                tags = [t.lower() for t in re.findall(r'#([A-Za-z0-9_а-яА-ЯёЁ]+)', text)]
                author = next((t.replace("author_", "") for t in tags if t.startswith("author_")), None)
                char_tags = [t for t in tags if t not in ["переводы", "перевод", "комикс", "манга", "арт"] and not t.startswith("author_")]
                primary_char = char_tags[0] if char_tags else "other"

                name_ru = DEFAULT_NAMES.get(primary_char, primary_char.replace("_", " ").title())
                title = teletype_titles.get(msg_id) or extract_fallback_title(text, name_ru, msg_id)

                comics.append({
                    "id": msg_id,
                    "title": title,
                    "text": text,
                    "author": author,
                    "primary_char": primary_char,
                    "primary_char_name": name_ru,
                    "tags": tags,
                    "images": photos
                })

        if not oldest or oldest == before_id:
            break
        before_id = oldest
        time.sleep(0.5)

    # Убираем дубликаты и сортируем
    unique_comics = {c["id"]: c for c in comics}
    comics_list = sorted(unique_comics.values(), key=lambda x: x["id"], reverse=True)

    for c in comics_list:
        p = c["primary_char"]
        if p not in characters:
            characters[p] = {
                "tag": p,
                "name_ru": c["primary_char_name"],
                "count": 0,
                "avatar": c["images"][0] if c["images"] else None
            }
        characters[p]["count"] += 1

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({
            "comics": comics_list,
            "characters": list(characters.values())
        }, f, ensure_ascii=False, indent=2)

    print(f"Готово! Сохранено {len(comics_list)} комиксов в data.json")

if __name__ == "__main__":
    main()
