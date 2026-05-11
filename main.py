import discord
import os
import asyncio
import re
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# ================= НАСТРОЙКИ (ID) =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038

# Роли
ROLE_CANDIDATE = 1259813357763170394     # Роль КАНДИДАТ (дается при входе)
ROLE_CONFIRMED = 1503397505692598392      # Роль ПОДТВЕРЖДЕН (после анкеты)
ROLE_REGISTERED = 1259813357763170394     # Роль ЗАРЕГИСТРИРОВАН (финальная)

# Отряды
ROLE_ALFA = 1495510801811898378           # Отряд Альфа
ROLE_SEALS = 1503396665665523953          # Морские котики

# Каналы
LOG_CHANNEL_ID = 1216754939616039014      # Канал проверки анкет
SQUAD_CHANNEL_ID = 1503398461679210687    # Канал выбора отряда
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# ================= ВЕБ-СЕРВЕР (ДЛЯ RENDER) =================
async def handle(request): return web.Response(text="Бот активен!")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= 2 ЭТАП: ВЫБОР ОТРЯДА =================
class SquadSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def complete(self, interaction, squad_id, name):
        member = interaction.user
        guild = interaction.guild
        
        roles_to_add = [guild.get_role(squad_id), guild.get_role(ROLE_REGISTERED)]
        roles_to_remove = [guild.get_role(ROLE_CANDIDATE), guild.get_role(ROLE_CONFIRMED)]

        # Фильтруем None и выдаем/забираем
        await member.add_roles(*[r for r in roles_to_add if r])
        await member.remove_roles(*[r for r in roles_to_remove if r])

        await interaction.response.send_message(f"✅ Вы вступили в **{name}**! Регистрация завершена.", ephemeral=True)

    @discord.ui.button(label="Отряд Альфа 🐺", style=discord.ButtonStyle.primary, custom_id="sq_alfa")
    async def join_alfa(self, itn, btn): await self.complete(itn, ROLE_ALFA, "Альфа")

    @discord.ui.button(label="Морские котики ⚓", style=discord.ButtonStyle.success, custom_id="sq_seals")
    async def join_seals(self, itn, btn): await self.complete(itn, ROLE_SEALS, "Морские котики")

# ================= 1 ЭТАП: ПРОВЕРКА АНКЕТЫ =================
class AdminReviewView(View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        member = interaction.guild.get_member(self.target_user_id)
        if member:
            await member.add_roles(interaction.guild.get_role(ROLE_CONFIRMED))
            await interaction.response.edit_message(content=f"✅ <@{self.target_user_id}> подтвержден. Ждем выбор отряда.", view=None)
        else:
            await interaction.response.send_message("Игрок не найден.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        # Логика создания чата обсуждения (как в прошлых версиях)
        await interaction.response.send_message("Чат отказа создается...", ephemeral=True)

# ================= ОСНОВНОЙ БОТ =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(SquadSelectionView())
        self.add_view(RegistrationView())

    # Авто-выдача роли кандидата при заходе
    async def on_member_join(self, member):
        role = member.guild.get_role(ROLE_CANDIDATE)
        if role: await member.add_roles(role)

    async def on_message(self, message):
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                match = re.search(r"ID:(\d+)", message.content)
                if match:
                    user_id = int(match.group(1))
                    await message.delete()
                    await message.channel.send(content=message.content, view=AdminReviewView(user_id))
            except: pass
        await self.process_commands(message)

class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View(); v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Ваша ссылка:", view=v, ephemeral=True)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Начни регистрацию здесь:**", view=RegistrationView())

@bot.command()
async def установка_отрядов(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Выбери свой отряд:**", view=SquadSelectionView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
