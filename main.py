import discord
import os
from discord.ext import commands
from discord.ui import View, Button
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111
IN_PROGRESS_ROLE_ID = 1259813357763170394

# --- МАКСИМАЛЬНО ПРОСТАЯ ОБМАНКА ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"Web server active on port {port}")
    server.serve_forever()

# Запускаем веб-сервер в отдельном потоке СРАЗУ
threading.Thread(target=run_web_server, daemon=True).start()
# ----------------------------------

class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid
    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            r_done = inter.guild.get_role(ROLE_ID)
            r_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if r_prog in m.roles: await m.remove_roles(r_prog)
            await m.add_roles(r_done)
            await inter.response.send_message(f"✅ <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Игрок не найден", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            r_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
            if r_prog in m.roles: await m.remove_roles(r_prog)
        await inter.response.send_message("❌ Отказано", ephemeral=True)

class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_final_v6")
    async def start(self, inter, btn):
        r_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if r_prog and r_prog not in inter.user.roles:
            await inter.user.add_roles(r_prog)
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть анкету", url=link))
        await inter.response.send_message("Ваша ссылка:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(IN_PROGRESS_ROLE_ID)
    if role: 
        try: await member.add_roles(role)
        except: pass

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
    
