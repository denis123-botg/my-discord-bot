import discord
import os
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web
import asyncio

TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014

# --- ID РОЛЕЙ ---
ROLE_ID = 1259828977942528111          # Роль "Зарегистрирован"
IN_PROGRESS_ROLE_ID = 1259813357763170394  # Роль "Кандидат"
# ----------------

# --- МИНИ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is alive")

async def run_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000)))
    await site.start()

# Кнопки для админов
class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role_done = inter.guild.get_role(ROLE_ID)
            role_progress = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if role_progress in m.roles:
                await m.remove_roles(role_progress)
            await m.add_roles(role_done)
            await inter.response.send_message(f"✅ Игрок <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Игрок не найден", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role_progress = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if role_progress in m.roles:
                await m.remove_roles(role_progress)
        await inter.response.send_message("❌ Отказано, роль кандидата снята", ephemeral=True)

# Кнопка регистрации
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_v5")
    async def start(self, inter, btn):
        role_progress = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if role_progress and role_progress not in inter.user.roles:
            await inter.user.add_roles(role_progress)
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть анкету", url=link))
        await inter.response.send_message("Заполните анкету по ссылке:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

# --- ВЫДАЧА РОЛИ ПРИ ЗАХОДЕ НА СЕРВЕР ---
@bot.event
async def on_member_join(member):
    role = member.guild.get_role(IN_PROGRESS_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
            print(f"Выдана роль новому игроку: {member.name}")
        except Exception as e:
            print(f"Ошибка выдачи роли при заходе: {e}")

@bot.command()
async def установка(ctx):
    await ctx.send("**Регистрация**\nНажмите кнопку, чтобы начать:", view=PersistentView())

@bot.event
async def on_message(msg):
    if msg.channel.id == ADMIN_CHANNEL_ID and msg.author.bot and msg.embeds:
        try:
            footer = msg.embeds[0].footer.text
            if footer and "ID:" in footer:
                uid = "".join(filter(str.isdigit, footer))
                await msg.channel.send(f"Анкета от <@{uid}>:", view=AdminAction(uid))
        except: pass
    await bot.process_commands(msg)

async def main():
    asyncio.create_task(run_server())
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
