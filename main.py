import discord
import os
import asyncio
import re
from discord.ext import commands
from discord.ui import View, Button
from aiohttp import web

# ================= НАСТРОЙКИ (ID) =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038

# Роли
ROLE_CANDIDATE = 1259813357763170394     # КАНДИДАТ
ROLE_PLAYER = 1506372814477988002        # ИГРОК
ROLE_REGISTERED = 1259828977942528111     # ЗАРЕГИСТРИРОВАН (Добавлено обратно)

# Каналы
LOG_CHANNEL_ID = 1216754939616039014      
CATEGORY_DENY = 1216754938684903424       
URL_SAYTA = "https://sirionhub.online/"   

deny_counter = 0

# ================= ВЕБ-СЕРВЕР =================
async def handle(request): return web.Response(text="Work")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= VIEW: УДАЛЕНИЕ ЧАТА ОТКАЗА =================
class DenyChatView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger, custom_id="del_ch_final")
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == MY_ID or interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Удаление чата через 2 секунды...")
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ У вас нет прав на удаление этого канала.", ephemeral=True)

# ================= VIEW: ПРОВЕРКА АНКЕТЫ =================
class AdminReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_target_id(self, message_content):
        match = re.search(r"ID:(\d+)", message_content)
        return int(match.group(1)) if match else None

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green, custom_id="admin_approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID and not interaction.user.guild_permissions.administrator: 
            await interaction.response.send_message("❌ Доступно только администрации.", ephemeral=True)
            return
            
        target_id = self.get_target_id(interaction.message.content)
        if not target_id:
            await interaction.response.send_message("❌ Не удалось определить ID пользователя из анкеты.", ephemeral=True)
            return

        member = interaction.guild.get_member(target_id)
        if member:
            r_play = interaction.guild.get_role(ROLE_PLAYER)
            r_reg = interaction.guild.get_role(ROLE_REGISTERED) # Получаем роль зарегистрированного
            r_cand = interaction.guild.get_role(ROLE_CANDIDATE)
            
            # Собираем роли, которые нужно выдать (проверяя, что они существуют на сервере)
            roles_to_add = [r for r in [r_play, r_reg] if r]
            if roles_to_add: 
                await member.add_roles(*roles_to_add)
                
            if r_cand: 
                await member.remove_roles(r_cand)
            
            await interaction.response.edit_message(content=interaction.message.content + f"\n\n🟢 **СТАТУС: ОДОБРЕНО** администратором <@{interaction.user.id}>. Пользователю выданы роли <@&{ROLE_PLAYER}> и <@&{ROLE_REGISTERED}>.", view=None)
        else:
            await interaction.response.send_message("❌ Пользователь не найден на сервере.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger, custom_id="admin_deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != MY_ID and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Доступно только администрации.", ephemeral=True)
            return
            
        target_id = self.get_target_id(interaction.message.content)
        if not target_id:
            await interaction.response.send_message("❌ Не удалось определить ID пользователя.", ephemeral=True)
            return

        global deny_counter
        deny_counter += 1
        guild = interaction.guild
        member = guild.get_member(target_id)
        if not member: 
            await interaction.response.send_message("❌ Пользователь покинул сервер.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        category = guild.get_channel(CATEGORY_DENY)
        ch = await guild.create_text_channel(f"отказ-{deny_counter}", category=category, overwrites=overwrites)
        await ch.send(f"⚠️ <@{target_id}>, ваша анкета отклонена. Ожидайте администратора в этом канале.", view=DenyChatView())
        
        await interaction.response.edit_message(content=interaction.message.content + f"\n\n🔴 **СТАТУС: ОТКЛОНЕНО** администратором <@{interaction.user.id}>.\n💬 Чат разбора: {ch.mention}", view=None)

# ================= VIEW: АНКЕТА =================
class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_v12")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View()
        v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Твоя персональная ссылка на анкету (не делись ей с другими):", view=v, ephemeral=True)

# ================= BOT =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.add_view(RegistrationView())
        self.add_view(DenyChatView())
        self.add_view(AdminReviewView())
        
    async def on_member_join(self, m):
        r = m.guild.get_role(ROLE_CANDIDATE)
        if r: await m.add_roles(r)
        
    async def on_message(self, m):
        if m.channel.id == LOG_CHANNEL_ID and m.webhook_id:
            match = re.search(r"ID:(\d+)", m.content)
            if match:
                await m.delete()
                await m.channel.send(content=m.content, view=AdminReviewView())
        await self.process_commands(m)

bot = MyBot()

@bot.command()
async def установка(ctx):
    if ctx.author.id == MY_ID or ctx.author.guild_permissions.administrator: 
        await ctx.send("**Добро пожаловать в Сирион Хаб! Нажмите кнопку ниже, чтобы заполнить анкету игрока и получить доступ к серверу:**", view=RegistrationView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
