import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# Константы
TOKEN = os.getenv('BOT_TOKEN')
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111
IN_PROGRESS_ROLE_ID = 1259813357763170394

# Веб-сервер для Render
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# Кнопки админа
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

# Главная кнопка анкеты
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_final_v999")
    async def start(self, inter, btn):
        r_prog = inter.guild.get_role(IN_PROGRESS_ROLE_ID)
        if r_prog and r_prog not in inter.user.roles:
            try: await inter.user.add_roles(r_prog)
            except: pass
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть анкету", url=link))
        await inter.response.send_message("Твоя ссылка:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

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

async def main():
    await start_web_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
    
