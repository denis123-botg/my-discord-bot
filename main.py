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

async def handle(request):
    return web.Response(text="Bot is alive")

async def run_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000)))
    await site.start()

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
            
            # Забираем кандидата, даем жителя
            if role_progress in m.roles:
                await m.remove_roles(role_progress)
            await m.add_roles(role_done)
            
            await inter.response.send_message(f"✅ Игрок <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Игрок не найден на сервере", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role_progress = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if role_progress in m.roles:
                await m.remove_roles(role_progress)
        await inter.response.send_message("❌ Анкета отклонена, роль кандидата снята", ephemeral=True)

class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom
