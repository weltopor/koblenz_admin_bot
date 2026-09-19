import asyncio
from google.genai.errors import APIError
from config import ai_client

def get_prompt(current_date_str: str) -> str:
    return f"""
Ты — ассистент базы данных событий города Кобленц. Текущая дата: {current_date_str}.
Распарси текст анонса мероприятия и верни ТОЛЬКО валидный JSON-объект без лишних слов со следующей структурой:
{{
  "title": "Название мероприятия",
  "description": "Краткое описание",
  "start_date": "DD.MM.YYYY",
  "start_time": "HH:mm",
  "end_time": "HH:mm",
  "location_name": "Название площадки/места",
  "location_address": "Адрес или ориентир",
  "price_min": 0.00,
  "price_max": 0.00,
  "category_id": "Укажи только цифру ID от 1 до 11 из списка: [1-Food & Drink, 2-Music & Nightlife, 3-Culture & Art, 4-Tours & Sightseeing, 5-Sport & Fitness, 6-Nature & Adventure, 7-Wellness & Spa, 8-Family & Kids, 9-Markets & Shopping, 10-Community & Social, 11-Charity & Eco]",
  "organizer_id": "Укажи только цифру ID организатора из списка или null, если организатор не указан: [1-Weingut Schwaab, 2-Cafe Hahn GmbH, 3-Weingut Spurzem, 4-Koblenz-Touristik GmbH, 5-ARTogether Koblenz, 6-Jana Morjan & Dieter Eberle GbR, 7-Club Europe Ltd, 8-Forum Mittelrhein Koblenz, 9-Eifelblock Koblenz, 10-Kulturzentrum Festung Ehrenbreitstein, 11-Eigenbetrieb der Stadt Koblenz Grünflächen- und Bestattungswesen, 12-Koblenzer Sektmuseum, 13-Yoga mit Dorothe Struschka, 14-Green Office Uni Koblenz, 15-Rhein-Museum Koblenz e. V., 16-Elterninitiative krebskranker Kinder Koblenz e. V., 17-Villa Musica, 18-Landesbibliothekszentrum Rheinland-Pfalz, 19-Djangos Erben, 20-Ludwig Museum, 21-Pride+ und Pride-Zeit, 22-Gleichstellungsstelle der Stadt Koblenz und StadtBibliothek, 23-Music Live e.V Koblenz, 24-Mittelrheinmuseum Koblenz, 25-Mosellum, 26-Rhein-Mosel-Halle, 27-Gilles Personenschifffahrt GmbH, 28-Club Nova Koblenz, 29-Köln-Düsseldorfer Deutsche Rheinschiffahrt GmbH]",
  "additional_info": "Дополнительная информация или контакты"
}}
Если в тексте написано "завтра", "сегодня", "в пятницу" или указана дата без года, рассчитывай её строго относительно текущей даты: {current_date_str}. Если какое-то поле не удается определить, укажи null.

Текст анонса:
"""

async def generate_with_retry(prompt: str):
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash']
    last_error_msg = ""

    for model_name in models_to_try:
        delay = 2.0
        for attempt in range(3):
            try:
                chat = ai_client.aio.chats.create(model=model_name)
                response = await chat.send_message(prompt)
                if response and response.text:
                    return response
            except APIError as e:
                last_error_msg = f"[{model_name}] APIError {e.code}: {e.message}"
                if e.code in (503, 429) and attempt < 2:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                break
            except Exception as e:
                last_error_msg = f"[{model_name}] Неожиданная ошибка: {str(e)}"
                break

    raise Exception(f"Не удалось получить ответ от Gemini. Детали: {last_error_msg}")