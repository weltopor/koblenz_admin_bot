import os
import asyncio
from aiohttp import web
from config import bot, dp
import handlers

FORM_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ-панель CityFlow</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: var(--tg-theme-bg-color, #0f172a);
            --text-color: var(--tg-theme-text-color, #f8fafc);
            --card-bg: #1e293b;
            --accent: #38bdf8;
            --btn-text: #0f172a;
        }

        /* Темы оформления (Варианты под ваше настроение) */
        body.theme-1 { --bg-color: #0b0f19; --card-bg: #131b2e; --accent: #6366f1; --btn-text: #fff; }
        body.theme-2 { --bg-color: #f8fafc; --text-color: #0f172a; --card-bg: #ffffff; --accent: #0284c7; --btn-text: #fff; }
        body.theme-3 { --bg-color: #fdf6e2; --text-color: #433422; --card-bg: #faedcd; --accent: #dda15e; --btn-text: #283618; }
        body.theme-4 { --bg-color: #111827; --card-bg: #1f2937; --accent: #f43f5e; --btn-text: #fff; }
        body.theme-5 { --bg-color: #030712; --card-bg: #111827; --accent: #10b981; --btn-text: #fff; }

        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 16px; background-color: var(--bg-color); color: var(--text-color); margin: 0; transition: background 0.3s, color 0.3s; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 12px; border: 1px solid rgba(128,128,128,0.3); border-radius: 12px; box-sizing: border-box; font-size: 14px; background: rgba(255,255,255,0.05); color: inherit; }
        button { width: 100%; padding: 14px; background-color: var(--accent); color: var(--btn-text); border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; transition: opacity 0.2s; }
        button:active { opacity: 0.8; }
        .hidden { display: none !important; }
        .error { color: #ef4444; margin-bottom: 10px; font-size: 14px; text-align: center; }
        .login-box, .panel-box { max-width: 400px; margin: 20px auto; padding: 24px; border-radius: 20px; background: var(--card-bg); box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
        .theme-selector { display: flex; gap: 8px; margin-bottom: 16px; justify-content: center; }
        .theme-btn { width: 32px; height: 32px; border-radius: 50%; border: 2px solid #fff; cursor: pointer; padding: 0; }
    </style>
</head>
<body class="theme-1">

    <!-- ЭКРАН АВТОРИЗАЦИИ -->
    <div id="loginScreen" class="login-box">
        <h2 style="text-align:center; margin-top:0;">🔐 Вход</h2>
        <div id="errorMsg" class="error"></div>
        <input type="text" id="username" placeholder="Логин" autocomplete="off">
        <input type="password" id="password" placeholder="Пароль">
        <button onclick="checkLogin()">Войти в систему</button>
    </div>

    <!-- ЭКРАН ПУЛЬТА И ФОРМЫ -->
    <div id="formScreen" class="panel-box hidden">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="margin:0;">✨ Выберите стиль</h3>
        </div>
        
        <!-- Переключатель вариантов дизайна -->
        <div class="theme-selector">
            <button class="theme-btn" style="background:#0b0f19;" onclick="setTheme('theme-1')"></button>
            <button class="theme-btn" style="background:#f8fafc;" onclick="setTheme('theme-2')"></button>
            <button class="theme-btn" style="background:#faedcd;" onclick="setTheme('theme-3')"></button>
            <button class="theme-btn" style="background:#111827;" onclick="setTheme('theme-4')"></button>
            <button class="theme-btn" style="background:#030712;" onclick="setTheme('theme-5')"></button>
        </div>

        <h3 style="margin-top:20px;">📅 Добавить событие</h3>
        <input type="text" id="title" placeholder="Название мероприятия" required>
        <input type="text" id="start_date" placeholder="Дата (ДД.ММ.ГГГГ)" required>
        <div style="display: flex; gap: 10px;">
            <input type="time" id="start_time" required>
            <input type="time" id="end_time">
        </div>
        <input type="text" id="location_name" placeholder="Название площадки">
        <textarea id="description" placeholder="Описание" rows="3"></textarea>
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
            <option value="6">6 - Nature & Adventure</option>
            <option value="7">7 - Wellness & Spa</option>
            <option value="8">8 - Family & Kids</option>
            <option value="9">9 - Markets & Shopping</option>
            <option value="10">10 - Community & Social</option>
            <option value="11">11 - Charity & Eco</option>
        </select>
        <button onclick="sendData()" style="margin-top: 10px;">Отправить в бота</button>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();

        const CORRECT_USER = "admin";
        const CORRECT_PASS = "koblenz2026";

        function checkLogin() {
            let u = document.getElementById('username').value.trim();
            let p = document.getElementById('password').value.trim();
            
            if (u === CORRECT_USER && p === CORRECT_PASS) {
                document.getElementById('loginScreen').classList.add('hidden');
                document.getElementById('formScreen').classList.remove('hidden');
            } else {
                document.getElementById('errorMsg').innerText = "Неверный логин или пароль!";
            }
        }

        function setTheme(themeName) {
            document.body.className = themeName;
            localStorage.setItem('selected_theme', themeName);
        }

        // Восстанавливаем тему при повторном открытии
        let savedTheme = localStorage.getItem('selected_theme');
        if (savedTheme) {
            document.body.className = savedTheme;
        }

        function sendData() {
            let title = document.getElementById('title').value;
            let date = document.getElementById('start_date').value;
            
            if (!title || !date) {
                alert("Заполните название и дату мероприятия!");
                return;
            }

            let data = {
                title: title,
                start_date: date,
                start_time: document.getElementById('start_time').value,
                end_time: document.getElementById('end_time').value,
                location_name: document.getElementById('location_name').value,
                description: document.getElementById('description').value,
                price_min: document.getElementById('price_min').value || 0,
                price_max: document.getElementById('price_max').value || 0,
                category_id: document.getElementById('category_id').value,
                location_address: "",
                organizer_id: null,
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
    app.router.add_get('/form', handle_form)
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