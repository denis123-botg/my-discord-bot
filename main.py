import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
IN_PROGRESS_ROLE_ID = 1259813357763170394

# Тот самый веб-сервер, который нужен Render
async def handle(request):
    return web.Response(text="Бот в сети!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render сам назначит порт, бот его подхватит
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_final_v10")
    async def start(self, inter, btn):
        role_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if role_prog: await inter.user.add_roles(role_prog)
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        await inter.response.send_message(f"Твоя ссылка: {link}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация**\nНажмите кнопку:", view=PersistentView())

async def main():
    # Сначала запускаем сервер, потом бота
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
