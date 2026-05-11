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
ROLE_CONFIRMED = 1503397505692598392      # ПОДТВЕРЖДЕН (пропуск к выбору)
ROLE_REGISTERED = 1259813357763170394     # ЗАРЕГИСТРИРОВАН (финальная)

# Отряды
ROLE_ALFA = 1495510801811898378           # Альфа
ROLE_SEALS = 1503396665665523953          # Морские котики

# Каналы и категории
LOG_CHANNEL_ID = 1216754939616039014      
SQUAD_CHANNEL_ID = 1503398461679210687    
CATEGORY_DENY = 1216754938684903424       # Категория для чатов отказа
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

# ================= ВЫБОР ОТРЯДА =================
class SquadSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def complete(self, interaction, squad_id, name):
        member = interaction.user
        guild = interaction.guild
        
        r_squad = guild.get_role(squad_id)
        r_reg = guild.get_role(ROLE_REGISTERED)
        r_conf = guild.get_role(ROLE_CONFIRMED)

        # 1. Сначала выдаем роль отряда и финальную роль
        if r_squad: await member.add_roles(r_squad)
        if r_reg: await member.add_roles(r_reg)
        
        # 2. Небольшая задержка, чтобы Discord успел обновить статус
        await asyncio.sleep(1)
        
        # 3. Снимаем роль "Подтвержден"
        if r_conf and r_conf in member.roles:
            await member.remove_roles(r_conf)

        await interaction.response.send_message(f"✅ Вы вступили в **{name}**! Регистрация завершена.", ephemeral=True)

    @discord.ui.button(label="Отряд Альфа 🐺", style=discord.ButtonStyle.primary, custom_id="sq_alfa_v3")
    async def join_alfa(self, itn, btn): await self.complete(itn, ROLE_ALFA, "Альфа")

    @discord.ui.button(label="Морские котики ⚓", style=discord.ButtonStyle.success, custom_id="sq_seals_v3")
    async def join_seals(self, itn, btn): await self.complete(itn, ROLE_SEALS, "Морские котики")

# ================= ПРОВЕРКА АНКЕТЫ И ОТКАЗ =================
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
            # Снимаем кандидата только если ID ролей РАЗНЫЕ. 
            # Если ROLE_CANDIDATE == ROLE_REGISTERED, лучше снять его на финальном этапе.
            if r_cand and ROLE_CANDIDATE != ROLE_CONFIRMED:
                await member.remove_roles(r_cand)

            await interaction.response.edit_message(content=f"✅ <@{self.target_user_id}> одобрен. Выдана роль Подтвержден.", view=None)
        else:
            await interaction.response.send_message("Игрок не найден.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        global deny_counter
        deny_counter += 1
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True),
            member: discord.PermissionOverwrite(read_messages=True)
        }

        category = guild.get_channel(CATEGORY_DENY)
        channel = await guild.create_text_channel(f"отказ-{deny_counter}", category=category, overwrites=overwrites)
        
        await channel.send(f" <@{self.target_user_id}>, ваша анкета отклонена. Здесь вы можете узнать причину у <@{MY_ID}>.")
        await interaction.response.edit_message(content=f"❌ Отказано. Чат создан: {channel.mention}", view=None)

# ================= ГЛАВНЫЙ БОТ =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(SquadSelectionView())
        self.add_view(RegistrationView())

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
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_v3")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View(); v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Ваша ссылка:", view=v, ephemeral=True)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Регистрация в академию:**", view=RegistrationView())

@bot.command()
async def установка_отрядов(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Выберите ваш будущий отряд:**", view=SquadSelectionView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
