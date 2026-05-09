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
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

# 1. Веб-сервер для "здоровья" Render
async def handle(request):
    return web.Response(text="Бот работает!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передает порт через переменную среды PORT
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"--- Веб-сервер запущен на порту {port} ---")

# 2. Кнопка анкеты
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None) # Чтобы кнопка работала вечно
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_button_final")
    async def callback(self, interaction, button):
        role = interaction.guild.get_role(ROLE_ID)
        if role:
            try:
                await interaction.user.add_roles(role)
            except Exception as e:
                print(f"Не удалось выдать роль: {e}")
        
        link = f"{URL_SAYTA}?uid={interaction.user.id}"
        await interaction.response.send_message(f"Твоя ссылка для регистрации: {link}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        # Используем включенные тобой Intents
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    
    async def setup_hook(self):
        # Регистрируем кнопку, чтобы она не "забывалась" после перезагрузки
        self.add_view(RegistrationView())

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ БОТ {bot.user} УСПЕШНО ЗАПУЩЕН!")

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация**\nНажмите кнопку ниже, чтобы начать:", view=RegistrationView())

async def main():
    await start_server()
    if not TOKEN:
        print("❌ ОШИБКА: Переменная BOT_TOKEN не установлена в Render!")
        return
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
