import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# Твои данные
TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111
IN_PROGRESS_ROLE_ID = 1259813357763170394
MY_ID = 1118970574887211038  # Твой ID владельца

# Веб-сервер для поддержки активности на Render
async def handle(request):
    return web.Response(text="Bot is online")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# Класс кнопки для анкеты
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
        await inter.response.send_message(f"Твоя ссылка на анкету: {link}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        # Включаем все интенты
        intents = discord.Intents.all()
        # Устанавливаем префикс "!"
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Регистрируем кнопку, чтобы она работала вечно
        self.add_view(PersistentView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    # Проверка на твой ID
    if ctx.author.id != MY_ID:
        return # Если пишет не владелец, бот просто игнорирует
    
    await ctx.send("**Регистрация на сервере**\nНажмите кнопку ниже, чтобы получить ссылку на анкету:", view=PersistentView())

async def main():
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
