import discord
import os
import asyncio
from discord.ext import commands
from discord.ui import View
from aiohttp import web

# --- НАСТРОЙКИ ---
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038
ROLE_ID = 1259813357763170394
LOG_CHANNEL_ID = 1216754939616039014
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request): return web.Response(text="Бот активен")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# --- КНОПКИ В ЧАТЕ ОТКАЗА ---
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
            role = guild.get_role(ROLE_ID)
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Роль выдана! Удаление чата через 3 сек...")
            await asyncio.sleep(3)
            await interaction.channel.delete()

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger)
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        await interaction.channel.delete()

# --- КНОПКИ ПРОВЕРКИ ---
class AdminReviewView(View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        member = interaction.guild.get_member(self.target_user_id)
        if member:
            role = interaction.guild.get_role(ROLE_ID)
            await member.add_roles(role)
            await interaction.response.edit_message(content=f"✅ **ОДОБРЕНО** для <@{self.target_user_id}>", view=None)

    @discord.ui.button(label="Отказать (Чат) ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        global deny_counter
        deny_counter += 1
        member = interaction.guild.get_member(self.target_user_id)
        if not member: return
        
        channel_name = f"обсуждение-отказа-{deny_counter:04d}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await interaction.guild.create_text_channel(name=channel_name, overwrites=overwrites)
        await channel.send(f"👋 <@{self.target_user_id}>, Обсуждение отказа {deny_counter:04d}", view=ChatControlView(self.target_user_id))
        await interaction.response.edit_message(content=f"❌ **ОТКАЗАНО**. Чат: {channel.mention}", view=None)

# --- ГЛАВНЫЙ БОТ ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def on_message(self, message):
        # Если сообщение пришло от вебхука в канал логов
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                # Извлекаем ID из текста "ID:123..."
                user_id = int(message.content.split("ID:")[-1].strip())
                # Прикрепляем кнопки к сообщению вебхука
                await message.edit(view=AdminReviewView(user_id))
            except:
                pass
        await self.process_commands(message)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        # Важно: тут мы не можем заранее знать UID того, кто нажмет, 
        # поэтому используем специальную кнопку, которая подставит UID в ответном сообщении
        view = View(timeout=None)
        button = discord.ui.Button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="start_reg")
        
        async def button_callback(interaction):
            personal_link = f"{URL_SAYTA}?uid={interaction.user.id}"
            link_view = View()
            link_view.add_item(discord.ui.Button(label="Перейти к анкете", url=personal_link))
            await interaction.response.send_message("Нажми на кнопку ниже, чтобы открыть анкету со своим ID:", view=link_view, ephemeral=True)
        
        button.callback = button_callback
        view.add_item(button)
        await ctx.send("**Нажмите для получения ссылки на анкету:**", view=view)

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
