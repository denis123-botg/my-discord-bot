import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
from aiohttp import web
import asyncio
import sqlite3
import datetime
import time
import re
from typing import Dict, List, Optional

# ===== КОНФИГУРАЦИЯ =====
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN не задан")

GUILD_ID = int(os.environ.get("GUILD_ID", 0)) or None
ADMIN_CHANNEL_ID = int(os.environ.get("ADMIN_CHANNEL_ID", 0))
ACTIVITY_WARNING_CHANNEL_ID = int(os.environ.get("ACTIVITY_WARNING_CHANNEL_ID", 0))
WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", 0))

# ID канала для подачи анкеты (только для кандидатов)
ANKETA_CHANNEL_ID = 1495026945069682882

ROLE_CANDIDATE = "Кандидат"
ROLE_PLAYER = "Игрок"
ROLE_REGISTERED = "Зарегистрирован"

# ===== БАЗА ДАННЫХ =====
db = sqlite3.connect("sirion_hub.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS mods (
    user_id INTEGER PRIMARY KEY,
    can_moderate BOOLEAN DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS member_activity (
    user_id INTEGER PRIMARY KEY,
    last_message_time INTEGER,
    warned_time INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_links (
    user_id INTEGER PRIMARY KEY,
    link TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cleanup_jobs (
    channel_id INTEGER PRIMARY KEY,
    delete_after_seconds INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS welcome_settings (
    channel_id INTEGER,
    message_text TEXT,
    embed_title TEXT,
    embed_description TEXT,
    embed_color TEXT
)
""")

db.commit()

# ===== ФУНКЦИИ БАЗЫ ДАННЫХ =====
def get_config(key, default=None):
    cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

def set_config(key, value):
    cursor.execute("REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    db.commit()

def is_mod(user_id: int) -> bool:
    cursor.execute("SELECT can_moderate FROM mods WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row is not None and row[0] == 1

def add_mod(user_id: int):
    cursor.execute("REPLACE INTO mods (user_id, can_moderate) VALUES (?, 1)", (user_id,))
    db.commit()

def remove_mod(user_id: int):
    cursor.execute("DELETE FROM mods WHERE user_id = ?", (user_id,))
    db.commit()

def get_all_mods():
    cursor.execute("SELECT user_id FROM mods WHERE can_moderate = 1")
    return [row[0] for row in cursor.fetchall()]

def parse_time(time_str: str) -> int:
    time_str = time_str.lower().strip()
    if time_str.endswith('с'):
        return int(time_str[:-1])
    elif time_str.endswith('м'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('ч'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('д'):
        return int(time_str[:-1]) * 86400
    else:
        return int(time_str) * 60

def format_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} секунд"
    elif seconds < 3600:
        return f"{seconds // 60} минут"
    elif seconds < 86400:
        return f"{seconds // 3600} часов"
    else:
        return f"{seconds // 86400} дней"

def get_welcome_settings():
    cursor.execute("SELECT channel_id, message_text, embed_title, embed_description, embed_color FROM welcome_settings LIMIT 1")
    row = cursor.fetchone()
    if row:
        return {
            "channel_id": row[0],
            "message_text": row[1],
            "embed_title": row[2],
            "embed_description": row[3],
            "embed_color": row[4]
        }
    return None

def set_welcome_settings(channel_id: int, message_text: str = None, embed_title: str = None, embed_description: str = None, embed_color: str = None):
    cursor.execute("DELETE FROM welcome_settings")
    cursor.execute("INSERT INTO welcome_settings (channel_id, message_text, embed_title, embed_description, embed_color) VALUES (?, ?, ?, ?, ?)",
                   (channel_id, message_text, embed_title, embed_description, embed_color))
    db.commit()

# ===== БОТ =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class SirionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="s!", intents=intents)

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        
        self.loop.create_task(self.start_web_server())
        self.check_activity.start()
        self.auto_cleanup_loop.start()
        print("✅ Бот готов")

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="OK"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 10000)
        await site.start()
        print("🌐 Веб-сервер на порту 10000")

    @tasks.loop(hours=1)
    async def check_activity(self):
        guild = self.guilds[0] if self.guilds else None
        if not guild:
            return
        now = time.time()
        for member in guild.members:
            if member.bot:
                continue
            cursor.execute("SELECT last_message_time, warned_time FROM member_activity WHERE user_id = ?", (member.id,))
            row = cursor.fetchone()
            last_time = row[0] if row else 0
            warned_time = row[1] if row else 0

            if now - last_time > 6 * 86400:
                if warned_time == 0 or now - warned_time > 86400:
                    channel = self.get_channel(ACTIVITY_WARNING_CHANNEL_ID)
                    if channel:
                        view = discord.ui.View()
                        button = discord.ui.Button(label="Я тут! 🎮", custom_id=f"imhere_{member.id}", style=discord.ButtonStyle.primary)
                        view.add_item(button)
                        await channel.send(f"{member.mention}, ты давно не писал! Нажми кнопку, чтобы остаться.", view=view)
                        cursor.execute("REPLACE INTO member_activity (user_id, last_message_time, warned_time) VALUES (?, ?, ?)",
                                       (member.id, last_time, now))
                        db.commit()
            
            if warned_time and now - warned_time > 86400 and now - last_time > 7 * 86400:
                await member.kick(reason="Неактивность более 7 дней")
                cursor.execute("DELETE FROM member_activity WHERE user_id = ?", (member.id,))
                db.commit()

    @check_activity.before_loop
    async def before_check_activity(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=30)
    async def auto_cleanup_loop(self):
        cursor.execute("SELECT channel_id, delete_after_seconds FROM cleanup_jobs")
        jobs = cursor.fetchall()
        for channel_id, seconds in jobs:
            channel = self.get_channel(channel_id)
            if channel:
                cutoff = time.time() - seconds
                try:
                    async for message in channel.history(limit=None, after=datetime.datetime.fromtimestamp(cutoff)):
                        if not message.pinned and message.created_at.timestamp() < cutoff:
                            await message.delete()
                except Exception as e:
                    print(f"Ошибка очистки {channel_id}: {e}")

bot = SirionBot()

async def update_channel_visibility(member: discord.Member, is_candidate: bool):
    anketa_channel = bot.get_channel(ANKETA_CHANNEL_ID)
    if anketa_channel:
        if is_candidate:
            await anketa_channel.set_permissions(member, read_messages=True)
        else:
            await anketa_channel.set_permissions(member, overwrite=None)

async def send_welcome_message(member: discord.Member):
    settings = get_welcome_settings()
    if not settings:
        return
    
    channel = bot.get_channel(settings["channel_id"])
    if not channel:
        return
    
    if settings.get("message_text"):
        text = settings["message_text"].replace("{user}", member.name).replace("{user_mention}", member.mention)
        await channel.send(text)
    
    if settings.get("embed_title") or settings.get("embed_description"):
        color = int(settings["embed_color"], 16) if settings.get("embed_color") else 0x00ff00
        embed = discord.Embed(
            title=settings["embed_title"].replace("{user}", member.name) if settings.get("embed_title") else None,
            description=settings["embed_description"].replace("{user}", member.name) if settings.get("embed_description") else None,
            color=color
        )
        await channel.send(embed=embed)

# ===== СОБЫТИЯ =====
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен на {len(bot.guilds)} серверах")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    cursor.execute("REPLACE INTO member_activity (user_id, last_message_time, warned_time) VALUES (?, ?, 0)",
                   (message.author.id, int(time.time())))
    db.commit()
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    await send_welcome_message(member)
    
    anketa_mode = get_config("anketa_mode", "off")
    
    if anketa_mode == "on":
        role = discord.utils.get(member.guild.roles, name=ROLE_CANDIDATE)
        if role:
            await member.add_roles(role)
            await update_channel_visibility(member, True)
        
        unique_link = f"https://ваш-сайт.ru/anketa?discord_id={member.id}"
        cursor.execute("REPLACE INTO user_links (user_id, link) VALUES (?, ?)", (member.id, unique_link))
        db.commit()
        
        try:
            await member.send(f"📝 Добро пожаловать! Заполните анкету по ссылке:\n{unique_link}")
        except:
            pass
    else:
        player_role = discord.utils.get(member.guild.roles, name=ROLE_PLAYER)
        registered_role = discord.utils.get(member.guild.roles, name=ROLE_REGISTERED)
        if player_role:
            await member.add_roles(player_role)
        if registered_role:
            await member.add_roles(registered_role)
        await update_channel_visibility(member, False)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    
    custom_id = interaction.data.get("custom_id", "")
    
    if custom_id.startswith("imhere_"):
        user_id = int(custom_id.split("_")[1])
        if interaction.user.id == user_id:
            cursor.execute("UPDATE member_activity SET warned_time = 0, last_message_time = ? WHERE user_id = ?",
                           (int(time.time()), user_id))
            db.commit()
            await interaction.response.send_message("✅ Рады, что ты с нами!", ephemeral=True)
            await interaction.message.delete()
        else:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
        return
    
    if custom_id.startswith("accept_"):
        user_id = int(custom_id.split("_")[1])
        member = interaction.guild.get_member(user_id)
        if member:
            candidate_role = discord.utils.get(interaction.guild.roles, name=ROLE_CANDIDATE)
            player_role = discord.utils.get(interaction.guild.roles, name=ROLE_PLAYER)
            registered_role = discord.utils.get(interaction.guild.roles, name=ROLE_REGISTERED)
            
            if candidate_role and candidate_role in member.roles:
                await member.remove_roles(candidate_role)
            if player_role:
                await member.add_roles(player_role)
            if registered_role:
                await member.add_roles(registered_role)
            
            await update_channel_visibility(member, False)
            
            await interaction.response.send_message(f"✅ Анкета {member.display_name} принята.", ephemeral=True)
            try:
                await member.send("🎉 Ваша анкета одобрена! Добро пожаловать на сервер.")
            except:
                pass
        return
    
    if custom_id.startswith("reject_"):
        user_id = int(custom_id.split("_")[1])
        member = interaction.guild.get_member(user_id)
        if member:
            category = discord.utils.get(interaction.guild.categories, name="Разбор отказов")
            if not category:
                category = await interaction.guild.create_category("Разбор отказов")
            
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            channel = await category.create_text_channel(f"отказ-{member.name}", overwrites=overwrites)
            await channel.send(f"{member.mention}, {interaction.user.mention}, обсуждение причины отказа.")
            await interaction.response.send_message(f"✅ Создан чат {channel.mention}", ephemeral=True)
        return

# ===== СЛЭШ-КОМАНДЫ =====
def mod_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator or is_mod(interaction.user.id):
            return True
        await interaction.response.send_message("❌ У вас нет прав", ephemeral=True)
        return False
    return app_commands.check(predicate)

# ===== 1. РЕЖИМ АНКЕТ (ОДНА КОМАНДА) =====
@bot.tree.command(name="режим_анкет", description="Включить/выключить/статус режима анкет")
@app_commands.describe(действие="on - включить, off - выключить, status - статус")
@mod_only()
async def anketa_mode(interaction: discord.Interaction, действие: str):
    if действие.lower() == "on":
        set_config("anketa_mode", "on")
        embed = discord.Embed(title="✅ Режим анкет ВКЛЮЧЁН", description="Новые участники получают роль **Кандидат**", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif действие.lower() == "off":
        set_config("anketa_mode", "off")
        embed = discord.Embed(title="✅ Режим анкет ВЫКЛЮЧЕН", description="Новые участники сразу получают роли **Игрок** и **Зарегистрирован**", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif действие.lower() == "status":
        current = get_config("anketa_mode", "off")
        status_text = "ВКЛЮЧЁН" if current == "on" else "ВЫКЛЮЧЕН"
        color = discord.Color.green() if current == "on" else discord.Color.red()
        embed = discord.Embed(title="📋 Статус режима анкет", description=f"Режим анкет **{status_text}**", color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Используйте `on`, `off` или `status`", ephemeral=True)

# ===== 2. КНОПКА АНКЕТЫ =====
@bot.tree.command(name="кнопка_анкеты", description="Отправить сообщение с кнопкой для заполнения анкеты")
@app_commands.describe(ссылка="Ссылка на сайт с анкетой")
@mod_only()
async def anketa_button(interaction: discord.Interaction, ссылка: str):
    embed = discord.Embed(title="📝 Заполните анкету", description="Нажмите на кнопку ниже", color=discord.Color.blue())
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="📋 Заполнить анкету", url=ссылка, style=discord.ButtonStyle.link))
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Сообщение отправлено в <#{WELCOME_CHANNEL_ID}>", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден", ephemeral=True)

# ===== 3. ПРИВЕТСТВИЕ (ОДНА КОМАНДА) =====
@bot.tree.command(name="приветствие", description="Настройка приветственного сообщения")
@app_commands.describe(
    канал="Канал для приветствий",
    текст="Текст сообщения (используйте {user} или {user_mention})",
    заголовок="Заголовок Embed",
    описание="Описание Embed",
    цвет="Цвет Embed (HEX)"
)
@mod_only()
async def welcome(interaction: discord.Interaction, канал: discord.TextChannel, текст: str = None, заголовок: str = None, описание: str = None, цвет: str = None):
    color_hex = None
    if цвет:
        цвет = цвет.replace("#", "")
        if len(цвет) == 6 and all(c in "0123456789ABCDEFabcdef" for c in цвет):
            color_hex = цвет
        else:
            await interaction.response.send_message("❌ Неверный формат цвета! Используйте #00FF00", ephemeral=True)
            return
    
    set_welcome_settings(канал.id, текст, заголовок, описание, color_hex)
    embed = discord.Embed(title="✅ Настройки приветствия сохранены!", description=f"**Канал:** {канал.mention}", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="приветствие_откл", description="Отключить приветственное сообщение")
@mod_only()
async def welcome_off(interaction: discord.Interaction):
    cursor.execute("DELETE FROM welcome_settings")
    db.commit()
    await interaction.response.send_message("❌ Приветствие отключено", ephemeral=True)

# ===== 4. ОЧИСТИТЬ =====
@bot.tree.command(name="очистить", description="Удалить сообщения")
@app_commands.describe(amount="Количество (1-100)")
@mod_only()
async def clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ От 1 до 100", ephemeral=True)
        return
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"🗑 Удалено {amount} сообщений", ephemeral=True)

# ===== 5. АВТООЧИСТКА =====
@bot.tree.command(name="автоочистка", description="Настройка автоочистки")
@app_commands.describe(channel="Канал", время="30с, 5м, 2ч, 1д или 0")
@mod_only()
async def auto_cleanup(interaction: discord.Interaction, channel: discord.TextChannel, время: str):
    try:
        if время.lower() == "0" or время.lower() == "off":
            cursor.execute("DELETE FROM cleanup_jobs WHERE channel_id = ?", (channel.id,))
            db.commit()
            await interaction.response.send_message(f"⏹ Автоочистка в {channel.mention} отключена", ephemeral=True)
            return
        
        seconds = parse_time(время)
        time_text = format_time(seconds)
        cursor.execute("REPLACE INTO cleanup_jobs (channel_id, delete_after_seconds) VALUES (?, ?)", (channel.id, seconds))
        db.commit()
        await interaction.response.send_message(f"⏲ Автоочистка в {channel.mention}: удаление сообщений старше **{time_text}**", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ Неверный формат! Примеры: `30с`, `5м`, `2ч`, `1д`", ephemeral=True)

# ===== 6. ДОСТУП (ОДНА КОМАНДА) =====
@bot.tree.command(name="доступ", description="Управление модераторами бота")
@app_commands.describe(действие="add - добавить, remove - удалить, list - список", пользователь="Пользователь")
@mod_only()
async def access(interaction: discord.Interaction, действие: str, пользователь: discord.User = None):
    действие = действие.lower()
    
    if действие == "add":
        if not пользователь:
            await interaction.response.send_message("❌ Укажите пользователя: `/доступ add @user`", ephemeral=True)
            return
        add_mod(пользователь.id)
        await interaction.response.send_message(f"✅ {пользователь.mention} добавлен", ephemeral=True)
    
    elif действие == "remove":
        if not пользователь:
            await interaction.response.send_message("❌ Укажите пользователя: `/доступ remove @user`", ephemeral=True)
            return
        remove_mod(пользователь.id)
        await interaction.response.send_message(f"❌ {пользователь.mention} удалён", ephemeral=True)
    
    elif действие == "list":
        mods = get_all_mods()
        if not mods:
            await interaction.response.send_message("📋 Список модераторов пуст", ephemeral=True)
            return
        mod_mentions = [f"• {interaction.guild.get_member(mid).mention if interaction.guild.get_member(mid) else f'<@{mid}>'}" for mid in mods]
        embed = discord.Embed(title="🛡️ Модераторы бота", description="\n".join(mod_mentions), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    else:
        await interaction.response.send_message("❌ Используйте `add`, `remove` или `list`", ephemeral=True)

# ===== 7. PING =====
@bot.tree.command(name="ping", description="Проверка")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    bot.run(TOKEN)