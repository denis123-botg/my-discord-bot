import discord
import os
import asyncio
import re
import sqlite3
from datetime import datetime, timezone
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
conn.commit()

def update_user_activity(user_id, dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    cursor.execute("INSERT OR REPLACE INTO activity (user_id, last_active, warned) VALUES (?, ?, 0)", 
                   (user_id, dt.replace(tzinfo=None).isoformat()))
    conn.commit()

# Проверки прав
def has_staff_perms(interaction: discord.Interaction):
    if interaction.user.id == MY_ID: return True
    if interaction.user.guild_permissions.administrator: return True
    mod_role = interaction.guild.get_role(ROLE_MODERATOR)
    if mod_role and mod_role in interaction.user.roles: return True
    return False

def has_cmd_perms(ctx):
    if ctx.author.id == MY_ID: return True
    if ctx.author.guild_permissions.administrator: return True
    mod_role = ctx.guild.get_role(ROLE_MODERATOR)
    if mod_role and mod_role in ctx.author.roles: return True
    return False

# ================= ВЕБ-СЕРВЕР =================
async def handle(request): return web.Response(text="Work")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# ================= VIEW: КНОПКА ПОДТВЕРЖДЕНИЯ АКТИВНОСТИ =================
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
        await interaction.response.send_message("✅ Ваша активность подтверждена! Больше вам ничего не угрожает.", ephemeral=True)
        await interaction.message.delete()

# ================= VIEW: УДАЛЕНИЕ ЧАТА ОТКАЗА =================
class DenyChatView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить чат 🗑️", style=discord.ButtonStyle.danger, custom_id="del_ch_final")
    async def delete_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if has_staff_perms(interaction):
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
        if not has_staff_perms(interaction):
            await interaction.response.send_message("❌ Доступно только администрации и модераторам.", ephemeral=True)
            return
            
        target_id = self.get_target_id(interaction.message.content)
        if not target_id:
            await interaction.response.send_message("❌ Не удалось определить ID пользователя из анкеты.", ephemeral=True)
            return

        member = interaction.guild.get_member(target_id)
        if member:
            r_play = interaction.guild.get_role(ROLE_PLAYER)
            r_reg = interaction.guild.get_role(ROLE_REGISTERED)
            r_cand = interaction.guild.get_role(ROLE_CANDIDATE)
            
            roles_to_add = [r for r in [r_play, r_reg] if r]
            if roles_to_add: await member.add_roles(*roles_to_add)
            if r_cand: await member.remove_roles(r_cand)
            
            update_user_activity(target_id)
            
            await interaction.response.edit_message(content=interaction.message.content + f"\n\n🟢 **СТАТУС: ОДОБРЕНО** модератором <@{interaction.user.id}>. Пользователю выданы роли <@&{ROLE_PLAYER}> и <@&{ROLE_REGISTERED}>.", view=None)
        else:
            await interaction.response.send_message("❌ Пользователь не найден на сервере.", ephemeral=True)

    @discord.ui.button(label="Отказать ❌", style=discord.ButtonStyle.danger, custom_id="admin_deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_staff_perms(interaction):
            await interaction.response.send_message("❌ Доступно только администрации и модераторам.", ephemeral=True)
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
            guild.get_member(MY_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(ROLE_MODERATOR): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        category = guild.get_channel(CATEGORY_DENY)
        ch = await guild.create_text_channel(f"отказ-{deny_counter}", category=category, overwrites=overwrites)
        await ch.send(f"⚠️ <@{target_id}>, ваша анкета отклонена. Ожидайте модератора в этом канале.", view=DenyChatView())
        
        await interaction.response.edit_message(content=interaction.message.content + f"\n\n🔴 **СТАТУС: ОТКЛОНЕНО** модератором <@{interaction.user.id}>.\n💬 Чат разбора: {ch.mention}", view=None)

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
        self.check_activity_loop.start()
        
    async def on_ready(self):
        print(f"Бот запущен под именем {self.user}")
        if not self.guilds: return
        guild = self.guilds[0]
        
        player_role = guild.get_role(ROLE_PLAYER)
        if not player_role: return

        print("Запуск БЕЗОПАСНОЙ синхронизации участников...")
        current_time = datetime.now(timezone.utc)
        
        for member in guild.members:
            if member.bot: continue
            if player_role in member.roles:
                cursor.execute("SELECT user_id FROM activity WHERE user_id = ?", (member.id,))
                if cursor.fetchone() is None:
                    # ИСПРАВЛЕНО: Вместо даты захода на сервер мы ставим ТЕКУЩЕЕ время.
                    # Отсчет 6 дней начнется прямо с этого момента для всех старичков.
                    update_user_activity(member.id, current_time)
        print("Синхронизация завершена. Все старые игроки успешно добавлены в очередь без ложных киков!")

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
        await self.process_commands(m)

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

            # День 6: Предупреждение
            if days_passed >= 6 and days_passed < 7 and warned == 0:
                cursor.execute("UPDATE activity SET warned = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
                await channel.send(
                    f"⚠️ Игрок <@{user_id}>, вы не проявляли активность на сервере уже 6 дней!\n"
                    f"Нажмите на кнопку ниже в течение 24 часов, иначе вы будете исключены с сервера.",
                    view=AliveButtonView(user_id)
                )

            # День 7: Кик (сработает только если прошло еще 24 часа после 6-го дня)
            elif days_passed >= 7:
                cursor.execute("DELETE FROM activity WHERE user_id = ?", (user_id,))
                conn.commit()
                try:
                    await member.kick(reason="Неактивность на сервере в течение 7 дней")
                    await channel.send(f"❌ Игрок **{member.name}** был кикнут с сервера за полную неактивность в течение 7 дней.")
                except discord.Forbidden:
                    # Если у бота не хватает прав кикнуть админа/модератора, пишем об этом в чат логов
                    await channel.send(f"⚠️ Не удалось кикнуть **{member.name}** (у бота недостаточно прав/роль бота ниже роли юзера).")

bot = MyBot()

@bot.command()
async def установка(ctx):
    if has_cmd_perms(ctx):
        await ctx.send("**Добро пожаловать в Сирион Хаб! Нажмите кнопку ниже, чтобы заполнить анкету игрока и получить доступ к serverу:**", view=RegistrationView())

async def main():
    await start_server()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
