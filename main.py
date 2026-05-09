import discord
import os
import asyncio
from aiohttp import web

# Константы (просто цифры и ссылки)
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394
URL = "https://denis123-botg.github.io/sirion_forms/"

# 1. Веб-сервер (чтобы Render не ругался)
async def handle(request): return web.Response(text="OK")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"--- Сервер запущен на порту {port} ---")

# 2. Настройка бота
intents = discord.Intents.default() # Минимальные права, чтобы не упасть
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"--- БОТ {bot.user} В СЕТИ! ---")

async def main():
    await start_server()
    async with bot:
        try:
            await bot.start(TOKEN)
        except Exception as e:
            print(f"ОШИБКА ТОКЕНА: {e}")

if __name__ == "__main__":
    asyncio.run(main())
