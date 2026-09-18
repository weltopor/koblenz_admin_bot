import os
import json
import re
import asyncio
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from google.genai.errors import APIError
from aiohttp import web

# Загрузка переменных окружения из .env (для локального запуска)
load_dotenv()

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GEMINI_KEY = os.getenv("GEMINI_KEY")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Koblenz Events")
# ===================================================

ai_client = genai.Client(api_key=GEMINI_KEY)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).worksheet("Events")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

pending_events = {}

PROMPT_TEMPLATE = """
Ты — ассистент базы данных событий города Кобленц. 
Распарси текст анонса мероприятия и верни ТОЛЬКО валидный JSON-объект без лишних слов со следующей структурой:
{
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
  "additional_info": "Дополнительная информация или контакты"
}
Если какое-то поле не удается определить, укажи null.

Текст анонса:
"""

async def generate_with_retry(prompt: str):
    models_to_try = ['gemini-3.6-flash', 'gemini-3.1-pro-preview']
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
                last_error_msg = f"[{model_name}] Unexpected error: {str(e)}"
                break

    raise Exception(f"Не удалось получить ответ от Gemini. Детали: {last_error_msg}")



@dp.message(F.from_user.id == ADMIN_ID)
async def handle_announcement(message: types.Message):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовый анонс мероприятия.")
        return

    status_msg = await message.answer("🧠 Извлекаю данные через Gemini AI...")

    try:
        response = await generate_with_retry(PROMPT_TEMPLATE + message.text)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        if not json_match:
            raise ValueError("Не удалось получить структурированный JSON от модели.")
            
        data = json.loads(json_match.group(0))
        user_id = message.from_user.id
        pending_events[user_id] = data

        end_time_str = f" до {data.get('end_time')}" if data.get('end_time') else ""
        preview_text = (
            f"📌 **Проверьте распарсенные данные:**\n\n"
            f"**Название:** {data.get('title')}\n"
            f"**Дата и время:** {data.get('start_date')} в {data.get('start_time')}{end_time_str}\n"
            f"**Место:** {data.get('location_name')} ({data.get('location_address')})\n"
            f"**Цена:** {data.get('price_min') or 0} € - {data.get('price_max') or 0} €\n"
            f"**ID Категории:** {data.get('category_id')}\n"
            f"**Описание:** {data.get('description')}\n"
            f"**Доп. инфо:** {data.get('additional_info')}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить в таблицу", callback_data="save_event"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")
            ]
        ])

        await status_msg.edit_text(preview_text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as err:
        await status_msg.edit_text(f"❌ Ошибка при обработке: {err}")

@dp.callback_query(F.data == "save_event")
async def save_to_sheets(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = pending_events.get(user_id)

    if not data:
        await callback.message.edit_text("❌ Данные не найдены или сессия истекла.")
        return

    try:
        records = sheet.get_all_records()
        next_id = len(records) + 1

        row = [
            next_id,                         # id
            "active",                        # status
            "FALSE",                         # featured
            data.get("title", "") or "",
            data.get("description", "") or "",
            "",                              # icon_url
            data.get("start_date", "") or "",
            data.get("start_time", "") or "",
            data.get("end_time", "") or "",  # end_time
            data.get("location_name", "") or "",
            data.get("location_address", "") or "",
            data.get("price_min") if data.get("price_min") is not None else 0,
            data.get("price_max") if data.get("price_max") is not None else 0,
            "",                              # ticket_link
            data.get("additional_info", "") or "",
            data.get("category_id", "") or "",
            ""                               # organizer_id
        ]

        sheet.append_row(row)
        del pending_events[user_id]
        await callback.message.edit_text("🎉 **Событие успешно добавлено в Google Таблицу!**")

    except Exception as err:
        await callback.message.edit_text(f"❌ Ошибка записи в таблицу: {err}")

@dp.callback_query(F.data == "cancel_event")
async def cancel_save(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_events:
        del pending_events[user_id]
    await callback.message.edit_text("Действие отменено.")

# ==================== WEB SERVER ДЛЯ RENDER FREE TIER ====================
async def handle_healthcheck(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())