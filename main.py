import discord
from discord.ext import commands
from discord.ui import View, Button

TOKEN = 'MTQ5OTY1NzEwMDA0Mzc0NzMzOA.GWtUct.xPnXDdHzPEacPi7a53UqvNCUztXXjpRMzotGfI'
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111

# Кнопки для админа
class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            await m.add_roles(inter.guild.get_role(ROLE_ID))
            await inter.response.send_message(f"✅ Участник <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Участник не найден", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter, btn):
        await inter.response.send_message("❌ Анкета отклонена", ephemeral=True)

# Кнопка регистрации
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start")
    async def start(self, inter, btn):
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть форму", url=link))
        await inter.response.send_message("Твоя ссылка:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

# Используй ЭТУ команду для создания поста: !установка
@bot.command()
async def установка(ctx):
    await ctx.send("Нажми на кнопку ниже, чтобы начать регистрацию:", view=PersistentView())

@bot.event
async def on_message(msg):
    # Исправленная логика: бот ПИШЕТ НОВОЕ сообщение с кнопками
    if msg.channel.id == ADMIN_CHANNEL_ID and msg.author.bot and msg.embeds:
        try:
            footer = msg.embeds[0].footer.text
            if footer and "ID:" in footer:
                uid = footer.split("ID: ")[1].strip()
                # БОТ НЕ РЕДАКТИРУЕТ, А ПИШЕТ НОВОЕ
                await msg.channel.send(f"Управление анкетой игрока <@{uid}>:", view=AdminAction(uid))
        except Exception as e:
            print(f"Ошибка: {e}")
    await bot.process_commands(msg)

bot.run(TOKEN)
