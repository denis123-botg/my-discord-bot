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
ROLE_ID = 1259813357763170394  # Роль, которую выдаем
LOG_CHANNEL_ID = 1216754939616039014  # Канал, куда приходят анкеты
URL_SAYTA = "https://denis123-botg.github.io/sirion_forms/"

deny_counter = 0

# ================= ВЕБ-СЕРВЕР (ДЛЯ RENDER) =================
async def handle(request): 
    return web.Response(text="Бот активен и готов к работе!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

# ================= КНОПКИ В ЧАТЕ ОТКАЗА =================
class ChatControlView(View):
        @discord.ui.button(label="Выдать роль ✅", style=discord.ButtonStyle.green)
    async def give_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        
        if member:
            role_to_give = guild.get_role(ROLE_ID)
            role_to_remove = guild.get_role(1259813357763170394) # ID роли кандидата

            await member.add_roles(role_to_give)
            if role_to_remove:
                await member.remove_roles(role_to_remove)
                
            await interaction.response.send_message("✅ Роль выдана, статус кандидата снят! Удаление чата...")
            await asyncio.sleep(5)
            await interaction.channel.delete()

# ================= КНОПКИ ПРОВЕРКИ АНКЕТЫ =================
class AdminReviewView(View):
    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID: return
        member = interaction.guild.get_member(self.target_user_id)
        
        if member:
            role_to_give = interaction.guild.get_role(ROLE_ID) # Роль игрока
            # Если роль кандидата — это ТА ЖЕ роль, что мы выдаем, то ничего удалять не надо.
            # НО, если у кандидата есть другая роль (например, "Кандидат"), укажи её ID ниже:
            role_to_remove_id = 1259813357763170394 # ЗАМЕНИ НА ID РОЛИ КАНДИДАТА
            role_to_remove = interaction.guild.get_role(role_to_remove_id)

            await member.add_roles(role_to_give) # Выдаем новую
            
            if role_to_remove:
                await member.remove_roles(role_to_remove) # Забираем старую
            
            await interaction.response.edit_message(content=f"✅ **ПРИНЯТ**: <@{self.target_user_id}>. Роли обновлены.", view=None)
        else:
            await interaction.response.send_message("Ошибка: Игрок покинул сервер.", ephemeral=True)


# ================= КНОПКА УСТАНОВКИ =================
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="persistent_reg_button")
    async def start_reg(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Генерируем личную ссылку с UID
        personal_url = f"{URL_SAYTA}?uid={interaction.user.id}"
        
        # Кнопка-ссылка, которая появится только для нажавшего
        link_view = View()
        link_view.add_item(discord.ui.Button(label="Открыть форму", url=personal_url))
        
        await interaction.response.send_message(
            "Твоя персональная ссылка (действует только для тебя):", 
            view=link_view, 
            ephemeral=True
        )

# ================= ОСНОВНОЙ КЛАСС БОТА =================
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Регистрируем View, чтобы кнопки работали вечно
        self.add_view(RegistrationView())

    async def on_ready(self):
        print(f"✅ Бот {self.user} запущен и готов!")

    async def on_message(self, message):
        # Слушаем только канал логов и только сообщения от вебхуков
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                # Ищем ID пользователя в тексте сообщения
                match = re.search(r"ID:(\d+)", message.content)
                if match:
                    user_id = int(match.group(1))
                    content = message.content
                    
                    # 1. Удаляем сообщение вебхука (нужно право 'Manage Messages')
                    await message.delete()
                    
                    # 2. Переотправляем его от имени бота с кнопками
                    view = AdminReviewView(user_id)
                    await message.channel.send(content=content, view=view)
            except Exception as e:
                print(f"Ошибка при обработке анкеты: {e}")
        
        await self.process_commands(message)

# ================= ЗАПУСК =================
bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID:
        await ctx.send("**Нажмите на кнопку ниже, чтобы начать регистрацию:**", view=RegistrationView())

async def main():
    await start_server()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
