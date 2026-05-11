import discord
import os
import asyncio
import re
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038

# Роли
ROLE_CANDIDATE = 1259813357763170394     # КАНДИДАТ
ROLE_CONFIRMED = 1503397505692598392      # ПОДТВЕРЖДЕН
ROLE_REGISTERED = 1259828977942528111     # ЗАРЕГИСТРИРОВАН

# Отряды
ROLE_ALFA = 1495510801811898378           
ROLE_SEALS = 1503396665665523953          

# Каналы
LOG_CHANNEL_ID = 1216754939616039014      
SQUAD_CHANNEL_ID = 1503398461679210687    
CATEGORY_DENY = 1216754938684903424       
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# ================= СЕРВЕР =================
async def handle(request): return web.Response(text="Work")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= VIEW: УДАЛЕНИЕ ЧАТА ОТКАЗА =================
class DenyChatView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger, custom_id="del_ch")
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == MY_ID:
            await interaction.response.send_message("Удаление...")
            await asyncio.sleep(2)
            await interaction.channel.delete()

# ================= VIEW: ВЫБОР ОТРЯДА =================
class SquadSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def complete(self, interaction, squad_id, name):
        member = interaction.user
        guild = interaction.guild
        r_conf = guild.get_role(ROLE_CONFIRMED)
        
        # Даем Зарегистрированного и Отряд, снимаем Подтвержденного
        await member.add_roles(guild.get_role(ROLE_REGISTERED), guild.get_role(squad_id))
        if r_conf: await member.remove_roles(r_conf)
        await interaction.response.send_message(f"✅ Выбрано: {name}", ephemeral=True)

    @discord.ui.button(label="Альфа 🐺", style=discord.ButtonStyle.primary, custom_id="sq_1")
    async def sq1(self, itn, btn): await self.complete(itn, ROLE_ALFA, "Альфа")
    @discord.ui.button(label="Морские котики ⚓", style=discord.ButtonStyle.success, custom_id="sq_2")
    async def sq2(self, itn, btn): await self.complete(itn, ROLE_SEALS, "Морские котики")

# ================= VIEW: ПРОВЕРКА АНКЕТЫ =================
class AdminReviewView(View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        member = interaction.guild.get_member(self.target_user_id)
        if member:
            # Снимаем Кандидата, даем Подтвержденного
            await member.add_roles(interaction.guild.get_role(ROLE_CONFIRMED))
            await member.remove_roles(interaction.guild.get_role(ROLE_CANDIDATE))
            await interaction.response.edit_message(content=f"✅ <@{self.target_user_id}> принят.", view=None)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        global deny_counter
        deny_counter += 1
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        ch = await guild.create_text_channel(f"отказ-{deny_counter}", category=guild.get_channel(CATEGORY_DENY), overwrites=overwrites)
        await ch.send(f"⚠️ <@{self.target_user_id}>, отказ. Ждите админа.", view=DenyChatView())
        await interaction.response.edit_message(content=f"❌ Отказано. Чат: {ch.mention}", view=None)

# ================= VIEW: АНКЕТА =================
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_v10")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View(); v.add_item(discord.ui.Button(label="Открыть", url=url))
        await itn.response.send_message("Ссылка:", view=v, ephemeral=True)

# ================= BOT =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(SquadSelectionView()); self.add_view(RegistrationView()); self.add_view(DenyChatView())
    async def on_member_join(self, m):
        r = m.guild.get_role(ROLE_CANDIDATE)
        if r: await m.add_roles(r)
    async def on_message(self, m):
        if m.channel.id == LOG_CHANNEL_ID and m.webhook_id:
            match = re.search(r"ID:(\d+)", m.content)
            if match:
                uid = int(match.group(1))
                await m.delete()
                await m.channel.send(content=m.content, view=AdminReviewView(uid))
        await self.process_commands(m)

bot = MyBot()
@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID: await ctx.send("**Регистрация:**", view=RegistrationView())
@bot.command()
async def установка_отрядов(ctx):
    if ctx.author.id == MY_ID: await ctx.send("**Выбор отряда:**", view=SquadSelectionView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
