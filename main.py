    async def on_message(self, message):
        # 1. Проверяем, что это наш канал логов
        if message.channel.id == LOG_CHANNEL_ID:
            # 2. Если сообщение от вебхука (Captain Hook)
            if message.webhook_id is not None:
                try:
                    # Ищем ID пользователя в тексте (после "ID:")
                    import re
                    # Ищем 17-20 цифр после слова ID
                    match = re.search(r"ID:(\d{17,20})", message.content)
                    if match:
                        user_id = int(match.group(1))
                        # Добавляем кнопки
                        await message.edit(view=AdminReviewView(user_id))
                        print(f"Кнопки успешно добавлены для ID: {user_id}")
                except Exception as e:
                    print(f"Ошибка при добавлении кнопок: {e}")
        
        await self.process_commands(message)
