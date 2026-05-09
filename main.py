import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# Константы (проверь, чтобы BOT_TOKEN был в настройках Render)
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
IN_PROGRESS_ROLE_ID = 1259813357763170394

# Веб-сервер для "здоровья" Render
async def handle(request):
    return web.Response(text="Bot is alive")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# Кнопка анкеты
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="button_v25")
    async def start(self, inter, btn):
        role = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if role:
            try: await inter.user.add_roles(role)
            except: pass
        await inter.response.send_message(f"Твоя ссылка: {URL_SAYTA}?uid={inter.user.id}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.event
async def on_ready():
    print(f"--- БОТ {bot.user} ЗАПУЩЕН! ---")

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация**\nНажмите кнопку:", view=PersistentView())

async def main():
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
