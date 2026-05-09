import discord
import os
import asyncio
import re
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394  # Роль игрока (выдаем)
CANDIDATE_ROLE_ID = 1259813357763170394 # Роль кандидата (забираем)
LOG_CHANNEL_ID = 1216754939616039014
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# ================= ВЕБ-СЕРВЕР =================
async def handle(request): 
    return web.Response(text="Бот активен!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# ================= КНОПКИ В ЧАТЕ ОТКАЗА =================
class ChatControlView(View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Выдать роль ✅", style=discord.ButtonStyle.green)
    async def give_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        
        if member:
            role_to_give = guild.get_role(ROLE_ID)
            role_to_remove = guild.get_role(CANDIDATE_ROLE_ID)

            await member.add_roles(role_to_give)
            if role_to_remove:
                await member.remove_roles(role_to_remove)
                
            await interaction.response.send_message("✅ Роль выдана, статус кандидата снят! Удаление чата...")
            await asyncio.sleep(5)
            await interaction.channel.delete()

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger)
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        await interaction.channel.delete()

# ================= КНОПКИ ПРОВЕРКИ АНКЕТЫ =================
class AdminReviewView(View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        member = interaction.guild.get_member(self.target_user_id)
        
        if member:
            role_to_give = interaction.guild.get_role(ROLE_ID)
            role_to_remove = interaction.guild.get_role(CANDIDATE_ROLE_ID)

            await member.add_roles(role_to_give)
            if role_to_remove:
                await member.remove_roles(role_to_remove)
            
            await interaction.response.edit_message(content=f"✅ **ПРИНЯТ**: <@{self.target_user_id}>. Кандидат снят.", view=None)
        else:
            await interaction.response.send_message("Ошибка: Игрок покинул сервер.", ephemeral=True)

    @discord.ui.button(label="Отказать (Чат) ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        global deny_counter
        deny_counter += 1
        member = interaction.guild.get_member(self.target_user_id)
        
        if not member: return await interaction.response.send_message("Пользователь не найден.", ephemeral=True)
        
        ch_name = f"обсуждение-отказа-{deny_counter:04d}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await interaction.guild.create_text_channel(name=ch_name, overwrites=overwrites)
        await channel.send(f"👋 <@{self.target_user_id}>, обсуждение отказа {deny_counter:04d}", view=ChatControlView(self.target_user_id))
        await interaction.response.edit_message(content=f"❌ **ОТКАЗАНО**. Чат: {channel.mention}", view=None)

# ================= КНОПКА УСТАНОВКИ =================
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="persistent_reg_button")
    async def start_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        personal_url = f"{URL_SAYTA}?uid={interaction.user.id}"
        link_view = View()
        link_view.add_item(discord.ui.Button(label="Открыть форму", url=personal_url))
        await interaction.response.send_message("Твоя ссылка:", view=link_view, ephemeral=True)

# ================= ОСНОВНОЙ КЛАСС БОТА =================
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(RegistrationView())

    async def on_message(self, message):
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                match = re.search(r"ID:(\d+)", message.content)
                if match:
                    user_id = int(match.group(1))
                    await message.delete()
                    await message.channel.send(content=message.content, view=AdminReviewView(user_id))
            except Exception as e:
                print(f"Ошибка: {e}")
        await self.process_commands(message)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Нажмите для регистрации:**", view=RegistrationView())

async def main():
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
