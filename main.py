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

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.environ.get("DISCORD_TOKEN")

# Проверка: если токен не найден — завершаем с ошибкой
if not TOKEN:
    print("❌ ОШИБКА: Переменная DISCORD_TOKEN не найдена в Environment!")
    print("Добавьте её в Render: Environment → DISCORD_TOKEN = ваш_токен")
    exit(1)

print(f"✅ Токен загружен из переменных окружения (длина: {len(TOKEN)})")

# Остальные переменные тоже через окружение
GUILD_ID = int(os.environ.get("GUILD_ID", 0)) or None
ADMIN_CHANNEL_ID = int(os.environ.get("ADMIN_CHANNEL_ID", 0))
ACTIVITY_WARNING_CHANNEL_ID = int(os.environ.get("ACTIVITY_WARNING_CHANNEL_ID", 0))
WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", 0))
WEBHOOK_LOG_URL = os.environ.get("WEBHOOK_LOG_URL", "")

# Роли (можно тоже вынести в окружение, но пока оставим)
ROLE_CANDIDATE = "Кандидат"
ROLE_PLAYER = "Игрок"
ROLE_REGISTERED = "Зарегистрирован"

# Настройки автоочистки (канал: (секунды, последняя очистка))
auto_cleanup_config: Dict[int, int] = {}

# ------------------ БАЗА ДАННЫХ ------------------
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

# ------------------ БОТ ------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True

class SirionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="s!", intents=intents)
        self.synced = False
        self.web_app = None
        self.web_runner = None

    async def setup_hook(self):
        if not self.synced:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
            self.synced = True
        self.loop.create_task(self.start_web_server())
        self.check_activity.start()
        self.process_webhook_logs.start()

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get("/", self.health_check)
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        site = web.TCPSite(self.web_runner, "0.0.0.0", 10000)
        await site.start()
        print("Веб-сервер запущен на порту 10000")

    async def health_check(self, request):
        return web.Response(text="OK", status=200)

    async def on_ready(self):
        print(f"Бот {self.user} готов!")
        await self.load_cleanup_jobs()

    async def load_cleanup_jobs(self):
        cursor.execute("SELECT channel_id, delete_after_seconds FROM cleanup_jobs")
        for channel_id, seconds in cursor.fetchall():
            auto_cleanup_config[channel_id] = seconds
            self.loop.create_task(self.auto_cleanup_loop(channel_id, seconds))

    async def auto_cleanup_loop(self, channel_id, seconds):
        await self.wait_until_ready()
        while True:
            channel = self.get_channel(channel_id)
            if channel:
                now = time.time()
                cutoff = now - seconds
                try:
                    async for message in channel.history(limit=None, after=datetime.datetime.fromtimestamp(cutoff)):
                        if message.pinned:
                            continue
                        if message.created_at.timestamp() < cutoff:
                            await message.delete()
                    print(f"Очистка {channel.name} завершена")
                except Exception as e:
                    print(f"Ошибка очистки {channel_id}: {e}")
            await asyncio.sleep(seconds // 2)

bot = SirionBot()

# ------------------ ДЕКОРАТОР ПРОВЕРКИ ПРАВ ------------------
def mod_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator or is_mod(interaction.user.id):
            return True
        await interaction.response.send_message("❌ У вас нет прав на использование этой команды.", ephemeral=True)
        return False
    return app_commands.check(predicate)

# ------------------ СЛЭШ-КОМАНДЫ ------------------
@bot.tree.command(name="установка_анкеты", description="Включить обязательную проверку анкет")
@mod_only()
async def setup_ankety(interaction: discord.Interaction):
    set_config("anketa_mode", "on")
    await interaction.response.send_message("✅ Режим анкет включён. Новые участники получают роль `Кандидат`.", ephemeral=True)

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
        await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)

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
@app_commands.describe(
    channel="Канал",
    minutes="Через сколько минут удалять сообщения (0 = отключить)"
)
@mod_only()
async def auto_cleanup(interaction: discord.Interaction, channel: discord.TextChannel, minutes: int):
    if minutes <= 0:
        cursor.execute("DELETE FROM cleanup_jobs WHERE channel_id = ?", (channel.id,))
        db.commit()
        if channel.id in auto_cleanup_config:
            del auto_cleanup_config[channel.id]
        await interaction.response.send_message(f"⏹ Автоочистка в {channel.mention} отключена.", ephemeral=True)
    else:
        seconds = minutes * 60
        cursor.execute("REPLACE INTO cleanup_jobs (channel_id, delete_after_seconds) VALUES (?, ?)", (channel.id, seconds))
        db.commit()
        auto_cleanup_config[channel.id] = seconds
        bot.loop.create_task(bot.auto_cleanup_loop(channel.id, seconds))
        await interaction.response.send_message(f"⏲ Настроена автоочистка в {channel.mention}: удаление сообщений старше {minutes} минут.", ephemeral=True)

@bot.tree.command(name="доступ", description="Управление модераторами бота")
@app_commands.describe(
    action="add или remove",
    user="Пользователь"
)
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

# ------------------ ОБРАБОТЧИК ВЕБХУКОВ (анкеты) ------------------
@tasks.loop(seconds=5)
async def process_webhook_logs():
    # В реальной реализации тут должен быть сбор данных с вашего сайта
    # Мы эмулируем: читаем из базы или очереди
    # Для демо: пропускаем, но структура готова
    pass

async def send_anketa_to_moderation(user_id: int, anketa_data: dict):
    """Вызывается из веб-сервера или парсера хуков"""
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if not admin_channel:
        return
    embed = discord.Embed(title="📄 Новая анкета", color=discord.Color.orange())
    embed.add_field(name="Пользователь", value=f"<@{user_id}>", inline=False)
    for k, v in anketa_data.items():
        embed.add_field(name=k, value=v[:1024], inline=False)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Принять ✅", custom_id=f"accept_{user_id}", style=discord.ButtonStyle.success))
    view.add_item(discord.ui.Button(label="Отказать ❌", custom_id=f"reject_{user_id}", style=discord.ButtonStyle.danger))
    await admin_channel.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    custom_id = interaction.data.get("custom_id", "")
    if custom_id.startswith("accept_"):
        user_id = int(custom_id.split("_")[1])
        guild = interaction.guild
        member = guild.get_member(user_id)
        if member:
            candidate_role = discord.utils.get(guild.roles, name=ROLE_CANDIDATE)
            player_role = discord.utils.get(guild.roles, name=ROLE_PLAYER)
            registered_role = discord.utils.get(guild.roles, name=ROLE_REGISTERED)
            if candidate_role and candidate_role in member.roles:
                await member.remove_roles(candidate_role)
            if player_role:
                await member.add_roles(player_role)
            if registered_role:
                await member.add_roles(registered_role)
            await interaction.response.send_message(f"✅ Анкета {member.display_name} принята.", ephemeral=True)
            try:
                await member.send("🎉 Ваша анкета одобрена! Добро пожаловать на сервер.")
            except:
                pass
    elif custom_id.startswith("reject_"):
        user_id = int(custom_id.split("_")[1])
        guild = interaction.guild
        member = guild.get_member(user_id)
        if member:
            # Создаём изолированный чат
            category = discord.utils.get(guild.categories, name="Разбор отказов")
            if not category:
                category = await guild.create_category("Разбор отказов")
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            channel = await category.create_text_channel(f"отказ-{member.name}", overwrites=overwrites)
            await channel.send(f"{member.mention}, {interaction.user.mention}, обсуждение причины отказа.")
            await interaction.response.send_message(f"✅ Создан чат {channel.mention}", ephemeral=True)

# ------------------ ПРИВЕТСТВИЕ НОВЫХ ------------------
@bot.event
async def on_member_join(member):
    anketa_mode = get_config("anketa_mode", "off")
    guild = member.guild
    if anketa_mode == "on":
        role = discord.utils.get(guild.roles, name=ROLE_CANDIDATE)
        if role:
            await member.add_roles(role)
        # Генерация персональной ссылки
        unique_link = f"https://ваш-сайт.ru/anketa?discord_id={member.id}"
        cursor.execute("REPLACE INTO user_links (user_id, link) VALUES (?, ?)", (member.id, unique_link))
        db.commit()
        try:
            await member.send(f"📝 Добро пожаловать! Заполните анкету по ссылке:\n{unique_link}")
        except:
            pass
    else:
        player_role = discord.utils.get(guild.roles, name=ROLE_PLAYER)
        registered_role = discord.utils.get(guild.roles, name=ROLE_REGISTERED)
        if player_role:
            await member.add_roles(player_role)
        if registered_role:
            await member.add_roles(registered_role)

# ------------------ КОНТРОЛЬ АКТИВНОСТИ ------------------
@tasks.loop(hours=1)
async def check_activity():
    guild = bot.guilds[0] if bot.guilds else None
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

        # Обновляем last_message_time из реальных сообщений
        # В реальности нужно слушать on_message, здесь упрощённо
        if now - last_time > 6 * 86400:  # 6 дней
            if warned_time == 0 or now - warned_time > 86400:
                # Тегаем в канале
                channel = bot.get_channel(ACTIVITY_WARNING_CHANNEL_ID)
                if channel:
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Я тут! 🎮", custom_id=f"imhere_{member.id}", style=discord.ButtonStyle.primary))
                    await channel.send(f"{member.mention}, ты давно не писал! Нажми кнопку, чтобы остаться.", view=view)
                    cursor.execute("REPLACE INTO member_activity (user_id, last_message_time, warned_time) VALUES (?, ?, ?)",
                                   (member.id, last_time, now))
                    db.commit()
        # Если прошло 7 дней без активности (warned_time был установлен 24+ часов назад)
        if warned_time and now - warned_time > 86400 and now - last_time > 7 * 86400:
            await member.kick(reason="Неактивность более 7 дней")
            cursor.execute("DELETE FROM member_activity WHERE user_id = ?", (member.id,))
            db.commit()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Обновляем активность
    cursor.execute("REPLACE INTO member_activity (user_id, last_message_time, warned_time) VALUES (?, ?, 0)",
                   (message.author.id, time.time()))
    db.commit()
    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("imhere_"):
            user_id = int(custom_id.split("_")[1])
            if interaction.user.id == user_id:
                cursor.execute("UPDATE member_activity SET warned_time = 0, last_message_time = ? WHERE user_id = ?",
                               (time.time(), user_id))
                db.commit()
                await interaction.response.send_message("✅ Рады, что ты с нами!", ephemeral=True)
                await interaction.message.delete()
            else:
                await interaction.response.send_message("❌ Эта кнопка не для вас.", ephemeral=True)
            return
        elif custom_id.startswith("accept_") or custom_id.startswith("reject_"):
            # Обработка принятия/отказа анкет (код выше)
            pass

# ------------------ ЗАПУСК ------------------
if __name__ == "__main__":
    bot.run(TOKEN)