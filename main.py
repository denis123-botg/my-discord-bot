import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# Берем данные
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394
URL = "https://denis123-botg.github.io/sirion_forms/"

# Сервер для Render
async def hello(r): return web.Response(text="OK")
async def start_web():
    app = web.Application()
    app.router.add_get('/', hello)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# Кнопка
class MyView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="v30")
    async def s(self, i, b):
        r = i.guild.get_role(ROLE_ID)
        if r:
            try: await i.user.add_roles(r)
            except: pass
        await i.response.send_message(f"Ссылка: {URL}?uid={i.user.id}", ephemeral=True)

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None)
    async def setup_hook(self): self.add_view(MyView())

bot = Bot()

@bot.event
async def on_ready(): print(f"ЗАПУЩЕН: {bot.user}")

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация**", view=MyView())

async def main():
    await start_web()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__": asyncio.run(main())
