import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from aiohttp import web
import aiosqlite
import datetime
import asyncio
import re
from database import init_db, DB_NAME

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def is_mod(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator: 
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM mods WHERE user_id = ?", (interaction.user.id,)) as cursor:
            return await cursor.fetchone() is not None

# ================= КНОПКИ И ИНТЕРФЕЙС =================

class ActivityCheckView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Я тут! 🎮", style=discord.ButtonStyle.green, custom_id="act_btn")
    async def here_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: 
            return await interaction.response.send_message("Не твоя кнопка!", ephemeral=True)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR REPLACE INTO member_activity VALUES (?, ?, 0, NULL)", (self.user_id, datetime.datetime.utcnow().isoformat()))
            await db.commit()
        await interaction.response.send_message("Активность обновлена!", ephemeral=True)
        await interaction.message.delete()

class AdminFormReviewView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_mod(interaction): 
            return
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        
        r_cand = guild.get_role(1259813357763170394)
        r_reg = guild.get_role(1259828977942528111)
        r_play = guild.get_role(1506372814477988002)

        if member:
            if r_cand: await member.remove_roles(r_cand)
            if r_play: await member.add_roles(r_play)
            if r_reg: await member.add_roles(r_reg)
            try: await member.send("🎉 Ваша анкета одобрена!")
            except: pass
        await interaction.message.delete()

    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_mod(interaction): 
            return
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        cat = discord.utils.get(guild.categories, name="Разбор отказов") or await guild.create_category("Разбор отказов")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False), 
            interaction.user: discord.PermissionOverwrite(read_messages=True)
        }
        if member: 
            overwrites[member] = discord.PermissionOverwrite(read_messages=True)
        ch = await guild.create_text_channel(name=f"разбор-{self.applicant_id}", category=cat, overwrites=overwrites)
        await ch.send(f"⚠️ Чат разбора. Модератор: {interaction.user.mention}, Игрок: {member.mention if member else self.applicant_id}")
        await interaction.message.delete()

# ================= СОБЫТИЯ =================

@bot.event
async def on_ready():
    await init_db()
    print(f"[OK] Бот запущен: {bot.user}")
    await bot.tree.sync()
    check_activity.start()
    auto_cleanup_loop.start()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO member_activity VALUES (?, ?, 0, NULL)", (message.author.id, datetime.datetime.utcnow().isoformat()))
        await db.commit()

@bot.event
async def on_member_join(member):
    guild = member.guild
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await db.commit()
        async with db.execute("SELECT value FROM config WHERE key = 'reg_mode'") as c:
            row = await c.fetchone()
            mode = row[0] if row else "off"
            
    r_cand = guild.get_role(1259813357763170394)
    r_reg = guild.get_role(1259828977942528111)
    r_play = guild.get_role(1506372814477988002)

    if mode == "on":
        if r_cand: await member.add_roles(r_cand)
        if r_play: await member.remove_roles(r_play)
        if r_reg: await member.remove_roles(r_reg)
        try: await member.send("Привет! Наш сервер закрытого типа. Заполни анкету: https://sirionhub.online/")
        except: pass
    else:
        if r_play: await member.add_roles(r_play)
        if r_reg: await member.add_roles(r_reg)
        if r_cand: await member.remove_roles(r_cand)
        try: await member.send("Привет! Добро пожаловать на Sirion Hub! Тебе открыты все каналы.")
        except: pass

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT channel_id, text, title, description, color FROM welcome_settings WHERE guild_id = ?", (guild.id,)) as c:
            w = await c.fetchone()
            if w and guild.get_channel(w[0]):
                ch = guild.get_channel(w[0])
                txt = w[1].replace("{user_mention}", member.mention) if w[1] else None
                emb = discord.Embed(title=w[2], description=w[3].replace("{user_mention}", member.mention) if w[3] else "", color=int(w[4].replace("#",""),16) if w[4] else 0x00ff00) if (w[2] or w[3]) else None
                await ch.send(content=txt, embed=emb)

# ================= АВТОМАТИЧЕСКИЕ ТАСКИ =================

@tasks.loop(hours=1)
async def check_activity():
    now = datetime.datetime.utcnow()
    async with aiosqlite.connect(DB_NAME) as db:
        for g in bot.guilds:
            ch = discord.utils.get(g.text_channels, name="активность")
            if not ch: 
                continue
            async with db.execute("SELECT * FROM member_activity") as cur:
                for row in await cur.fetchall():
                    m = g.get_member(row[0])
                    if not m or m.guild_permissions.administrator: 
                        continue
                    days = (now - datetime.datetime.fromisoformat(row[1])).days
                    if days >= 6 and row[2] == 0:
                        await ch.send(f"⚠️ {m.mention}, пройдите проверку активности!", view=ActivityCheckView(m.id))
                        await db.execute("UPDATE member_activity SET warned=1, warned_at=? WHERE user_id=?", (now.isoformat(), m.id))
                    elif row[2] == 1 and (now - datetime.datetime.fromisoformat(row[3])).total_seconds() >= 86400:
                        try: 
                            await g.kick(m, reason="Неактивен 7 дней")
                        except: 
                            pass
                        await db.execute("DELETE FROM member_activity WHERE user_id=?", (m.id,))
        await db.commit()

@tasks.loop(minutes=30)
async def auto_cleanup_loop():
    now = datetime.datetime.utcnow()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM cleanup_jobs") as c:
            for ch_id, sec in await c.fetchall():
                ch = bot.get_channel(ch_id)
                if ch: 
                    await ch.purge(before=now-datetime.timedelta(seconds=sec), check=lambda m: not m.pinned)

# ================= СЛЭШ КОМАНДЫ =================

@bot.tree.command(name="режим_анкет")
@app_commands.choices(status=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off"), app_commands.Choice(name="status", value="status")])
async def reg_mode(interaction: discord.Interaction, status: str):
    if not await is_mod(interaction): 
        return
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await db.commit()
        
        if status == "status":
            async with db.execute("SELECT value FROM config WHERE key = 'reg_mode'") as c:
                row = await c.fetchone()
                current = row[0] if row else "off"
                await interaction.response.send_message(f"Режим анкет сейчас: {current}")
        else:
            await db.execute("INSERT OR REPLACE INTO config VALUES ('reg_mode', ?)", (status,))
            await db.commit()
            await interaction.response.send_message(f"Установлен режим {status}")

@bot.tree.command(name="кнопка_анкеты")
async def cmd_btn(interaction: discord.Interaction):
    if not await is_mod(interaction): 
        return
    ссылка = "https://sirionhub.online/"
    v = discord.ui.View()
    v.add_item(discord.ui.Button(label="Заполнить анкету 📝", url=ссылка))
    await interaction.response.send_message("Нажмите кнопку ниже, чтобы открыть сайт и заполнить анкету:", view=v)

@bot.tree.command(name="приветствие")
@app_commands.choices(действие=[app_commands.Choice(name="Включить", value="set"), app_commands.Choice(name="Отключить", value="disable")])
async def cmd_welcome(interaction: discord.Interaction, действие: str, канал: discord.TextChannel=None, текст: str=None, заголовок: str=None, описание: str=None, цвет: str=None):
    if not await is_mod(interaction): 
        return
    async with aiosqlite.connect(DB_NAME) as db:
        if действие == "disable":
            await db.execute("DELETE FROM welcome_settings WHERE guild_id=?", (interaction.guild_id,))
            await interaction.response.send_message("Приветствия отключены")
        else:
            await db.execute("INSERT OR REPLACE INTO welcome_settings VALUES (?,?,?,?,?,?)", (interaction.guild_id, канал.id, текст, заголовок, описание, цвет))
            await interaction.response.send_message("Приветствие сохранено")
        await db.commit()

@bot.tree.command(name="автоочистка")
async def cmd_cleanup(interaction: discord.Interaction, канал: discord.TextChannel, время: str):
    if not await is_mod(interaction): 
        return
    if время == "0":
        async with aiosqlite.connect(DB_NAME) as db: 
            await db.execute("DELETE FROM cleanup_jobs WHERE channel_id=?", (канал.id,))
            await db.commit()
        return await interaction.response.send_message("Очистка отключена")
    m = re.match(r"(\d+)([смчд]?)", время.lower())
    val, unit = int(m.group(1)), m.group(2)
    sec = val if unit=='s' else val*60 if unit=='м' or not unit else val*3600 if unit=='ч' else val*86400
    async with aiosqlite.connect(DB_NAME) as db: 
        await db.execute("INSERT OR REPLACE INTO cleanup_jobs VALUES (?,?)", (канал.id, sec))
        await db.commit()
    await interaction.response.send_message("Автоочистка включена")

@bot.tree.command(name="доступ")
@app_commands.choices(действие=[app_commands.Choice(name="add", value="add"), app_commands.Choice(name="remove", value="remove"), app_commands.Choice(name="list", value="list")])
async def cmd_access(interaction: discord.Interaction, действие: str, пользователь: discord.Member=None):
    if not interaction.user.guild_permissions.administrator: 
        return
    async with aiosqlite.connect(DB_NAME) as db:
        if действие == "list":
            async with db.execute("SELECT user_id FROM mods") as c:
                await interaction.response.send_message("Модераторы:\n" + "\n".join([f"<@{r[0]}>" for r in await c.fetchall()]))
        elif действие == "add":
            await db.execute("INSERT OR IGNORE INTO mods VALUES (?)", (пользователь.id,))
            await interaction.response.send_message("Добавлен")
        elif действие == "remove":
            await db.execute("DELETE FROM mods WHERE user_id=?", (пользователь.id,))
            await interaction.response.send_message("Удален")
        await db.commit()

@bot.tree.command(name="очистить")
async def cmd_clear(interaction: discord.Interaction, количество: int):
    if not await is_mod(interaction): 
        return
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=max(1, min(100, количество)))
    await interaction.followup.send("Готово!", ephemeral=True)

@bot.tree.command(name="ping")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong: {round(bot.latency*1000)}ms")

# ================= ЗАЩИТА ОТ ОШИБОК И ПАДЕНИЙ =================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message("❌ У вас нет прав модератора для использования этой команды!", ephemeral=True)
    else:
        print(f"[КРИТ] Ошибка в команде: {error}")
        try:
            await interaction.response.send_message("⚠️ Произошла внутренняя ошибка, но я выжил!", ephemeral=True)
        except:
            pass

# ================= ВЕБ СЕРВЕР ДЛЯ WEBHOOK И HEALTH CHECK =================

async def web_main():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="OK"))
    app.router.add_post('/webhook', web_hook_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"[WEB] Сервер запущен на динамическом порту {port}")

async def web_hook_handler(request):
    try:
        data = await request.json()
        uid, ans = int(data.get("user_id")), data.get("answers", "")
        for g in bot.guilds:
            ch = discord.utils.get(g.text_channels, name="модерация-анкет")
            if ch: 
                await ch.send(embed=discord.Embed(title="Новая анкета", description=f"От: <@{uid}>\n{ans}"), view=AdminFormReviewView(uid))
        return web.Response(text="OK")
    except: 
        return web.Response(status=400)

async def main():
    await web_main()
    await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
