
import os
import sys

print("--- ЗАПУСК ДИАГНОСТИКИ ---")

# 1. Проверяем токен
token = os.getenv('BOT_TOKEN')
if not token:
    print("❌ ОШИБКА: Токен не найден в Environment Variables!")
else:
    print(f"✅ Токен найден (длина: {len(token)} символов)")

# 2. Проверяем библиотеку
try:
    import discord
    print(f"✅ Библиотека discord.py установлена (версия: {discord.__version__})")
except ImportError:
    print("❌ ОШИБКА: Библиотека discord.py НЕ установлена!")

# 3. Минимальный сервер для Render (чтобы он не ругался)
from aiohttp import web
async def handle(request): return web.Response(text="OK")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"✅ Веб-сервер запущен на порту {port}")

# 4. Простейший вход в Дискорд
import asyncio
async def test_run():
    await start_server()
    if token:
        print("--- ПОПЫТКА ПОДКЛЮЧЕНИЯ К DISCORD ---")
        client = discord.Client(intents=discord.Intents.default())
        @client.event
        async def on_ready():
            print(f"🚀 ПОБЕДА! Бот {client.user} в сети!")
        try:
            await client.start(token)
        except Exception as e:
            print(f"❌ DISCORD ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
