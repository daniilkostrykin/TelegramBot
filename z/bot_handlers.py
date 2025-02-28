# bot_handlers.py
import re
import threading
import time
import requests
import logging
import os
from z.config import ADMIN_ID, POPULAR_SITES, GEMINI_API_KEY, BOT_TOKEN, MISTRAL_API_KEY
import google.generativeai as genai
from g4f.client import Client
from deep_translator import GoogleTranslator
from aiogram.types import Message
from z.keyboards import *
import psycopg2
import json
import traceback
from aiogram.fsm.state import State, StatesGroup
from aiogram import Dispatcher, Bot, types, F
from aiogram.utils import markdown
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
import asyncio
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import BaseFilter
from mistralai import Mistral
import aiohttp
import PIL.Image


class DialogStates(StatesGroup):
    waiting_for_dialog = State()
    waiting_for_g4f_dialog = State()
    waiting_for_model_selection = State()
    waiting_for_g4f_model = State()
    waiting_for_mistral_dialog = State()
    waiting_for_mistral_model = State()
    waiting_for_text_image = State()
    waiting_for_text_voice = State()
    waiting_for_nocode = State()
    waiting_for_appearance = State()
    waiting_for_photo = State()
    waiting_for_midjourney = State()


# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:XgFOPaWGkymuYpcXKkuSJwIlcPihcHKI@autorack.proxy.rlwy.net:36255/railway")
# Получаем URL базы данных из переменной окружения
DATABASE_URL = os.environ.get("DB_URL")
if not DATABASE_URL:
    print("Ошибка: Не найдена переменная окружения DB_URL из системы.  Убедитесь, что она установлена.")
    DATABASE_URL = "postgresql://postgres:UxAgpKnoEDeQGLsAODlFNlVOirCaoCIa@gondola.proxy.rlwy.net:54556/railway"

# Инициализируем диспетчер с хранилищем состояний
dp = Dispatcher(storage=MemoryStorage())


def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dialog_sessions (
            chat_id BIGINT,
            ai_name TEXT,
            messages JSONB,
            PRIMARY KEY (chat_id, ai_name)
        );
    """)
    # Создаем таблицу для хранения всех пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("Database tables created successfully")
    conn.commit()

# Добавляем отдельную функцию для отправки уведомления администратору


async def send_admin_notification(bot):
    try:
        await bot.send_message(ADMIN_ID, "✅Бот запущен)")
        print("Уведомление администратору отправлено")
    except Exception as e:
        print(f"Ошибка при отправке уведомления администратору: {e}")

# Добавляем функцию для получения всех пользователей из базы данных


async def get_all_users():
    try:
        # Сначала пробуем получить пользователей из таблицы users
        cursor.execute("SELECT chat_id FROM users")
        users = cursor.fetchall()

        if not users:
            # Если таблица users пуста, получаем пользователей из dialog_sessions
            cursor.execute("SELECT DISTINCT chat_id FROM dialog_sessions")
            users = cursor.fetchall()

        return [user[0] for user in users]
    except Exception as e:
        print(f"Ошибка при получении списка пользователей: {e}")
        return []

# Добавляем функцию для сохранения пользователя в базу данных


async def save_user(message: types.Message):
    try:
        cursor.execute("""
            INSERT INTO users (chat_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (chat_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_activity = CURRENT_TIMESTAMP;
        """, (
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        ))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении пользователя: {e}")

# Добавляем функцию для отправки клавиатуры всем пользователям


async def send_keyboard_to_all_users(bot):
    try:
        users = await get_all_users()
        print(f"Отправка главной клавиатуры {len(users)} пользователям...")
        for chat_id in users:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="Бот был перезапущен. Вот главное меню:",
                    reply_markup=get_main_keyboard()
                )
                # Сохраняем состояние пользователя как main_menu
                user_states[chat_id] = 'main_menu'
                # Небольшая задержка, чтобы не превысить лимиты API
                await asyncio.sleep(0.1)
            except Exception as e:
                print(
                    f"Ошибка при отправке клавиатуры пользователю {chat_id}: {e}")
        print("Главная клавиатура отправлена всем пользователям")
    except Exception as e:
        print(f"Ошибка при отправке клавиатуры пользователям: {e}")

# Изменяем блок try-except
conn = None  # Инициализируем conn вне блока try
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # Выводим сообщение об успешном подключении
    print("Успешно подключено к базе данных!")
    # Просто вызываем синхронную функцию создания таблиц
    create_tables()
except psycopg2.Error as e:
    print(f"Ошибка при подключении к базе данных: {e}")


logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

dialog_sessions = {}  # Словарь для хранения истории диалогов
g4f_dialog_sessions = {}
active_generations = {}  # Словарь для отслеживания генерации сообщений
user_states = {}  # {chat_id: [state1, state2, ...]}


async def setup_handlers(bot):
    # Отправляем уведомление администратору при запуске
    await send_admin_notification(bot)

    # Отправляем клавиатуру всем пользователям
    await send_keyboard_to_all_users(bot)

    @dp.message(Command('start'))
    async def start(message: types.Message):
        try:
            # Сохраняем пользователя в базу данных
            await save_user(message)

            await message.answer(
                f"Привет, {message.from_user.first_name}!\n\n"
                "Я бот, который предоставляет доступ к различным нейросетям и другим полезным функциям.\n\n"
                "Вот что я умею:\n"
                "- Работа с текстом (генерация, перевод, суммаризация)\n"
                "- Генерация изображений\n"
                "- Доступ к различным AI-моделям (Gemini, G4F, ChatGPT и др.)\n\n"
                "Чтобы начать, выберите пункт в меню.",
                reply_markup=get_main_keyboard()
            )
            # Сохраняем состояние
            await save_user_state(message.chat.id, 'main_menu')
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await message.answer('Произошла ошибка')

    @dp.message(Command('test'))
    async def test(message: types.Message):
        text = "* Это *не жирный* и не *курсив*, но **это жирный**, а *это курсив*."
        clean_text = prepare_markdown_text(text)

        # Отправляем сообщение без форматирования
        await message.answer(clean_text)

        # Отправляем сообщение с HTML форматированием
        await message.answer(clean_text, parse_mode=types.ParseMode.HTML)

    def prepare_markdown_text(text: str) -> str:
        """
        Подготавливает текст для корректного отображения в Markdown V2.
        - Удаляет одиночные * в начале строк
        - Экранирует специальные символы
        """
        # Удаляем одиночные * в начале строк
        text = re.sub(r'^\s*\*(?!\*)', '', text, flags=re.MULTILINE)

        # Экранируем специальные символы
        chars = ['[', ']', '(', ')', '~', '>', '#', '+',
                 '-', '=', '|', '{', '}', '.', '!', '_']
        for char in chars:
            text = text.replace(char, f'\\{char}')

        return text

    def process_code_block(text: str) -> list:
        """
        Разделяет текст на обычный текст и блоки кода.
        Возвращает список кортежей (текст, is_code).
        """
        parts = []
        current_text = ""

        # Находим все блоки кода
        pattern = r'```(?:python)?\n([\s\S]*?)```'
        last_end = 0

        for match in re.finditer(pattern, text):
            # Добавляем текст до блока кода
            if match.start() > last_end:
                parts.append((text[last_end:match.start()], False))

            # Добавляем сам блок кода
            parts.append((match.group(1), True))
            last_end = match.end()

        # Добавляем оставшийся текст
        if last_end < len(text):
            parts.append((text[last_end:], False))

        return parts if parts else [(text, False)]

    async def safe_send_message(message: types.Message, text: str):
        MAX_LENGTH = 4000
        try:
            # Разделяем текст на части с кодом и без
            parts = process_code_block(text)

            for content, is_code in parts:
                if not content.strip():
                    continue

                if is_code:
                    # Отправляем код без форматирования
                    await message.answer(f"```\n{content}\n```", parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    # Форматируем обычный текст
                    formatted_text = prepare_markdown_text(content)

                    # Разбиваем на части если текст длинный
                    for i in range(0, len(formatted_text), MAX_LENGTH):
                        chunk = formatted_text[i:i + MAX_LENGTH]
                        await message.answer(chunk, parse_mode=ParseMode.MARKDOWN_V2)

                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"Ошибка форматирования: {e}")
            # Если все попытки форматирования не удались, отправляем текст как есть
            await message.answer(text)

    async def handle_dialog(message: types.Message, state: FSMContext, model_name: str, test_query: str = None):
        chat_id = message.chat.id
        try:
            if message.text == '⏹️ Завершить диалог':
                await message.answer(
                    "Диалог завершен.",
                    reply_markup=get_ai_selection_keyboard()
                )
                if (chat_id, model_name) in dialog_sessions:
                    print(
                        f"[WARNING] Удаляю dialog_sessions[{(chat_id, model_name)}]")
                    del dialog_sessions[(chat_id, model_name)]
                if chat_id in user_states:
                    del user_states[chat_id]
                await save_user_state(state, 'ai_selection')
                await state.finish()
                return

            query = test_query if test_query else message.text
            await save_dialog_message(chat_id, model_name, "user", query)

            sent_message = await message.answer("Генерация ответа...")
            active_generations[chat_id] = True

            try:
                model = genai.GenerativeModel(model_name)
                messages = dialog_sessions.get((chat_id, model_name), [])
                print(
                    f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

                response = await asyncio.to_thread(model.generate_content, messages)
                response_text = response.text
                await save_dialog_message(chat_id, model_name,
                                          "model", response_text)

                await safe_send_message(message, response_text)
                await sent_message.delete()

                # Сохраняем состояние для следующего сообщения
                await state.set_state(DialogStates.waiting_for_dialog)
                await save_user_state(state, model_name)

            except Exception as e:
                logger.error(
                    f"Ошибка генерации контента: {type(e).__name__} - {str(e)}")
                await message.answer(
                    f"Произошла ошибка генерации контента: {str(e)}\nПожалуйста, попробуйте снова."
                )
                # Сохраняем состояние для следующего сообщения
                await state.set_state(DialogStates.waiting_for_dialog)
                await save_user_state(state, model_name)

        except Exception as e:
            logger.error(
                f"Ошибка в диалоге Gemini: {type(e).__name__} - {str(e)}\n{traceback.format_exc()}"
            )
            await message.answer(f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова.")
            await state.set_state(DialogStates.waiting_for_dialog)
            await save_user_state(state, model_name)

    async def handle_g4f_dialog(message: types.Message, state: FSMContext):
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            await message.answer(
                "Диалог завершен.",
                reply_markup=get_main_keyboard()
            )
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            if chat_id in user_states:
                del user_states[chat_id]
            await save_user_state(state, 'main_menu')
            await state.finish()
            return

        elif message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора G4F модели.",
                reply_markup=get_g4f_model_keyboard()
            )
            await save_user_state(state, 'g4f_model_selection')
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            await state.finish()
            return

        query = message.text
        await save_dialog_message(chat_id, "g4f", "user", query)

        if chat_id not in g4f_dialog_sessions:
            g4f_dialog_sessions[chat_id] = []

        g4f_dialog_sessions[chat_id].append({"role": "user", "content": query})

        sent_message = await message.answer("Генерация ответа...")
        active_generations[chat_id] = True  # Помечаем генерацию активной

        try:
            response = await asyncio.to_thread(g4f_bot.ask, query)
            await save_dialog_message(chat_id, "g4f", "assistant", response)

            response_text = response
            max_length = 4000  # Telegram ограничение
            generated_text = ""
            formatted_chunk = ""

            for i in range(0, len(response_text), max_length):
                chunk = response_text[i:i + max_length]
                generated_text += chunk
                new_formatted_chunk = generated_text

                # Проверяем, изменился ли текст перед обновлением
                if new_formatted_chunk != formatted_chunk:
                    formatted_chunk = new_formatted_chunk
                    await message.answer(
                        formatted_chunk,
                        parse_mode=types.ParseMode.HTML
                    )
                    await asyncio.sleep(0.5)  # Асинхронная задержка

            # Добавляем ответ в историю
            g4f_dialog_sessions[chat_id].append(
                {"role": "assistant", "content": response_text}
            )
            await sent_message.delete()

            # Сохраняем состояние для следующего сообщения
            await state.set_state(DialogStates.waiting_for_g4f_dialog)

        except Exception as e:
            error_message = f"Ошибка: {type(e).__name__} - {str(e)}"
            logger.error(error_message)
            print(error_message)

            try:
                # Пробуем отправить текст без форматирования
                plain_text = re.sub(
                    r'<[^>]+>', '',
                    formatted_chunk if formatted_chunk else response_text
                )
                await message.answer(plain_text)
            except Exception as e2:
                logger.error(
                    f"Повторная ошибка при отправке без форматирования: {e2}")
                await message.answer("Ошибка при отправке сообщения. Попробуйте позже.")

            # Сохраняем состояние несмотря на ошибку
            await state.set_state(DialogStates.waiting_for_g4f_dialog)

    async def save_user_state(state_or_chat_id, new_state: str):
        """
        Сохраняет текущее состояние пользователя.
        Args:
            state_or_chat_id: FSMContext объект или chat_id пользователя
            new_state: Новое состояние для сохранения
        """
        if isinstance(state_or_chat_id, int):
            # Если передан chat_id, просто сохраняем состояние в словарь
            user_states[state_or_chat_id] = new_state
        else:
            # Если передан FSMContext, сохраняем в FSM
            state = state_or_chat_id
            data = await state.get_data()
            if 'states_history' not in data:
                data['states_history'] = []
            data['states_history'].append(new_state)
            data['current_state'] = new_state
            await state.update_data(data)

            # Также сохраняем в словарь для совместимости
            try:
                chat_id = state.key.chat_id
                user_states[chat_id] = new_state
            except:
                pass  # Если не удалось получить chat_id, просто пропускаем

    async def get_previous_user_state(state: FSMContext) -> str | None:
        """
        Возвращает предыдущее состояние пользователя из FSM.

        Args:
            state: FSMContext объект для работы с состоянием

        Returns:
            str | None: Предыдущее состояние или None если истории нет
        """
        data = await state.get_data()
        if 'states_history' in data and len(data['states_history']) > 1:
            data['states_history'].pop()  # Убираем текущее состояние
            previous_state = data['states_history'][-1]  # Берем предыдущее
            data['current_state'] = previous_state
            return previous_state
        return None

    async def save_dialog_message(chat_id: int, ai_name: str, role: str, content: str):
        """
        Сохраняет сообщение в диалог пользователя (в БД и в память).

        Args:
            chat_id: ID чата пользователя
            ai_name: Название AI модели
            role: Роль отправителя (user/model)
            content: Содержание сообщения
        """
        print(
            f"[LOG] save_dialog_message вызван с: chat_id={chat_id}, ai_name={ai_name}, role={role}, content={content}"
        )

        # Проверяем, есть ли диалог в памяти
        if (chat_id, ai_name) not in dialog_sessions:
            print(
                f"[ERROR] dialog_sessions НЕ содержит ({chat_id}, {ai_name}). Создаю новый ключ."
            )
            dialog_sessions[(chat_id, ai_name)] = []

        # Добавляем сообщение в локальный кэш
        try:
            dialog_sessions[(chat_id, ai_name)].append(
                {"role": role, "parts": [content]}
            )
        except KeyError as e:
            print(f"[CRITICAL ERROR] KeyError при добавлении сообщения! {e}")
            raise  # Повторно вызываем ошибку, чтобы видеть стек вызова

        # Сохраняем в БД
        try:
            # Получаем текущую историю
            cursor.execute(
                "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
                (chat_id, ai_name)
            )
            result = cursor.fetchone()

            # Загружаем существующие сообщения
            old_messages = []
            if result and result[0]:
                if isinstance(result[0], list):
                    old_messages = result[0]
                elif isinstance(result[0], str):
                    try:
                        old_messages = json.loads(result[0])
                    except json.JSONDecodeError:
                        print("[ERROR] JSONDecodeError! Используем пустой список.")
                        old_messages = []

            # Объединяем старые и новые сообщения
            new_messages = old_messages + [{"role": role, "parts": [content]}]
        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении в БД: {e}")
            print(traceback.format_exc())

    async def get_dialog_history(chat_id: int, ai_name: str) -> list:
        """
        Получает всю историю диалога из БД.

        Args:
            chat_id: ID чата пользователя
            ai_name: Название AI модели

        Returns:
            list: Список сообщений диалога
        """
        cursor.execute(
            "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
            (chat_id, ai_name)
        )
        result = cursor.fetchone()

        if result:
            return json.loads(result[0])
        return []

    @dp.message(Command('user_states'))
    async def show_user_states(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        await message.answer(f"👥 *Состояния пользователей:*\n{user_states}", parse_mode=ParseMode.MARKDOWN)

    @dp.message(Command('send_keyboard'))
    async def send_keyboard_command(message: types.Message):
        """Отправляет клавиатуру всем пользователям (только для админа)."""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        await message.answer("Начинаю отправку клавиатуры всем пользователям...")
        await send_keyboard_to_all_users(dp.bot)
        await message.answer("✅ Клавиатура отправлена всем пользователям.")

    @dp.message(Command('dialog_sessions'))
    async def show_dialog_sessions(message: types.Message):
        """Показывает историю диалогов (только для админа)."""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

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

    @dp.message(Command('active_generations'))
    async def show_active_generations(message: types.Message):
        """Показывает активные генерации (только для админа)."""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        await message.answer(
            f"⚙️ *Активные генерации:*\n{active_generations}",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    @dp.message(F.text == '⬅️ Назад')
    async def back(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        current_state = user_states.get(chat_id)

        state_transitions = {
            'gemini_dialog': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'g4f_dialog': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'ai_selection': ('main_menu', get_main_keyboard(), "Возврат в главное меню."),
            'text_text': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'text_image': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'text_voice': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'nocode': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'gemini_model_selection': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'g4f_model_selection': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'mistral_model_selection': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'appearance': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'photo': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'midjourney_dialog': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI."),
            'mistral_dialog': ('ai_selection', get_ai_selection_keyboard(), "Возврат в меню выбора AI.")
        }

        if current_state in state_transitions:
            new_state, keyboard, message_text = state_transitions[current_state]
            await message.answer(message_text, reply_markup=keyboard)
            await save_user_state(state, new_state)
            # Очищаем состояние FSM если возвращаемся в главное меню или меню выбора AI
            if new_state in ['main_menu', 'ai_selection']:
                await state.clear()
        else:
            # Если состояние не определено, возвращаемся в главное меню
            await message.answer("Возврат в главное меню.", reply_markup=get_main_keyboard())
            await save_user_state(state, 'main_menu')
            await state.clear()

        # Очищаем историю диалога при возврате
        if chat_id in dialog_sessions:
            dialog_sessions.pop(chat_id, None)
        if chat_id in g4f_dialog_sessions:
            g4f_dialog_sessions.pop(chat_id, None)

    @dp.message(F.text == 'Видео')
    async def handle_video(message: types.Message):
        await message.answer("Видео недоступно на сервере.",
                             reply_markup=get_main_keyboard())
        # Сохраняем состояние
        await save_user_state(message.chat.id, 'main_menu')

    @dp.message(F.text == 'Компьютер')
    async def handle_computer(message: types.Message):
        await message.answer("Функции управления компьютером недоступны.",
                             reply_markup=get_main_keyboard())
        # Сохраняем состояние
        await save_user_state(message.chat.id, 'main_menu')

    class ChatBotG4F:
        def __init__(self):
            self.client = Client()
            self.messages = []

        def set_model(self, model_name: str):
            """Устанавливает модель для G4F"""
            self.model_name = model_name

        async def ask(self, user_input: str) -> str:
            """Отправляет запрос в G4F и получает ответ"""
            self.messages.append({"role": "user", "content": user_input})

            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=self.messages,
                )
                reply = response.choices[0].message.content
                self.messages.append({"role": "assistant", "content": reply})
                return reply
            except Exception as err:
                logger.error(f"Ошибка при запросе к {self.model_name}: {err}")
                return "Не удалось получить ответ."

    # Создаем экземпляр бота для G4F
    g4f_bot = ChatBotG4F()

    @dp.message(F.text == 'Нейросети')
    async def handle_ai(message: types.Message):
        # Сохраняем пользователя
        await save_user(message)
        await message.answer(
            "Выберите AI:",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @dp.message(F.text == '🦆 Нейросети в интернете')
    async def handle_ai_web(message: types.Message):
        # Сохраняем пользователя
        await save_user(message)
        await message.answer(
            "Открываю",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @dp.message(F.text == '🤖 Выбор AI')
    async def choose_ai(message: types.Message):
        # Сохраняем пользователя
        await save_user(message)
        await message.answer(
            "Выберите AI:",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @dp.message(F.text.in_(['ChatGPT🌐', 'Gemini', 'G4F (Аналог ChatGPT)', 'Microsoft Copilot🌐', 'Github Copilot🌐', 'Mistral AI']))
    async def handle_ai_choice(message: types.Message, state: FSMContext):
        chat_id = message.chat.id

        # Очищаем предыдущие состояния и истории диалогов
        if chat_id in dialog_sessions:
            dialog_sessions.pop(chat_id, None)
        if chat_id in g4f_dialog_sessions:
            g4f_dialog_sessions.pop(chat_id, None)
        await state.clear()

        if message.text == 'Gemini':
            await message.answer(
                "Вы выбрали Gemini.",
                reply_markup=get_gemini_model_keyboard()
            )
            await save_user_state(state, 'gemini_model_selection')
            await state.set_state(DialogStates.waiting_for_model_selection)

        elif message.text == 'G4F (Аналог ChatGPT)':
            await message.answer(
                "Вы выбрали G4F. Выберите модель:",
                reply_markup=get_g4f_model_keyboard()
            )
            await save_user_state(state, 'g4f_model_selection')
            await state.set_state(DialogStates.waiting_for_g4f_model)

        elif message.text == 'Mistral AI':
            await message.answer(
                "Вы выбрали Mistral AI. Выберите модель:",
                reply_markup=get_mistral_model_keyboard()
            )
            await save_user_state(state, 'mistral_model_selection')
            await state.set_state(DialogStates.waiting_for_mistral_model)

        elif message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в главное меню.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'main_menu')
            await state.clear()  # Очищаем состояние FSM

    @dp.message(StateFilter(DialogStates.waiting_for_g4f_model))
    async def handle_g4f_model_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await choose_ai(message)
            await state.finish()
            return

        model_mapping = {
            'GPT 4o mini': 'gpt-4o-mini',
        }

        model_name = model_mapping.get(message.text)

        if model_name:
            g4f_bot.set_model(model_name)
            await message.answer(
                f"Вы выбрали {model_name}. Введите ваш запрос:",
                reply_markup=get_dialog_keyboard()
            )
            await save_user_state(state, 'g4f_dialog')
            await state.set_state(DialogStates.waiting_for_g4f_dialog)
        else:
            await message.answer("Неверный выбор модели. Попробуйте снова.")

    @dp.callback_query(F.data.startswith("stop_"))
    async def stop_generation(call: types.CallbackQuery):
        chat_id = int(call.data.split("_")[1])
        active_generations[chat_id] = False
        await call.message.edit_text("⏹️ Генерация остановлена.")

    @dp.message(StateFilter(DialogStates.waiting_for_model_selection))
    async def handle_model_selection(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        model_name = None

        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.clear()  # Очищаем состояние FSM
            return

        # Очищаем предыдущие состояния и истории диалогов
        if chat_id in dialog_sessions:
            dialog_sessions.pop(chat_id, None)
        if chat_id in g4f_dialog_sessions:
            g4f_dialog_sessions.pop(chat_id, None)

        # Маппинг моделей
        model_mapping = {
            'Gemini 2.0 Experimental': 'gemini-2.0-flash-exp',
            'Gemini 1.5 Pro': 'gemini-1.5-pro',
            'Gemini 1.5 Flash': 'gemini-1.5-flash',
            'Gemini 2.0 Pro Experimental 02-05': 'gemini-2.0-pro-exp-02-05',
            'Gemini 2.0 Flash Thinking Experimental 01-21': 'gemini-2.0-flash-thinking-exp-01-21',
            'Gemini 2.0 Flash-Lite Preview 02-05': 'gemini-2.0-flash-lite-preview-02-05',
            'Gemini 2.0 Flash': 'gemini-2.0-flash'
        }

        model_name = model_mapping.get(message.text)

        if not model_name:
            await message.answer("Неверный выбор модели. Попробуйте снова.")
            return

        # Сохраняем выбранную модель в состояние
        await state.update_data(model_name=model_name)

        await message.answer(
            f"Вы выбрали: {model_name}. Начните диалог.",
            reply_markup=get_dialog_keyboard()
        )
        await save_user_state(state, 'gemini_dialog')
        await state.set_state(DialogStates.waiting_for_dialog)

    def translate_text(text, target_lang="en"):
        return GoogleTranslator(source="auto", target=target_lang).translate(text)

    @dp.message(lambda message: message.text == 'Midjourney')
    async def handle_midjourney_choice(message: Message):
        await message.answer(
            "Вы выбрали Midjourney. Введите запрос для генерации изображения.",
            reply_markup=get_dialog_keyboard()
        )
        user_states[message.chat.id] = 'midjourney_dialog'

    @dp.message(lambda message: user_states.get(message.chat.id) == 'midjourney_dialog')
    async def handle_midjourney(message: Message):
        chat_id = message.chat.id
        if message.text in ['⬅️ Назад', '⏹️ Завершить диалог']:
            await message.answer(
                "Возврат в меню нейросетей.",
                reply_markup=get_ai_selection_keyboard()
            )
            user_states.pop(chat_id, None)
            return

        translated_text = translate_text(message.text)

        loading_message = await message.answer("Генерация картинки...")

        stop_event = threading.Event()
        loading_thread = threading.Thread(
            target=lambda: asyncio.run(
                update_loading_message(loading_message, stop_event))
        )
        loading_thread.start()

        start_time = time.time()

        # 🖼️ Запрос к API для генерации картинки
        client = Client()
        response = client.images.generate(
            model="flux",
            prompt=translated_text,
            response_format="url"
        )

        image_url = response.data[0].url
        image_data = requests.get(image_url).content

        stop_event.set()
        loading_thread.join()

        elapsed_time = round(time.time() - start_time, 2)

        await dp.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=loading_message.message_id,
            text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
        )
        await dp.bot.send_photo(message.chat.id, photo=image_data)

    async def update_loading_message(message: Message, stop_event):
        dots = ""
        counter = 0

        while not stop_event.is_set():
            dots = "." * (counter % 4)
            elapsed_time = counter
            new_text = f"Генерация картинки{dots}\nГенерируется лишь: {elapsed_time} сек"

            try:
                await dp.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=new_text
                )
            except Exception:
                pass

            counter += 1
            await asyncio.sleep(1)

    @dp.message(lambda message: message.text == 'Текст-Текст')
    async def handle_ai_text_text(message: Message):
        await message.answer(
            """📄 *Категория: Текст-Текст*

            Нейросети для работы с текстом:
            - *ChatGPT* – генерация и анализ текста.
            - *Gemini* – текстовая обработка от Google.
            - *G4F* – бесплатная альтернатива ChatGPT.
            - *Microsoft Copilot* – помощник для программистов.
            - *Github Copilot* – помощник для программистов.

            Выберите модель:""",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_text_text_button()
        )

    async def handle_ai_category(message: types.Message, category: str, text: str, keyboard):
        await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await save_user_state(message.chat.id, category)

    @dp.message(lambda message: message.text == 'Текст-Изображение')
    async def handle_ai_text_image(message: types.Message, state: FSMContext):
        await handle_ai_category(
            message, 'text_image',
            """🖼️ *Категория: Текст-Изображение*

            Нейросети для генерации изображений:
            - *Midjourney* – создание детализированных картинок.

            Выберите сервис:""",
            get_text_image_button()
        )
        await state.set_state(DialogStates.waiting_for_text_image)

    @dp.message(lambda message: message.text == 'Текст-Голос')
    async def handle_ai_text_voice(message: types.Message, state: FSMContext):
        await handle_ai_category(
            message, 'text_voice',
            """🔊 *Категория: Текст-Голос*

            Нейросети для озвучивания текста:
            - *Hailuo* – генерация естественной речи.
            - *Hugging Face Audiobook* – конвертация текста в аудиокниги.

            Выберите сервис:""",
            get_text_voice_keyboard()
        )
        await state.set_state(DialogStates.waiting_for_text_voice)

    @dp.message(lambda message: message.text == 'NoCode')
    async def handle_ai_nocode(message: types.Message, state: FSMContext):
        await handle_ai_category(
            message, 'nocode',
            """🛠️ *Категория: NoCode*

            Платформы для разработки без кода:
            - *Glide* – создание мобильных приложений.

            Выберите платформу:""",
            get_nocode_keyboard()
        )
        await state.set_state(DialogStates.waiting_for_nocode)

    @dp.message(lambda message: message.text == 'Внешность')
    async def handle_ai_appearance(message: types.Message, state: FSMContext):
        await handle_ai_category(
            message, 'appearance',
            """🎭 *Категория: Внешность*

            Сервисы для изменения внешности:
            - *Tough Tongue AI* – ваш ИИ-клон для онлайн-конференций.

            Выберите сервис:""",
            get_appearance_keyboard()
        )
        await state.set_state(DialogStates.waiting_for_appearance)

    @dp.message(lambda message: message.text == 'Фото')
    async def handle_ai_photo(message: types.Message, state: FSMContext):
        await message.answer(
            """📸 *Категория: Фото*

            Сервисы для обработки изображений:
            - *Memenome* – создание видео с текстом для людей с СДВГ.

            Выберите сервис:""",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_photo_keyboard()
        )
        await save_user_state(message.chat.id, 'photo')
        await state.set_state(DialogStates.waiting_for_photo)

    @dp.message(Command('gemini'))
    async def handle_gemini_command(message: types.Message, state: FSMContext):
        """Запуск Gemini по команде /gemini"""
        chat_id = message.chat.id
        # Устанавливаем модель по умолчанию
        model_name = 'gemini-2.0-flash-exp'

        # Сохраняем модель в состояние
        await state.update_data(model_name=model_name)

        await message.answer("Вы выбрали Gemini.\nВведите запрос:", reply_markup=get_dialog_keyboard())
        await save_user_state(state, 'gemini_dialog')
        # Устанавливаем состояние ожидания диалога
        await state.set_state(DialogStates.waiting_for_dialog)  # ИСПРАВЛЕНО

    @dp.message(Command('g4f'))
    async def handle_g4f_command(message: types.Message, state: FSMContext):
        """Запуск G4F по команде /g4f"""
        chat_id = message.chat.id
        g4f_bot.set_model("gpt-4o-mini")
        await message.answer("Вы выбрали G4F. Введите ваш запрос:", reply_markup=get_dialog_keyboard())
        await save_user_state(state, 'g4f_dialog')

    @dp.message(Command('midjourney'))
    async def handle_midjourney_command(message: types.Message, state: FSMContext):
        """Запуск Midjourney по команде /midjourney"""
        chat_id = message.chat.id
        await message.answer("Вы выбрали Midjourney. Введите запрос для генерации изображения:",
                             reply_markup=get_dialog_keyboard())
        await save_user_state(state, 'midjourney_dialog')

    @dp.message(Command('mistral'))
    async def handle_mistral_command(message: types.Message, state: FSMContext):
        """Запуск Mistral AI по команде /mistral"""
        chat_id = message.chat.id
        await message.answer("Вы выбрали Mistral AI. Выберите модель:", reply_markup=get_mistral_model_keyboard())
        await save_user_state(state, 'mistral_model_selection')
        await state.set_state(DialogStates.waiting_for_mistral_model)

    # Добавляем обработчик для состояния waiting_for_dialog
    @dp.message(StateFilter(DialogStates.waiting_for_dialog))
    async def process_dialog_message(message: types.Message, state: FSMContext):
        """Обработчик сообщений в состоянии диалога с Gemini"""
        logger.info(
            f"process_dialog_message вызван: chat_id={message.chat.id}, текст={message.text}")
        data = await state.get_data()
        logger.info(f"Данные состояния: {data}")
        model_name = data.get('model_name')
        logger.info(f"Выбранная модель: {model_name}")

        if not model_name:
            model_name = 'gemini-2.0-flash-exp'
            logger.warning(
                f"Модель не найдена в состоянии, используем {model_name}")

        # Проверяем, есть ли изображения в сообщении
        if message.photo or message.media_group_id:
            try:
                images = []
                temp_files = []

                if message.media_group_id:
                    # Получаем все фото из группы
                    media_group = message.photo
                    for i, photo in enumerate(media_group):
                        file_info = await message.bot.get_file(photo.file_id)
                        downloaded_file = await message.bot.download_file(file_info.file_path)

                        # Создаем уникальное имя файла для каждого изображения
                        temp_filename = f"temp_image_{message.chat.id}_{i}.jpg"
                        temp_files.append(temp_filename)

                        with open(temp_filename, "wb") as new_file:
                            new_file.write(downloaded_file.read())

                        img = PIL.Image.open(temp_filename)
                        images.append(img)
                else:
                    # Обработка одиночного изображения
                    photo = message.photo[-1]
                    file_info = await message.bot.get_file(photo.file_id)
                    downloaded_file = await message.bot.download_file(file_info.file_path)

                    temp_filename = f"temp_image_{message.chat.id}_0.jpg"
                    temp_files.append(temp_filename)

                    with open(temp_filename, "wb") as new_file:
                        new_file.write(downloaded_file.read())

                    img = PIL.Image.open(temp_filename)
                    images.append(img)

                # Если есть текст с изображениями
                prompt = message.caption if message.caption else "Опишите эти изображения"

                # Создаем модель и генерируем ответ
                model = genai.GenerativeModel(model_name)

                # Формируем запрос с изображениями
                request = [prompt] + images
                response = await asyncio.to_thread(model.generate_content, request)

                # Удаляем временные файлы
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        logger.warning(
                            f"Не удалось удалить временный файл {temp_file}: {e}")

                # Отправляем ответ
                await safe_send_message(message, response.text)

            except Exception as e:
                logger.error(f"Ошибка при обработке изображения: {e}")
                await message.answer(f"Произошла ошибка при обработке изображения: {str(e)}")

                # Пытаемся удалить временные файлы в случае ошибки
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception as e:
                        logger.warning(
                            f"Не удалось удалить временный файл {temp_file}: {e}")
        else:
            # Обычная обработка текстового сообщения
            await handle_dialog(message, state, model_name)

    # Обработчик для диалога с Mistral
    @dp.message(StateFilter(DialogStates.waiting_for_mistral_dialog))
    async def handle_mistral_dialog(message: types.Message, state: FSMContext):
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            # Удаляем все диалоги пользователя из локального кэша
            keys_to_delete = [(cid, ai) for (cid, ai)
                              in dialog_sessions.keys() if cid == chat_id]
            for key in keys_to_delete:
                dialog_sessions.pop(key, None)

            await message.answer(
                "Диалог завершен.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        elif message.text == '⬅️ Назад':
            # Удаляем все диалоги пользователя из локального кэша
            keys_to_delete = [(cid, ai) for (cid, ai)
                              in dialog_sessions.keys() if cid == chat_id]
            for key in keys_to_delete:
                dialog_sessions.pop(key, None)

            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        try:
            # Получаем выбранную модель из состояния
            data = await state.get_data()
            # По умолчанию используем mistral-small-latest
            model_name = data.get('mistral_model', 'mistral-small-latest')

            # Сохраняем сообщение пользователя
            await save_dialog_message(chat_id, "mistral", "user", message.text)
            sent_message = await message.answer("Генерация ответа...")

            # Получаем историю диалога из локального кэша
            messages = dialog_sessions.get((chat_id, "mistral"), [])
            print(
                f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

            # Преобразуем сообщения в формат Mistral
            mistral_messages = []
            for msg in messages:
                if isinstance(msg, dict) and "role" in msg and ("parts" in msg or "content" in msg):
                    content = msg.get("parts", [None])[
                        0] if "parts" in msg else msg.get("content")
                    if content:
                        mistral_messages.append({
                            "role": msg["role"],
                            "content": content
                        })

            # Запрос к Mistral AI с выбранной моделью
            chat_response = mistral_client.chat.complete(
                model=model_name,
                messages=mistral_messages
            )

            response_text = chat_response.choices[0].message.content

            # Сохраняем ответ модели
            await save_dialog_message(chat_id, "mistral", "assistant", response_text)

            # Отправляем ответ
            await sent_message.delete()
            await safe_send_message(message, response_text)

        except Exception as e:
            logger.error(f"Ошибка Mistral API: {e}")
            await message.answer(f"Произошла ошибка при генерации ответа: {str(e)}. Попробуйте позже.")

    @dp.message(Command('get_mistral_models'))
    async def get_mistral_models(message: types.Message):
        """Получение списка доступных моделей Mistral AI"""
        try:
            # Создаем заголовки для запроса
            headers = {
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }

            # Выполняем запрос к API
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.mistral.ai/v1/models", headers=headers) as response:
                    if response.status == 200:
                        models_data = await response.json()

                        if "data" in models_data and models_data["data"]:
                            models_text = "Доступные модели Mistral AI:\n\n"
                            for model in models_data["data"]:
                                models_text += f"• {model['id']}"
                                if "description" in model:
                                    models_text += f" - {model['description']}"
                                models_text += "\n"
                        else:
                            models_text = "Нет доступных моделей."
                    else:
                        models_text = f"Ошибка при получении списка моделей. Код ответа: {response.status}"

                    await message.answer(models_text)
        except Exception as e:
            logger.error(f"Ошибка при получении списка моделей Mistral: {e}")
            await message.answer("Произошла ошибка при получении списка моделей. Попробуйте позже.")

    @dp.message(StateFilter(DialogStates.waiting_for_mistral_model))
    async def handle_mistral_model_selection(message: types.Message, state: FSMContext):
        """Обработчик выбора модели Mistral AI"""
        chat_id = message.chat.id

        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        # Маппинг моделей с их API именами
        model_mapping = {
            'Ministral 8b': 'ministral-8b-latest',
            'Mistral Medium': 'mistral-medium-latest',
            'Pixtral Large': 'pixtral-large-latest',
            'Codestral': 'codestral-latest',
            'Codestral Mamba': 'codestral-mamba-latest',
            'Pixtral 12b': 'pixtral-12b-latest',
            'Mistral Small': 'mistral-small-latest',
            'Mistral Saba': 'mistral-saba-latest',
            'Mistral Moderation': 'mistral-moderation-latest'
        }

        model_name = model_mapping.get(message.text)
        if not model_name:
            await message.answer("Пожалуйста, выберите модель из предложенных вариантов.")
            return

        # Сохраняем выбранную модель в состояние
        await state.update_data(mistral_model=model_name)

        await message.answer(
            f"Вы выбрали модель {message.text}. Начните диалог:",
            reply_markup=get_dialog_keyboard()
        )
        await save_user_state(state, 'mistral_dialog')
        await state.set_state(DialogStates.waiting_for_mistral_dialog)

    @dp.message(StateFilter(DialogStates.waiting_for_text_image))
    async def handle_text_image_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        if message.text == "Midjourney":
            await message.answer(
                "Вы выбрали Midjourney. Введите запрос для генерации изображения:",
                reply_markup=get_dialog_keyboard()
            )
            await save_user_state(state, 'midjourney_dialog')
            await state.set_state(DialogStates.waiting_for_midjourney)
        else:
            await message.answer("Пожалуйста, выберите сервис из предложенных вариантов.")

    @dp.message(StateFilter(DialogStates.waiting_for_text_voice))
    async def handle_text_voice_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        valid_options = {
            "Озвучка текста": "https://www.hailuo.ai/audio",
            "Озвучка книги": "https://huggingface.co/spaces/drewThomasson/ebook2audiobook"
        }

        if message.text in valid_options:
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text=f"Перейти к {message.text}",
                url=valid_options[message.text]
            )
            markup.add(button)
            await message.answer(
                f"Нажмите кнопку ниже, чтобы перейти к сервису {message.text}:",
                reply_markup=markup
            )
        else:
            await message.answer("Пожалуйста, выберите сервис из предложенных вариантов.")

    @dp.message(StateFilter(DialogStates.waiting_for_nocode))
    async def handle_nocode_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        if message.text == "Glide":
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="Перейти к Glide",
                url="https://www.glideapps.com/"
            )
            markup.add(button)
            await message.answer(
                "Нажмите кнопку ниже, чтобы перейти к Glide:",
                reply_markup=markup
            )
        else:
            await message.answer("Пожалуйста, выберите платформу из предложенных вариантов.")

    @dp.message(StateFilter(DialogStates.waiting_for_appearance))
    async def handle_appearance_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        if message.text == "Tough Tongue AI":
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="Перейти к Tough Tongue AI",
                url="https://app.toughtongueai.com/"
            )
            markup.add(button)
            await message.answer(
                "Нажмите кнопку ниже, чтобы перейти к Tough Tongue AI:",
                reply_markup=markup
            )
        else:
            await message.answer("Пожалуйста, выберите сервис из предложенных вариантов.")

    @dp.message(StateFilter(DialogStates.waiting_for_photo))
    async def handle_photo_selection(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        if message.text == "Memenome":
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="Перейти к Memenome",
                url="https://www.memenome.gg/"
            )
            markup.add(button)
            await message.answer(
                "Нажмите кнопку ниже, чтобы перейти к Memenome:",
                reply_markup=markup
            )
        else:
            await message.answer("Пожалуйста, выберите сервис из предложенных вариантов.")

    @dp.message(StateFilter(DialogStates.waiting_for_midjourney))
    async def handle_midjourney_dialog(message: Message, state: FSMContext):
        chat_id = message.chat.id

        if message.text in ['⬅️ Назад', '⏹️ Завершить диалог']:
            await message.answer(
                "Возврат в меню нейросетей.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        translated_text = translate_text(message.text)
        loading_message = await message.answer("Генерация картинки...")

        stop_event = threading.Event()
        loading_thread = threading.Thread(
            target=lambda: asyncio.run(
                update_loading_message(loading_message, stop_event))
        )
        loading_thread.start()

        start_time = time.time()

        try:
            client = Client()
            response = client.images.generate(
                model="flux",
                prompt=translated_text,
                response_format="url"
            )

            image_url = response.data[0].url
            image_data = requests.get(image_url).content

            stop_event.set()
            loading_thread.join()

            elapsed_time = round(time.time() - start_time, 2)

            await dp.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
            )
            await dp.bot.send_photo(message.chat.id, photo=image_data)
        except Exception as e:
            stop_event.set()
            loading_thread.join()
            await message.answer(f"Произошла ошибка при генерации изображения: {str(e)}")


class UserStateFilter(BaseFilter):
    def __init__(self, state_name: str):
        self.state_name = state_name

    async def __call__(self, message: Message) -> bool:
        return user_states.get(message.chat.id) == self.state_name


# Инициализация Mistral AI клиента
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
