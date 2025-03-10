import logging
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
import json
from src.states.user_state import user_state_manager
from src.keyboard.keyboards import get_main_keyboard
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()  # загружаем переменные из .env
admin_id = int(os.getenv('ADMIN_ID'))
if admin_id is None:
    raise ValueError("ADMIN_ID не установлен в .env файле")
ADMIN_ID = int(admin_id)

logger = logging.getLogger(__name__)


async def send_admin_notification(bot):
    """Отправляет уведомление администратору о запуске бота"""
    try:
        await bot.send_message(ADMIN_ID, "✅Бот запущен)")
        print("Уведомление администратору отправлено")
    except Exception as e:
        print(f"Ошибка при отправке уведомления администратору: {e}")


async def send_keyboard_to_all_users(bot, db_manager):
    """Отправляет клавиатуру всем пользователям"""
    try:
        users = await db_manager.get_all_users()
        print(f"Отправка главной клавиатуры {len(users)} пользователям...")
        for chat_id in users:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="Бот был перезапущен. Вот главное меню:",
                    reply_markup=get_main_keyboard()
                )
                await asyncio.sleep(0.1)  # Небольшая задержка
            except Exception as e:
                print(
                    f"Ошибка при отправке клавиатуры пользователю {chat_id}: {e}")
        print("Главная клавиатура отправлена всем пользователям")
    except Exception as e:
        print(f"Ошибка при отправке клавиатуры пользователям: {e}")


async def setup_admin_handlers(dp, db_manager, dialog_sessions, active_generations):
    """Настраивает обработчики административных команд"""

    @dp.message(Command('user_states'))
    async def show_user_states(message: types.Message):
        """Показывает состояния всех пользователей"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        user_states = user_state_manager.get_all_user_states()
        # Экранируем специальные символы для Markdown
        escaped_states = str(user_states).replace(
            '{', '\\{').replace('}', '\\}').replace('_', '\\_')
        await message.answer(
            f"👥 *Состояния пользователей:*\n{escaped_states}",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    @dp.message(Command('send_keyboard'))
    async def send_keyboard_command(message: types.Message):
        """Отправляет клавиатуру всем пользователям"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        await message.answer("Начинаю отправку клавиатуры всем пользователям...")
        await send_keyboard_to_all_users(message.bot, db_manager)
        await message.answer("✅ Клавиатура отправлена всем пользователям.")

    @dp.message(Command('dialog_sessions'))
    async def show_dialog_sessions(message: types.Message):
        """Показывает историю диалогов"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        # Используем курсор из db_manager
        try:
            cursor = db_manager.conn.cursor()
            cursor.execute(
                "SELECT chat_id, ai_name, messages FROM dialog_sessions")
            users = cursor.fetchall()

            text = "💬 *История диалогов:*\n\n"
            for chat_id, ai_name, messages in users:
                text += f"🔹 Чат {chat_id} с {ai_name}:\n"
                try:
                    if isinstance(messages, str):
                        dialog = json.loads(messages)
                    else:
                        dialog = messages

                    if isinstance(dialog, list):
                        for msg in dialog[-5:]:  # Показываем последние 5 сообщений
                            role = msg.get('role', 'unknown')
                            content = msg.get('parts', [None])[
                                0] if 'parts' in msg else msg.get('content', 'no content')
                            text += f"  - *{role}*: {str(content)[:100]}...\n"
                    else:
                        text += "  - Ошибка формата диалога\n"
                except json.JSONDecodeError:
                    text += "  - Ошибка при чтении сообщений\n"
                except Exception as e:
                    text += f"  - Ошибка: {str(e)}\n"
                text += "\n"

            # Разбиваем длинное сообщение на части, если нужно
            max_length = 4000
            for i in range(0, len(text), max_length):
                chunk = text[i:i + max_length]
                try:
                    await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    # Если не удалось отправить с форматированием, отправляем без него
                    await message.answer(chunk)
        finally:
            cursor.close()
