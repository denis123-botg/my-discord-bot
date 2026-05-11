# ================= 2 ЭТАП: ВЫБОР ОТРЯДА (ОБНОВЛЕНО) =================
class SquadSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def complete(self, interaction, squad_id, name):
        member = interaction.user
        guild = interaction.guild
        
        r_squad = guild.get_role(squad_id)
        r_reg = guild.get_role(ROLE_REGISTERED)
        r_conf = guild.get_role(ROLE_CONFIRMED)

        # 1. Выдаем финальные роли
        if r_reg: await member.add_roles(r_reg)
        if r_squad: await member.add_roles(r_squad)
        
        # 2. СТРОГО СНИМАЕМ роль "Подтвержден"
        if r_conf: 
            await member.remove_roles(r_conf)

        await interaction.response.send_message(f"✅ Вы выбрали **{name}**. Роль подтвержденного снята, регистрация завершена!", ephemeral=True)
