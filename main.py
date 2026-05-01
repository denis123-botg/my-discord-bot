import discord
import os
from discord.ext import commands
from discord.ui import View, Button

# Берем токен из секретов Render
TOKEN = os.getenv('BOT_TOKEN')

URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111

class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid
    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            await m.add_roles(inter.guild.get_role(ROLE_ID))
            await inter.response.send_message(f"✅ Игрок <@{self.uid}> принят!", ephemeral=True)
    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        await inter.response.send_message("❌ Отказано", ephemeral=True)

class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_final")
    async def start(self, inter, btn):
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть анкету", url=link))
        await inter.response.send_message("Твоя ссылка:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    await ctx.send("**Регистрация**\nНажми кнопку ниже:", view=PersistentView())

@bot.event
async def on_message(msg):
    if msg.channel.id == ADMIN_CHANNEL_ID and msg.author.bot and msg.embeds:
        try:
            footer = msg.embeds[0].footer.text
            if footer and "ID:" in footer:
                uid = "".join(filter(str.isdigit, footer))
                await msg.channel.send(f"Анкета от <@{uid}>. Управление:", view=AdminAction(uid))
        except: pass
    await bot.process_commands(msg)

if TOKEN:
    bot.run(TOKEN)
else:
    print("ОШИБКА: Токен не найден в Environment Variables!")
    
