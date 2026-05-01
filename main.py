import discord
import os
from discord.ext import commands
from discord.ui import View, Button

# Бот берет токен из настроек Render (Environment Variables)
TOKEN = os.getenv('BOT_TOKEN')

URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"
ADMIN_CHANNEL_ID = 1216754939616039014
ROLE_ID = 1259828977942528111

# Кнопки для админа
class AdminAction(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def ok(self, inter: discord.Interaction, btn):
        m = inter.guild.get_member(int(self.uid))
        if m:
            role = inter.guild.get_role(ROLE_ID)
            await m.add_roles(role)
            await inter.response.send_message(f"✅ Участник <@{self.uid}> принят!", ephemeral=True)
        else:
            await inter.response.send_message("❌ Участник не найден на сервере", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.red)
    async def no(self, inter: discord.Interaction, btn):
        await inter.response.send_message("❌ Анкета отклонена", ephemeral=True)

# Вечная кнопка регистрации для игроков
class PersistentView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_start_fixed")
    async def start(self, inter: discord.Interaction, btn):
        link = f"{URL_SAYTA}?uid={inter.user.id}"
        v = View().add_item(Button(label="Открыть форму", url=link))
        await inter.response.send_message("Ваша ссылка для заполнения:", view=v, ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(PersistentView())

bot = MyBot()

@bot.command()
async def установка(ctx):
    await ctx.send("**Регистрация**\nНажмите кнопку ниже, чтобы подать заявку:", view=PersistentView())

@bot.event
async def on_message(msg):
    # Если пришла анкета в админ-канал
    if msg.channel.id == ADMIN_CHANNEL_ID and msg.author.bot and msg.embeds:
        try:
            footer = msg.embeds[0].footer.text
            if footer and "ID:" in footer:
                uid = footer.split("ID: ")[1].strip()
                # Создаем НОВОЕ сообщение с кнопками, чтобы не было ошибки 403
                await msg.channel.send(f"Управление анкетой игрока <@{uid}>:", view=AdminAction(uid))
        except Exception as e:
            print(f"Ошибка: {e}")
    await bot.process_commands(msg)

bot.run(TOKEN)
