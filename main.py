import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
from aiohttp import web
import asyncio
import sqlite3
import json
import datetime
import time
from typing import Optional, Dict, List

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

auto_cleanup_config: Dict[int, int] = {}

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

# ===== БОТ =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True

class SirionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="s!", intents=intents)

    async def setup_hook(self):
        # Синхронизация команд
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        
        # Запуск веб-сервера
        self.loop.create_task(self.start_web_server())
        
        # Запуск задач
        self.check_activity.start()
        self.auto_cleanup_loop.start()
        
        print("✅ Бот готов, все задачи запущены")

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get("/", self.health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 10000)
        await site.start()
        print("🌐 Веб-сервер на порту 10000")

    async def health_check(self, request):
        return web.Response(text="OK", status=200)

    @tasks.loop(hours=1)
    async def check_activity(self):
        """Проверка активности игроков"""
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
        """Автоочистка каналов"""
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

# ===== ФУНКЦИЯ ДЛЯ СКРЫТИЯ/ПОКАЗА КАНАЛОВ =====
async def update_channel_visibility(member: discord.Member, is_candidate: bool):
    """Скрывает или показывает каналы в зависимости от роли"""
    anketa_channel = bot.get_channel(ANKETA_CHANNEL_ID)
    if anketa_channel:
        if is_candidate:
            # Кандидат: видит только канал для анкеты
            await anketa_channel.set_permissions(member, read_messages=True)
        else:
            # Игрок: убираем специальные права (возвращаем стандартные)
            await anketa_channel.set_permissions(member, overwrite=None)

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
    """Приём новых участников"""
    anketa_mode = get_config("anketa_mode", "off")
    
    if anketa_mode == "on":
        # Режим анкет: выдаём роль Кандидат
        role = discord.utils.get(member.guild.roles, name=ROLE_CANDIDATE)
        if role:
            await member.add_roles(role)
            # Скрываем все каналы кроме канала для анкеты
            await update_channel_visibility(member, True)
        
        # Генерация персональной ссылки
        unique_link = f"https://ваш-сайт.ru/anketa?discord_id={member.id}"
        cursor.execute("REPLACE INTO user_links (user_id, link) VALUES (?, ?)", (member.id, unique_link))
        db.commit()
        
        try:
            await member.send(f"📝 Добро пожаловать! Заполните анкету по ссылке:\n{unique_link}")
        except:
            pass
    else:
        # Режим без анкет: выдаём роли сразу
        player_role = discord.utils.get(member.guild.roles, name=ROLE_PLAYER)
        registered_role = discord.utils.get(member.guild.roles, name=ROLE_REGISTERED)
        if player_role:
            await member.add_roles(player_role)
        if registered_role:
            await member.add_roles(registered_role)
        
        # Показываем все каналы
        await update_channel_visibility(member, False)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
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
                
                # Показываем все каналы игроку
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
        await interaction.response.send_message("❌ У вас нет прав на использование этой команды.", ephemeral=True)
        return False
    return app_commands.check(predicate)

@bot.tree.command(name="установка_анкеты", description="Включить обязательную проверку анкет")
@mod_only()
async def setup_ankety(interaction: discord.Interaction):
    set_config("anketa_mode", "on")
    await interaction.response.send_message("✅ Режим анкет включён. Новые участники получают роль `Кандидат` и видят только канал для анкеты.", ephemeral=True)

@bot.tree.command(name="убрать_анкету", description="Отключить проверку анкет")
@mod_only()
async def remove_anketu(interaction: discord.Interaction):
    set_config("anketa_mode", "off")
    await interaction.response.send_message("✅ Режим анкет выключен. Новые участники сразу получают `Игрок` и `Зарегистрирован`.", ephemeral=True)

@bot.tree.command(name="сообщение_анкеты", description="Отправить приветственный пост с кнопкой на сайт")
@mod_only()
async def anketa_message(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📝 Заполните анкету",
        description="Нажмите на кнопку ниже, чтобы перейти на сайт и заполнить заявку.",
        color=discord.Color.blue()
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="📋 Заполнить анкету", url="https://ваш-сайт-анкеты.ru"))
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Сообщение отправлено!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден. Проверьте WELCOME_CHANNEL_ID", ephemeral=True)

@bot.tree.command(name="очистить", description="Удалить указанное количество сообщений")
@app_commands.describe(amount="Количество сообщений (1-100)")
@mod_only()
async def clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Укажите число от 1 до 100.", ephemeral=True)
        return
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"🗑 Удалено {amount} сообщений.", ephemeral=True)

@bot.tree.command(name="автоочистка", description="Настройка автоочистки в канале")
@app_commands.describe(channel="Канал", minutes="Через сколько минут удалять сообщения (0 = отключить)")
@mod_only()
async def auto_cleanup(interaction: discord.Interaction, channel: discord.TextChannel, minutes: int):
    if minutes <= 0:
        cursor.execute("DELETE FROM cleanup_jobs WHERE channel_id = ?", (channel.id,))
        db.commit()
        await interaction.response.send_message(f"⏹ Автоочистка в {channel.mention} отключена.", ephemeral=True)
    else:
        seconds = minutes * 60
        cursor.execute("REPLACE INTO cleanup_jobs (channel_id, delete_after_seconds) VALUES (?, ?)", (channel.id, seconds))
        db.commit()
        await interaction.response.send_message(f"⏲ Настроена автоочистка в {channel.mention}: удаление сообщений старше {minutes} минут.", ephemeral=True)

@bot.tree.command(name="доступ", description="Управление модераторами бота")
@app_commands.describe(action="add или remove", user="Пользователь")
@mod_only()
async def access(interaction: discord.Interaction, action: str, user: discord.User):
    if action.lower() == "add":
        add_mod(user.id)
        await interaction.response.send_message(f"✅ {user.mention} теперь может управлять ботом.", ephemeral=True)
    elif action.lower() == "remove":
        remove_mod(user.id)
        await interaction.response.send_message(f"❌ {user.mention} больше не имеет прав.", ephemeral=True)
    else:
        await interaction.response.send_message("Используйте `add` или `remove`", ephemeral=True)

@bot.tree.command(name="ping", description="Проверка работы бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Задержка: {round(bot.latency * 1000)}ms")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    bot.run(TOKEN)