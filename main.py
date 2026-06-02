import discord
import os
import asyncio
import re
import sqlite3
from typing import Union
from datetime import datetime, timezone, timedelta
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
from aiohttp import web

# ================= НАСТРОЙКИ (ID) =================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = 1118970574887211038

# Роли
ROLE_CANDIDATE = 1259813357763170394     # КАНДИДАТ
ROLE_PLAYER = 1506372814477988002        # ИГРОК
ROLE_REGISTERED = 1259828977942528111     # ЗАРЕГИСТРИРОВАН
ROLE_MODERATOR = 1182036238337855600      # МОДЕРАТОР

# Каналы
LOG_CHANNEL_ID = 1216754939616039014      
CATEGORY_DENY = 1216754938684903424       
ACTIVITY_CHECK_CHANNEL_ID = 1506694190057263325 
URL_SAYTA = "https://sirionhub.online/"   

deny_counter = 0

# ================= ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =================
conn = sqlite3.connect("activity.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        user_id INTEGER PRIMARY KEY,
        last_active TEXT,
        warned INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff_access (
        target_id INTEGER PRIMARY KEY,
        type TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_purge (
        channel_id INTEGER PRIMARY KEY,
        time_value INTEGER,
        time_type TEXT
    )
""")

# Таблица для сохранения режима анкеты (1 - включен, 0 - выключен)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value INTEGER
    )
""")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('survey_mode', 1)")
conn.commit()

def get_survey_mode() -> bool:
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'survey_mode'")
    row = cursor.fetchone()
    return bool(row[0]) if row else True

def set_survey_mode(enabled: bool):
    cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('survey_mode', ?)", (1 if enabled else 0,))
    conn.commit()

def update_user_activity(user_id, dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    cursor.execute("INSERT OR REPLACE INTO activity (user_id, last_active, warned) VALUES (?, ?, 0)", 
                   (user_id, dt.replace(tzinfo=None).isoformat()))
    conn.commit()

def check_staff_permission(user: discord.Member) -> bool:
    if user.id == MY_ID: return True
    if user.guild_permissions.administrator: return True
    
    mod_role = user.guild.get_role(ROLE_MODERATOR)
    if mod_role and mod_role in user.roles: return True
    
    cursor.execute("SELECT target_id FROM staff_access")
    allowed_ids = [row[0] for row in cursor.fetchall()]
    
    if user.id in allowed_ids: return True
    for role in user.roles:
        if role.id in allowed_ids: return True
        
    return False

# ================= ВЕБ-СЕРВЕР ДЛЯ RENDER =================
async def handle(request): return web.Response(text="Work")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= ЛОГИКА ДЛЯ РАБОТЫ КНОПОК ПРИНЯТИЯ И ОТКАЗА =================
async def process_approve(interaction: discord.Interaction, target_id: int):
    member = interaction.guild.get_member(target_id)
    if member:
        r_play = interaction.guild.get_role(ROLE_PLAYER)
        r_reg = interaction.guild.get_role(ROLE_REGISTERED)
        r_cand = interaction.guild.get_role(ROLE_CANDIDATE)
        
        roles_to_add = [r for r in [r_play, r_reg] if r]
        if roles_to_add: await member.add_roles(*roles_to_add)
        if r_cand: await member.remove_roles(r_cand)
        
        update_user_activity(target_id)
        return True
    return False

async def process_deny(interaction: discord.Interaction, target_id: int):
    global deny_counter
    guild = interaction.guild
    member = guild.get_member(target_id)
    if not member: 
        return None

    deny_counter += 1
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_role(ROLE_MODERATOR): discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    category = guild.get_channel(CATEGORY_DENY)
    ch = await guild.create_text_channel(f"отказ-{deny_counter}", category=category, overwrites=overwrites)
    await ch.send(f"⚠️ <@{target_id}>, ваша анкета отклонена. Ожидайте модератора в этом канале.", view=DenyChatView())
    return ch

# ================= VIEWS =================
class AliveButtonView(View):
    def __init__(self, target_id):
        super().__init__(timeout=None)
        self.target_id = target_id

    @discord.ui.button(label="Я тут! 🎮", style=discord.ButtonStyle.green, custom_id="alive_btn")
    async def alive_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Эта кнопка предназначена не для вас!", ephemeral=True)
            return
        update_user_activity(interaction.user.id)
        await interaction.response.send_message("✅ Ваша активность подтверждена!", ephemeral=True)
        await interaction.message.delete()

class DenyChatView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger, custom_id="del_ch_final")
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if check_staff_permission(interaction.user):
            await interaction.response.send_message("Удаление чата через 2 секунды...")
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ У вас нет прав на удаление этого канала.", ephemeral=True)

class AdminReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_target_id(self, message_content):
        match = re.search(r"ID:(\d+)", message_content)
        return int(match.group(1)) if match else None

    @discord.ui.button(label="Принять ✅", style=discord.ButtonStyle.green, custom_id="admin_approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff_permission(interaction.user):
            await interaction.response.send_message("❌ У вас нет доступа к управлению анкетами.", ephemeral=True)
            return
        target_id = self.get_target_id(interaction.message.content)
        if not target_id:
            await interaction.response.send_message("❌ Не удалось определить ID пользователя.", ephemeral=True)
            return

        success = await process_approve(interaction, target_id)
        if success:
            await interaction.response.edit_message(content=interaction.message.content + f"\n\n🟢 **СТАТУС: ОДОБРЕНО** модератором <@{interaction.user.id}>.", view=None)
        else:
            await interaction.response.send_message("❌ Пользователь не найден на сервере.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger, custom_id="admin_deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff_permission(interaction.user):
            await interaction.response.send_message("❌ У вас нет доступа к управлению анкетами.", ephemeral=True)
            return
        target_id = self.get_target_id(interaction.message.content)
        if not target_id:
            await interaction.response.send_message("❌ Не удалось определить ID пользователя.", ephemeral=True)
            return

        ch = await process_deny(interaction, target_id)
        if ch:
            await interaction.response.edit_message(content=interaction.message.content + f"\n\n🔴 **СТАТУС: ОТКЛОНЕНО** модератором <@{interaction.user.id}>.\n💬 Чат разбора: {ch.mention}", view=None)
        else:
            await interaction.response.send_message("❌ Пользователь покинул сервер.", ephemeral=True)

class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_v12")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View()
        v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Твоя персональная ссылка на анкету:", view=v, ephemeral=True)
