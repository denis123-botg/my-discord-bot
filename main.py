    async def on_message(self, message):
        # Если сообщение пришло в канал логов от вебхука
        if message.channel.id == LOG_CHANNEL_ID and message.webhook_id:
            try:
                # Ищем ID пользователя
                match = re.search(r"ID:(\d+)", message.content)
                if match:
                    user_id = int(match.group(1))
                    content = message.content
                    
                    # Удаляем сообщение вебхука
                    await message.delete()
                    
                    # Отправляем от имени бота с кнопками
                    view = AdminReviewView(user_id)
                    await message.channel.send(content=content, view=view)
                    print(f"Кнопки успешно добавлены для {user_id}")
            except Exception as e:
                print(f"Ошибка обработки: {e}")
        
        await self.process_commands(message)
