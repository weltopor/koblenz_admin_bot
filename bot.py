import os
import asyncio
from aiohttp import web
from config import bot, dp
import handlers  # Импортируем хэндлеры

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
    # Устанавливаем кнопку меню с командами в Telegram
    await handlers.set_bot_commands(bot)
    
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())