import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# --- ТВОИ НАСТРОЙКИ ---
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394  # Роль игрока
LOG_CHANNEL_ID = 1216754939616039014  # Канал проверки
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

# Переменная для хранения номера отказа (сбросится при перезапуске бота на Render)
deny_counter = 0

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request): return web.Response(text="Бот в сети!")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# --- КНОПКИ В СЕКРЕТНОМ ЧАТЕ ---
class ChatControlView(View):
    def __init__(self, target_user, role_to_give):
        super().__init__(timeout=None)
        self.target_user = target_user
        self.role_to_give = role_to_give

    @discord.ui.button(label="Выдать роль ✅", style=discord.ButtonStyle.green)
    async def give_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID:
            return await interaction.response.send_message("Только админ может это делать!", ephemeral=True)
        
        await self.target_user.add_roles(self.role_to_give)
        await interaction.response.send_message(f"✅ Роль выдана! Чат будет удален через 3 секунды...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger)
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID:
            return await interaction.response.send_message("Только админ может это делать!", ephemeral=True)
        
        await interaction.response.send_message("🗑️ Удаление чата...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

# --- КНОПКИ ПРОВЕРКИ (В КАНАЛЕ ЛОГОВ) ---
class AdminReviewView(View):
    def __init__(self, target_user):
        super().__init__(timeout=None)
        self.target_user = target_user

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        await self.target_user.add_roles(role)
        await interaction.response.edit_message(content=f"✅ Заявка {self.target_user.mention} принята!", view=None)

    @discord.ui.button(label="Отказать (Чат) ❌", style=discord.ButtonStyle.danger)
    async def deny_with_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        global deny_counter
        deny_counter += 1
        
        # Форматируем номер (0001, 0002...)
        formatted_num = f"{deny_counter:04d}"
        channel_name = f"обсуждение-отказа-{formatted_num}"
        
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.target_user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Создаем канал
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        role = guild.get_role(ROLE_ID)
        view = ChatControlView(self.target_user, role)
        
        await channel.send(f"👋 {self.target_user.mention}, тут можно обсудить отказ №{formatted_num}.", view=view)
        await interaction.response.edit_message(content=f"❌ Отказано. Чат создан: {channel.mention}", view=None)

# --- КНОПКА ДЛЯ ИГРОКОВ ---
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_btn")
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        
        if log_channel:
            view = AdminReviewView(interaction.user)
            await log_channel.send(f"🔔 Новая попытка регистрации: {interaction.user.mention}", view=view)
        
        link = f"{URL_SAYTA}?uid={interaction.user.id}"
        await interaction.response.send_message(f"Твоя ссылка: {link}", ephemeral=True)

# --- ЗАПУСК БОТА ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
    
    async def setup_hook(self):
        self.add_view(RegistrationView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Нажмите кнопку для регистрации:**", view=RegistrationView())

async def main():
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
