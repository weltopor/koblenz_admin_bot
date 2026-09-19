import os
import asyncio
from aiohttp import web
from config import bot, dp
import handlers

# HTML-код нашей Mini App карточки
FORM_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Новое мероприятие</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: sans-serif; padding: 20px; background-color: var(--tg-theme-bg-color, #fff); color: var(--tg-theme-text-color, #000); }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 12px; border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; font-size: 14px; }
        button { width: 100%; padding: 14px; background-color: var(--tg-theme-button-color, #3390ec); color: var(--tg-theme-button-text-color, #fff); border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <h3 style="margin-top:0;">Добавить мероприятие</h3>
    <input type="text" id="title" placeholder="Название мероприятия" required>
    <input type="text" id="start_date" placeholder="Дата (ДД.ММ.ГГГГ)" required>
    <div style="display: flex; gap: 10px;">
        <input type="time" id="start_time" required>
        <input type="time" id="end_time">
    </div>
    <input type="text" id="location_name" placeholder="Название площадки">
    <textarea id="description" placeholder="Описание" rows="4"></textarea>
    <div style="display: flex; gap: 10px;">
        <input type="number" id="price_min" placeholder="Цена от (€)">
        <input type="number" id="price_max" placeholder="Цена до (€)">
    </div>
    <select id="category_id">
        <option value="1">1 - Food & Drink</option>
        <option value="2">2 - Music & Nightlife</option>
        <option value="3">3 - Culture & Art</option>
        <option value="4">4 - Tours & Sightseeing</option>
        <option value="5">5 - Sport & Fitness</option>
        <option value="8">8 - Family & Kids</option>
    </select>
    <button onclick="sendData()">Отправить в бота</button>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand(); // Разворачиваем на весь экран

        function sendData() {
            let data = {
                title: document.getElementById('title').value,
                start_date: document.getElementById('start_date').value,
                start_time: document.getElementById('start_time').value,
                end_time: document.getElementById('end_time').value,
                location_name: document.getElementById('location_name').value,
                description: document.getElementById('description').value,
                price_min: document.getElementById('price_min').value || 0,
                price_max: document.getElementById('price_max').value || 0,
                category_id: document.getElementById('category_id').value,
                location_address: "",
                organizer_id: "",
                additional_info: ""
            };
            tg.sendData(JSON.stringify(data));
        }
    </script>
</body>
</html>
"""

async def handle_form(request):
    return web.Response(text=FORM_HTML, content_type='text/html')

async def handle_healthcheck(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_healthcheck)
    app.router.add_get('/form', handle_form)  # Создаем ссылку на форму
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await handlers.set_bot_commands(bot)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())