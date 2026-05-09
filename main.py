import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# ТВОИ ДАННЫЕ
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394
URL = "https://denis123-botg.github.io/sirion_forms/"

# Минимальный веб-сервер для Render
async def handle(request): return web.Response(text="Бот живой!")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"--- WEB SERVER STARTED ON PORT {port} ---")

# Кнопка анкеты
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_v1")
    async def start_btn(self, interaction, button):
        role = interaction.guild.get_role(ROLE_ID)
        if role:
            try: await interaction.user.add_roles(role)
            except: pass
        link = f"{URL}?uid={interaction.user.id}"
        await interaction.response.send_message(f"Твоя ссылка: {link}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    
    async def setup_hook(self):
        self.add_view(RegistrationView())

bot = MyBot()

@bot.event
async def on_ready():
    print(f"--- БОТ {bot.user} УСПЕШНО ПОДКЛЮЧЕН К DISCORD ---")

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация на сервере**\nНажмите кнопку ниже:", view=RegistrationView())

async def main():
    try:
        await start_server()
        async with bot:
            if not TOKEN:
                print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена в настройках Render!")
                return
            await bot.start(TOKEN)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")

if __name__ == "__main__":
    asyncio.run(main())
