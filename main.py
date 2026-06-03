import os
import discord
from discord.ext import commands, tasks
import aiohttp
from aiohttp import web
import asyncio
import sqlite3
import time

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN не задан")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class SirionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="s!", intents=intents)

    async def setup_hook(self):
        self.loop.create_task(self.start_web_server())
        self.check_activity.start()

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="OK"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 10000)
        await site.start()
        print("🌐 Веб-сервер на порту 10000")

    @tasks.loop(hours=1)
    async def check_activity(self):
        guild = self.guilds[0] if self.guilds else None
        if not guild:
            return
        for member in guild.members:
            if member.bot:
                continue
            # Проверка активности (упрощённо)

bot = SirionBot()

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")

@bot.tree.command(name="ping", description="Проверка")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

if __name__ == "__main__":
    bot.run(TOKEN)