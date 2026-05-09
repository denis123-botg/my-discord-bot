import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# Константы (проверь ID еще раз)
TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111
IN_PROGRESS_ROLE_ID = 1259813357763170394

# Веб-сервер для "обманки" Render
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Кнопка анкеты
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_final_v10")
    async def start(self, inter, btn):
        role_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if role_prog: 
            try: await inter.user.add_roles(role_prog)
            except: pass
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        await inter.response.send_message(f"Твоя ссылка: {link}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    await ctx.send("**Регистрация**\nНажми кнопку ниже:", view=PersistentView())

async def main():
    await start_web_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
