import discord
import os
import asyncio
import re
import sqlite3
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

# Таблица изменена, чтобы хранить тип времени (минуты/часы) и его количество
cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_purge (
        channel_id INTEGER PRIMARY KEY,
        time_value INTEGER,
        time_type TEXT
    )
""")
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

# ================= ВЕБ-СЕРВЕР =================
async def handle(request): return web.Response(text="Work")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

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
        if not target_id: return

        member = interaction.guild.get_member(target_id)
        if member:
            r_play = interaction.guild.get_role(ROLE_PLAYER)
            r_reg = interaction.guild.get_role(ROLE_REGISTERED)
            r_cand = interaction.guild.get_role(ROLE_CANDIDATE)
            if r_play: await member.add_roles(r_play)
            if r_reg: await member.add_roles(r_reg)
            if r_cand: await member.remove_roles(r_cand)
            update_user_activity(target_id)
            await interaction.response.edit_message(content=interaction.message.content + f"\n\n🟢 **СТАТУС: ОДОБРЕНО** модератором <@{interaction.user.id}>.", view=None)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger, custom_id="admin_deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff_permission(interaction.user):
            await interaction.response.send_message("❌ У вас нет доступа к управлению анкетами.", ephemeral=True)
            return
        target_id = self.get_target_id(interaction.message.content)
        if not target_id: return

        global deny_counter
        guild = interaction.guild
        member = guild.get_member(target_id)
        if not member: return

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
        await interaction.response.edit_message(content=interaction.message.content + f"\n\n🔴 **СТАТУС: ОТКЛОНЕНО** модератором <@{interaction.user.id}>.\n💬 Чат разбора: {ch.mention}", view=None)

class RegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Заполнить анкету 📝", style=discord.ButtonStyle.gray, custom_id="reg_v12")
    async def start(self, itn, btn):
        url = f"{URL_SAYTA}?uid={itn.user.id}"
        v = View()
        v.add_item(discord.ui.Button(label="Открыть анкету", url=url))
        await itn.response.send_message("Твоя персональная ссылка на анкету:", view=v, ephemeral=True)

# ================= BOT CLASS =================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.add_view(RegistrationView())
        self.add_view(DenyChatView())
        self.add_view(AdminReviewView())
        
    async def on_ready(self):
        print(f"Бот запущен под именем {self.user}")
        if not self.guilds: return
        guild = self.guilds[0]
        
        # КРИТИЧЕСКИЙ СБРОС КЭША: гарантирует появление всех команд в Discord
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            print("Слэш-команды успешно прописаны и обновлены в Discord!")
        except Exception as e:
            print(f"Ошибка синхронизации слэш-команд: {e}")
            
        player_role = guild.get_role(ROLE_PLAYER)
        if not player_role: return

        print("Запуск БЕЗОПАСНОЙ очистки и синхронизации...")
        current_time = datetime.now(timezone.utc)
        
        for member in guild.members:
            if member.bot: continue
            if player_role in member.roles:
                cursor.execute("SELECT user_id FROM activity WHERE user_id = ?", (member.id,))
                if cursor.fetchone() is None:
                    update_user_activity(member.id, current_time)
                
        print("База данных успешно сброшена на безопасный режим.")
        
        if not self.check_activity_loop.is_running(): self.check_activity_loop.start()
        if not self.auto_purge_loop.is_running(): self.auto_purge_loop.start()

    async def on_member_join(self, m):
        r = m.guild.get_role(ROLE_CANDIDATE)
        if r: await m.add_roles(r)
        
    async def on_message(self, m):
        if m.author.bot:
            if m.channel.id == LOG_CHANNEL_ID and m.webhook_id:
                match = re.search(r"ID:(\d+)", m.content)
                if match:
                    await m.delete()
                    await m.channel.send(content=m.content, view=AdminReviewView())
            return
        update_user_activity(m.author.id)

    @tasks.loop(hours=1)
    async def check_activity_loop(self):
        await self.wait_until_ready()
        if not self.guilds: return
        guild = self.guilds[0]
        channel = guild.get_channel(ACTIVITY_CHECK_CHANNEL_ID)
        if not channel: return

        cursor.execute("SELECT user_id, last_active, warned FROM activity")
        rows = cursor.fetchall()
        now = datetime.now()

        for user_id, last_active_str, warned in rows:
            member = guild.get_member(user_id)
            if not member: continue
            if guild.get_role(ROLE_PLAYER) not in member.roles: continue

            last_active = datetime.fromisoformat(last_active_str)
            days_passed = (now - last_active).days

            if days_passed >= 6 and days_passed < 7 and warned == 0:
                cursor.execute("UPDATE activity SET warned = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
                await channel.send(
                    f"⚠️ Игрок <@{user_id}>, вы не проявляли активность на сервере уже 6 дней!\n"
                    f"Нажмите на кнопку ниже в течение 24 часов, иначе вы будете исключены.",
                    view=AliveButtonView(user_id)
                )
            elif days_passed >= 7:
                cursor.execute("DELETE FROM activity WHERE user_id = ?", (user_id,))
                conn.commit()
                try:
                    await member.kick(reason="Неактивность на сервере в течение 7 дней")
                    await channel.send(f"❌ Игрок **{member.name}** был кикнут за неактивность.")
                except discord.Forbidden:
                    await channel.send(f"⚠️ Не удалось кикнуть **{member.name}** (нет прав).")

    # Автоочистка запускается часто (каждые 2 минуты) для точности удаления
    @tasks.loop(minutes=2)
    async def auto_purge_loop(self):
        await self.wait_until_ready()
        cursor.execute("SELECT channel_id, time_value, time_type FROM auto_purge")
        channels = cursor.fetchall()
        
        now = datetime.now(timezone.utc)
        
        for ch_id, val, t_type in channels:
            channel = self.get_channel(ch_id)
            if not channel: continue
            
            # Быстрое вычисление точного срока
            if t_type == "minutes":
                cutoff = now - timedelta(minutes=val)
            else:
                cutoff = now - timedelta(hours=val)
                
            try:
                # Мгновенная очистка пачкой до высчитанной даты
                await channel.purge(limit=500, before=cutoff, check=lambda m: not m.pinned)
            except Exception: 
                pass

bot = MyBot()

# ================= ВСЕ 4 НЕОБХОДИМЫЕ СЛЭШ-КОМАНДЫ =================

@bot.tree.command(name="установка", description="Установить начальное сообщение с кнопкой анкеты")
async def _установка(ctx: discord.Interaction):
    if not check_staff_permission(ctx.user):
        await ctx.response.send_message("❌ У вас нет прав на использование этой команды.", ephemeral=True)
        return
    await ctx.response.send_message("Создаю сообщение...", ephemeral=True)
    await ctx.channel.send("**Добро пожаловать в Сирион Хаб! Нажмите кнопку ниже, чтобы заполнить анкету игрока и получить доступ к серверу:**", view=RegistrationView())

@bot.tree.command(name="очистить", description="Удалить определенное количество сообщений")
@app_commands.describe(количество="Сколько сообщений нужно стереть")
async def _очистить(ctx: discord.Interaction, количество: int):
    if not check_staff_permission(ctx.user):
        await ctx.response.send_message("❌ У вас нет доступа.", ephemeral=True)
        return
    if количество < 1:
        await ctx.response.send_message("❌ Укажите число больше нуля.", ephemeral=True)
        return
    await ctx.response.defer(ephemeral=True)
    deleted = await ctx.channel.purge(limit=количество)
    await ctx.followup.send(f"✅ Успешно удалено сообщений: {len(deleted)}.", ephemeral=True)

@bot.tree.command(name="автоочистка", description="Настроить автоматическую очистку старых сообщений в этом канале")
@app_commands.choices(тип_времени=[
    app_commands.Choice(name="Минуты", value="minutes"),
    app_commands.Choice(name="Часы", value="hours"),
    app_commands.Choice(name="Отключить автоочистку", value="off")
])
@app_commands.describe(тип_времени="В чем измерять срок жизни сообщений", значение="Какое время выставить (пропусти, если отключаешь)")
async def _автоочистка(ctx: discord.Interaction, тип_времени: str, значение: int = None):
    if not check_staff_permission(ctx.user):
        await ctx.response.send_message("❌ У вас нет доступа.", ephemeral=True)
        return
        
    if тип_времени == "off":
        cursor.execute("DELETE FROM auto_purge WHERE channel_id = ?", (ctx.channel_id,))
        conn.commit()
        await ctx.response.send_message("🛑 Автоочистка для этого канала полностью отключена.", ephemeral=True)
        return

    if значение is None or значение < 1:
        await ctx.response.send_message("❌ Вы должны указать числовое значение времени больше нуля!", ephemeral=True)
        return

    # Запись настроек времени в базу данных
    cursor.execute("INSERT OR REPLACE INTO auto_purge (channel_id, time_value, time_type) VALUES (?, ?, ?)", 
                   (ctx.channel_id, значение, тип_времени))
    conn.commit()
    
    label = "мин." if тип_времени == "minutes" else "ч."
    await ctx.response.send_message(f"⚙️ Срок успешно изменен! Теперь сообщения старше **{значение} {label}** будут мгновенно стираться пачкой.", ephemeral=True)

@bot.tree.command(name="доступ", description="Управление правами доступа к командам бота")
@app_commands.choices(действие=[
    app_commands.Choice(name="Добавить доступ", value="add"),
    app_commands.Choice(name="Забрать доступ", value="remove"),
    app_commands.Choice(name="Список персонала", value="list")
])
@app_commands.describe(выбор_объекта="Выберите пользователя или роль на сервере")
async def _доступ(ctx: discord.Interaction, действие: str, выбор_объекта: discord.Mentionable = None):
    if ctx.user.id != MY_ID and not ctx.user.guild_permissions.administrator:
        await ctx.response.send_message("❌ Настройка доступов доступна только Главному Администратору.", ephemeral=True)
        return

    if действие == "list":
        cursor.execute("SELECT target_id FROM staff_access")
        rows = cursor.fetchall()
        if not rows:
            await ctx.response.send_message("ℹ️ Кастомных доступов нет. Права есть у Администраторов и Модераторов.", ephemeral=True)
            return
        text = "📋 **Персонал с кастомным доступом к боту:**\n"
        for r in rows: text += f"• <@&{r[0]}> / <@{r[0]}> (ID: `{r[0]}`)\n"
        await ctx.response.send_message(text, ephemeral=True)
        return

    if not выбор_объекта:
        await ctx.response.send_message("❌ Вы забыли выбрать пользователя или роль в параметрах!", ephemeral=True)
        return

    target_id = выбор_объекта.id

    if действие == "add":
        cursor.execute("INSERT OR REPLACE INTO staff_access (target_id, type) VALUES (?, 'custom')", (target_id,))
        conn.commit()
        await ctx.response.send_message(f"✅ Доступ для {выбор_объекта.mention} успешно выдан.", ephemeral=True)
    elif действие == "remove":
        cursor.execute("DELETE FROM staff_access WHERE target_id = ?", (target_id,))
        conn.commit()
        await ctx.response.send_message(f"➖ Доступ для {выбор_объекта.mention} успешно аннулирован.", ephemeral=True)

# ================= ЗАПУСК БОТА =================
async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
