import discord
import os
import asyncio
from aiohttp import web

# Берем токен
TOKEN = os.getenv('BOT_TOKEN')

# 1. Простейший веб-сервер для Render
async def handle(request):
    return web.Response(text="Бот в сети!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"--- ВЕБ-СЕРВЕР ЗАПУЩЕН НА ПОРТУ {port} ---")

# 2. Настройка бота с МИНИМАЛЬНЫМИ правами (чтобы не падал)
intents = discord.Intents.default()
# Мы не включаем .all(), чтобы бот не вылетал, если галочки в портале забыты
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print("********************************")
    print(f"УРА! БОТ {bot.user} ПОДКЛЮЧИЛСЯ!")
    print("********************************")

async def main():
    await start_server()
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден в Environment Variables на Render!")
        return
    
    try:
        print("--- ПОПЫТКА ПОДКЛЮЧЕНИЯ К DISCORD ---")
        await bot.start(TOKEN)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")

if __name__ == "__main__":
    asyncio.run(main())
