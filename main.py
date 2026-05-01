import discord
import os
from discord.ext import commands
from discord.ui import View, Button
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import asyncio

TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111
IN_PROGRESS_ROLE_ID = 1259813357763170394

# --- НАДЕЖНАЯ ОБМАНКА ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is online")
    def log_message(self, format, *args): return # Чтобы не спамить в консоль

def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health check server started on port {port}")
    server.serve_forever()

# Запускаем сервер в отдельном потоке сразу
threading.Thread(target=run_health_server, daemon=True).start()
# ----------------------------------

class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid
    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role_done = inter.guild.get_role(ROLE_ID)
            role_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if role_prog in m.roles: await m.remove_roles(role_prog)
            await m.add_roles(role_done)
            await inter.response.send_message(f"✅ <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Игрок не найден", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if role_prog in m.roles: await m.remove_roles(role_prog)
        await inter.response.send_message("❌ Отказано", ephemeral=True)

class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_final")
    async def start(self, inter, btn):
        role_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if role_prog and role_prog not in inter.user.roles:
            await inter.user.add_roles(role_prog)
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть анкету", url=link))
        await inter.response.send_message("Ваша ссылка:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(IN_PROGRESS_ROLE_ID)
    if role: await member.add_roles(role)

@bot.command()
async def установка(ctx):
    await ctx.send("**Регистрация**\nНажмите кнопку ниже:", view=PersistentView())

@bot.event
async def on_message(msg):
    if msg.channel.id == ADMIN_CHANNEL_ID and msg.author.bot and msg.embeds:
        try:
            footer = msg.embeds[0].footer.text
            if footer and "ID:" in footer:
                uid = "".join(filter(str.isdigit, footer))
                await msg.channel.send(f"Анкета <@{uid}>:", view=AdminAction(uid))
        except: pass
    await bot.process_commands(msg)

if TOKEN:
    bot.run(TOKEN)
else:
    print("TOKEN NOT FOUND")
    
