import discord
import os
import asyncio
import re
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# ================= НАСТРОЙКИ (ID) =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038

# Роли
ROLE_CANDIDATE = 1259813357763170394     # КАНДИДАТ
ROLE_CONFIRMED = 1503397505692598392      # ПОДТВЕРЖДЕН
ROLE_REGISTERED = 1259828977942528111     # ЗАРЕГИСТРИРОВАН

# Отряды
ROLE_ALFA = 1495510801811898378           
ROLE_SEALS = 1503396665665523953          

# Каналы и категории
LOG_CHANNEL_ID = 1216754939616039014      
SQUAD_CHANNEL_ID = 1503398461679210687    
CATEGORY_DENY = 1216754938684903424       
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# ================= ВЕБ-СЕРВЕР =================
async def handle(request): return web.Response(text="Бот активен!")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= НОВАЯ ВЬЮ ДЛЯ УДАЛЕНИЯ ЧАТА =================
class DenyChatView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger, custom_id="delete_deny_ch_final")
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == MY_ID:
            await interaction.response.send_message("Чат будет удален через 3 секунды...")
            await asyncio.sleep(3)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("Только администратор может удалить этот чат.", ephemeral=True)

# ================= 2 ЭТАП: ВЫБОР ОТРЯДА =================
class SquadSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def complete(self, interaction, squad_id, name):
        member = interaction.user
        guild = interaction.guild
        r_squad = guild.get_role(squad_id)
        r_reg = guild.get_role(ROLE_REGISTERED)
        r_conf = guild.get_role(ROLE_CONFIRMED)

        if r_reg: await member.add_roles(r_reg)
        if r_squad: await member.add_roles(r_squad)
        if r_conf: await member.remove_roles(r_conf)

        await interaction.response.send_message(f"✅ Вы выбрали **{name}**. Регистрация завершена!", ephemeral=True)

    @discord.ui.button(label="Отряд Альфа 🐺", style=discord.ButtonStyle.primary, custom_id="sq_alfa_v6")
    async def join_alfa(self, itn, btn): await self.complete(itn, ROLE_ALFA, "Альфа")

    @discord.ui.button(label="Морские котики ⚓", style=discord.ButtonStyle.success, custom_id="sq_seals_v6")
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
            r_conf = interaction.guild.get_role(ROLE_CONFIRMED)
            r_cand = interaction.guild.get_role(ROLE_CANDIDATE)
            if r_conf: await member.add_roles(r_conf)
            if r_cand: await member.remove_roles(r_cand)
            await interaction.response.edit_message(content=f"✅ <@{self.target_user_id}>: Кандидат снят, выдана роль Подтвержден.", view=None)
        else:
            await interaction.response.send_message("Игрок не найден.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        global deny_counter
        deny_counter += 1
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        if not member: return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        category = guild.get_channel(CATEGORY_DENY)
        channel = await guild.create_text_channel(f"отказ-{deny_counter}", category=category, overwrites=overwrites)
        
        # ОТПРАВЛЯЕМ СООБЩЕНИЕ С КНОПКОЙ УДАЛЕНИЯ
        await channel.send(f"⚠️ <@{self.target_user_id}>, анкета отклонена. Ожидайте ответа от админа.", view=DenyChatView())
        await interaction.response.edit_message(content=f"❌ Отказано. Чат создан: {channel.mention}", view=None)

# ================= ОСНОВНОЙ БОТ =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(SquadSelectionView())
        self.add_view(RegistrationView())
        self.add_view(DenyChatView()) # Регистрируем кнопку удаления

    async def on_member_join(self, member):
        role = member.guild.get_role(ROLE_CANDIDATE)
        if role: await member.add_roles(role)

    async def on_message(self, message):
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                match = re.search(r"ID:(\d+)", message.content)
                if match:
                    uid = int(match.group(1))
                    await message.delete()
                    await message.channel.send(content=message.content, view=AdminReviewView(uid))
            except: pass
        await self.process_commands(message)

class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_v6")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View(); v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Ваша ссылка:", view=v, ephemeral=True)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация:**", view=RegistrationView())

@bot.command()
async def установка_отрядов(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Выберите отряд:**", view=SquadSelectionView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
