# bot_handlers.py
import re
import threading
import time
import requests
import logging
import os
from z.config import ADMIN_ID, POPULAR_SITES, GEMINI_API_KEY, BOT_TOKEN, MISTRAL_API_KEY, TOGETHER_API_KEY
import google.generativeai as genai
from g4f.client import Client
from deep_translator import GoogleTranslator
from aiogram.types import Message
from z.keyboards import *
import psycopg2
import json
import traceback
from aiogram import Dispatcher, Bot, types, F
from aiogram.utils import markdown
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
import asyncio
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from mistralai import Mistral
import aiohttp
import PIL.Image
from src.models.dialog_state import DialogStates, dialog_manager
from src.models.user_state import user_state_manager
from src.database.db_manager import db_manager
from src.admin.admin_handlers import setup_admin_handlers, send_admin_notification, send_keyboard_to_all_users
from src.handlers.midjourney import register_midjourney_handlers

# Константы для Qwen
API_URL = "https://api.together.xyz/inference"

# Инициализируем диспетчер с хранилищем состояний
dp = Dispatcher(storage=MemoryStorage())

# Получаем URL базы данных из переменной окружения, если она есть
DATABASE_URL = os.environ.get("DB_URL")
RAILWAY_DB_URL = "postgresql://postgres:tocutLkkpvyyDLmYnEPZrrovLcTbjFvA@postgres.railway.internal:5432/railway"
LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:5433/postgres"

conn = None

try:
    if DATABASE_URL:
        print(f"Попытка подключения к удаленной базе: {DATABASE_URL}")
        conn = psycopg2.connect(DATABASE_URL)
    else:
        raise psycopg2.OperationalError(
            "Переменная окружения DB_URL не задана, пробуем Railway...")

except psycopg2.Error as e:
    print(f"Ошибка при подключении к {DATABASE_URL}: {e}. Пробуем Railway...")

    try:
        conn = psycopg2.connect(RAILWAY_DB_URL)
        print("Успешно подключено к Railway!")
    except psycopg2.Error as e:
        print(
            f"Ошибка при подключении к Railway: {e}. Пробуем локальную базу...")

        try:
            conn = psycopg2.connect(LOCAL_DB_URL)
            print("Переключено на локальную базу данных!")
        except psycopg2.Error as e:
            print(
                f"Ошибка при подключении к локальной базе данных: {e}. Программа завершена.")
            exit(1)

cursor = conn.cursor()
print("Подключение успешно!")


# Добавляем функцию для получения всех пользователей из базы данных


async def get_all_users():
    return await db_manager.get_all_users()

# Добавляем функцию для сохранения пользователя в базу данных


async def save_user(message: types.Message):
    try:
        await db_manager.save_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
    except Exception as e:
        print(f"Ошибка при сохранении пользователя: {e}")

# Добавляем функцию для отправки клавиатуры всем пользователям


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

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

dialog_sessions = {}  # Словарь для хранения истории диалогов
g4f_dialog_sessions = {}
active_generations = {}  # Словарь для отслеживания генерации сообщений
user_states = {}  # {chat_id: [state1, state2, ...]}


async def setup_handlers(bot):
    # Отправляем уведомление администратору при запуске
    await send_admin_notification(bot)

    # Регистрируем обработчики Midjourney
    register_midjourney_handlers(dp)

    # Настраиваем административные обработчики
    await setup_admin_handlers(dp, db_manager, dialog_sessions, active_generations)

    # Отправляем клавиатуру всем пользователям при запуске
    await send_keyboard_to_all_users(bot, db_manager)

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

    def process_code_block(text: str) -> list:
        """
        Разделяет текст на обычный текст и блоки кода.
        Возвращает список кортежей (текст, is_code).
        """
        parts = []
        pattern = r'```(?:python)?\n([\s\S]*?)```'
        last_end = 0

        for match in re.finditer(pattern, text):
            if match.start() > last_end:
                parts.append((text[last_end:match.start()], False))

            parts.append((match.group(1), True))
            last_end = match.end()

        if last_end < len(text):
            parts.append((text[last_end:], False))

        return parts if parts else [(text, False)]

    def to_markdown(text: str) -> str:
        """
        Преобразует текст в формат Markdown для Telegram.
        Обрабатывает жирный текст, код и другие элементы.
        """
        bold_texts = []

        def save_bold(match):
            inner_text = match.group(1)
            bold_texts.append(inner_text)
            return f"§BOLD{len(bold_texts)-1}§"

        math_exprs = []

        def save_math(match):
            math_exprs.append(match.group(0))
            return f"§MATH{len(math_exprs)-1}§"

        # Сначала сохраняем математические выражения
        # Сохраняем сложные математические выражения с последовательными умножениями
        text = re.sub(
            r'(?:\d+(?:/\d+)?|\(\d+(?:/\d+)?\))(?:\s*\*\s*(?:\d+(?:/\d+)?|\(\d+(?:/\d+)?\)))+', save_math, text)
        # Сохраняем простые умножения вида 2 * 3
        text = re.sub(r'\d+\s*\*\s*\d+', save_math, text)
        # Сохраняем степени вида ^6
        text = re.sub(r'\^[0-9]+', save_math, text)

        # Сохраняем маркеры списка, заменяя их временно
        text = re.sub(r'^(\s*)\*(\s+)', r'\1§LIST§\2',
                      text, flags=re.MULTILINE)

        # Обрабатываем двойные звездочки (обычный жирный текст)
        text = re.sub(r'\*\*(.*?)\*\*', save_bold, text, flags=re.DOTALL)

        # Обрабатываем одиночные звездочки (если это не маркер списка)
        text = re.sub(r'\*([^*\n]+)\*', save_bold, text)

        # Возвращаем маркеры списка
        text = text.replace('§LIST§', '*')

        # Заменяем HTML-теги
        text = re.sub(r'<sup>([^<]+)</sup>', r'^\1', text)
        text = re.sub(r'<sub>([^<]+)</sub>', r'_\1', text)

        # Заменяем маркеры списка на буллеты
        text = re.sub(r'^\s*\*\s+', '• ', text, flags=re.MULTILINE)

        # Экранируем специальные символы Markdown
        special_chars = '_*[]()~>#+-=|{}.!\\'
        escaped_text = ''.join(
            f'\\{char}' if char in special_chars else char for char in text)
        text = escaped_text

        # Вставляем назад жирный текст
        for i, bold_text in enumerate(bold_texts):
            escaped_bold = ''.join(
                f'\\{char}' if char in special_chars and char != '*' else char for char in bold_text)
            text = text.replace(f"§BOLD{i}§", f"*{escaped_bold}*")

        # Вставляем назад математические выражения
        for i, math_expr in enumerate(math_exprs):
            escaped_expr = ''.join(
                f'\\{char}' if char in special_chars else char for char in math_expr)
            text = text.replace(f"§MATH{i}§", escaped_expr)

        return text

    async def safe_send_message(message: types.Message, text: str):
        MAX_LENGTH = 3500
        try:
            parts = process_code_block(text)
            current_message = ""

            for content, is_code in parts:
                if not content.strip():
                    continue

                if is_code:
                    if current_message:
                        try:
                            await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                        except Exception as e:
                            if "can't parse entities: Can't find end of Bold" in str(e):
                                # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                                fixed_text = current_message
                                # Если нечетное количество звездочек
                                if fixed_text.count('*') % 2 != 0:
                                    fixed_text += '*'
                                await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                            else:
                                await message.answer(current_message)
                        current_message = ""

                    # Разбиваем длинный код на части
                    code_parts = [content[i:i + MAX_LENGTH]
                                  for i in range(0, len(content), MAX_LENGTH)]
                    for code_part in code_parts:
                        try:
                            await message.answer(f"```\n{code_part}\n```", parse_mode=ParseMode.MARKDOWN_V2)
                        except Exception as e:
                            if "can't parse entities: Can't find end of PreCode entity" in str(e):
                                # Если ошибка связана с незакрытым блоком кода, добавляем закрывающие символы
                                fixed_code = code_part
                                if not fixed_code.endswith('\n'):
                                    fixed_code += '\n'
                                await message.answer(f"```\n{fixed_code}\n```", parse_mode=ParseMode.MARKDOWN_V2)
                            else:
                                await message.answer(code_part)
                else:
                    formatted_text = to_markdown(content)

                    if len(current_message) + len(formatted_text) > MAX_LENGTH:
                        try:
                            await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                        except Exception as e:
                            if "can't parse entities: Can't find end of Bold" in str(e):
                                # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                                fixed_text = current_message
                                # Если нечетное количество звездочек
                                if fixed_text.count('*') % 2 != 0:
                                    fixed_text += '*'
                                await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                            else:
                                await message.answer(current_message)
                        current_message = formatted_text
                    else:
                        current_message += formatted_text

            if current_message:
                try:
                    await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                except Exception as e:
                    if "can't parse entities: Can't find end of Bold" in str(e):
                        # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                        fixed_text = current_message
                        # Если нечетное количество звездочек
                        if fixed_text.count('*') % 2 != 0:
                            fixed_text += '*'
                        await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                    else:
                        await message.answer(current_message)

        except Exception as e:
            print(f"Ошибка форматирования: {e}")
            # Если произошла ошибка форматирования, разбиваем текст на части и отправляем без форматирования
            text_parts = [text[i:i + MAX_LENGTH]
                          for i in range(0, len(text), MAX_LENGTH)]
            for part in text_parts:
                await message.answer(part)

    async def handle_dialog(message: types.Message, state: FSMContext, model_name: str, test_query: str = None):
        chat_id = message.chat.id
        try:
            if message.text == '⏹️ Завершить диалог':
                await message.answer(
                    "Диалог завершен.",
                    reply_markup=get_ai_selection_keyboard()
                )
                dialog_manager.clear_dialog_history(chat_id, model_name)
                await save_user_state(state, 'ai_selection')
                await state.clear()
                return

            query = test_query if test_query else message.text
            await db_manager.save_dialog_message(chat_id, model_name, "user", query)

            sent_message = await message.answer("Генерация ответа...")
            dialog_manager.set_active_generation(chat_id, True)

            try:
                model = genai.GenerativeModel(model_name)
                messages = await db_manager.get_dialog_history(chat_id, model_name)
                print(
                    f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

                response = await asyncio.to_thread(model.generate_content, messages)
                response_text = response.text
                await db_manager.save_dialog_message(chat_id, model_name, "model", response_text)

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
            await state.clear()  # Было finish(), заменено на clear()
            return

        elif message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора G4F модели.",
                reply_markup=get_g4f_model_keyboard()
            )
            await save_user_state(state, 'g4f_model_selection')
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            await state.clear()  # Было finish(), заменено на clear()
            return

        query = message.text
        await db_manager.save_dialog_message(chat_id, "g4f", "user", query)

        if chat_id not in g4f_dialog_sessions:
            g4f_dialog_sessions[chat_id] = []

        g4f_dialog_sessions[chat_id].append({"role": "user", "content": query})

        sent_message = await message.answer("Генерация ответа...")
        active_generations[chat_id] = True  # Помечаем генерацию активной

        try:
            response = await asyncio.to_thread(g4f_bot.ask, query)
            await db_manager.save_dialog_message(chat_id, "g4f", "assistant", response)

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
        Обертка для сохранения состояния пользователя через менеджер состояний
        """
        await user_state_manager.save_user_state(state_or_chat_id, new_state)

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

    @dp.message(F.text == '⬅️ Назад')
    async def back(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        current_state = await user_state_manager.get_user_state(chat_id)

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
        dialog_manager.clear_dialog_history(chat_id)

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

    @dp.message(F.text.in_(['ChatGPT', 'Gemini', 'G4F (Аналог ChatGPT)', 'Microsoft Copilot', 'Github Copilot', 'Mistral AI', 'Qwen']))
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

        elif message.text == 'Qwen':
            dialog_sessions[chat_id] = []
            await message.answer(
                "Начинаю диалог с Qwen. Отправьте ваше сообщение.",
                reply_markup=get_dialog_keyboard()
            )
            await state.set_state(DialogStates.waiting_for_qwen_dialog)

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
            await state.clear()  # Было finish(), заменено на clear()
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

    @dp.message(Command('mistral'))
    async def handle_mistral_command(message: types.Message, state: FSMContext):
        """Запуск Mistral AI по команде /mistral"""
        chat_id = message.chat.id

        # Устанавливаем модель по умолчанию
        model_name = 'mistral-small-latest'

        # Сохраняем модель в состояние
        await state.update_data(mistral_model=model_name)

        await message.answer(
            f"Вы выбрали Mistral AI (модель: {model_name}). Начните диалог:",
            reply_markup=get_dialog_keyboard()
        )
        await save_user_state(state, 'mistral_dialog')
        await state.set_state(DialogStates.waiting_for_mistral_dialog)

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
            await state.clear()  # Было finish(), заменено на clear()
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
            await state.clear()  # Было finish(), заменено на clear()
            return

        try:
            # Получаем выбранную модель из состояния
            data = await state.get_data()
            # По умолчанию используем mistral-small-latest
            model_name = data.get('mistral_model', 'mistral-small-latest')

            # Сохраняем сообщение пользователя
            await db_manager.save_dialog_message(chat_id, "mistral", "user", message.text)
            sent_message = await message.answer("Генерация ответа...")

            # Получаем историю диалога из локального кэша
            messages = dialog_sessions.get((chat_id, "mistral"), [])
            print(
                f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

            # Добавляем текущее сообщение пользователя
            messages.append({
                "role": "user",
                "content": message.text
            })
            dialog_sessions[(chat_id, "mistral")] = messages

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

            # Если история пуста, добавляем хотя бы текущее сообщение
            if not mistral_messages:
                mistral_messages.append({
                    "role": "user",
                    "content": message.text
                })

            # Запрос к Mistral AI с выбранной моделью
            chat_response = mistral_client.chat.complete(
                model=model_name,
                messages=mistral_messages
            )

            response_text = chat_response.choices[0].message.content

            # Сохраняем ответ модели
            await db_manager.save_dialog_message(chat_id, "mistral", "assistant", response_text)

            # Сохраняем ответ в локальный кэш
            messages.append({
                "role": "assistant",
                "content": response_text
            })
            dialog_sessions[(chat_id, "mistral")] = messages

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
            await state.clear()  # Было finish(), заменено на clear()
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
            await state.clear()  # Было finish(), заменено на clear()
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
            await state.clear()  # Было finish(), заменено на clear()
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
    async def handle_ai_nocode(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.clear()  # Было finish(), заменено на clear()
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
    async def handle_ai_appearance(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.clear()  # Было finish(), заменено на clear()
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
    async def handle_ai_photo(message: types.Message, state: FSMContext):
        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.clear()  # Было finish(), заменено на clear()
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

    def get_qwen_response_stream(messages):
        if not TOGETHER_API_KEY:
            raise ValueError("TOGETHER_API_KEY не настроен в .env файле")

        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "messages": messages,
            "stream": True
        }

        try:
            response = requests.post(
                API_URL, headers=headers, json=data, stream=True)

            if response.status_code != 200:
                print(
                    f"Error: {response.status_code}, Response: {response.text}")
                yield None
                return

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    # Выводим сырые данные API
                    # print(f"[DEBUG] raw line: {decoded_line}")

                    if decoded_line.startswith('data: '):
                        json_data = decoded_line[len('data: '):].strip()
                        if json_data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(json_data)
                            # Показываем, что в JSON
                            # print(f"[DEBUG] parsed JSON: {chunk}")

                            if 'choices' in chunk and chunk['choices']:
                                content = chunk['choices'][0].get(
                                    'text', '')  # Исправлено!
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            print(
                                f"[ERROR] Ошибка декодирования JSON: {json_data}")
                            continue

        except Exception as e:
            print(f"Error in get_qwen_response_stream: {e}")
            raise

    @dp.message(Command('qwen'))
    async def handle_qwen_command(message: types.Message, state: FSMContext):
        """Обработчик команды /qwen"""
        chat_id = message.chat.id
        dialog_sessions[chat_id] = []

        await message.answer(
            "Начинаю диалог с Qwen. Отправьте ваше сообщение.",
            reply_markup=get_dialog_keyboard()
        )
        await state.set_state(DialogStates.waiting_for_qwen_dialog)

    @dp.message(StateFilter(DialogStates.waiting_for_qwen_dialog))
    async def handle_qwen_dialog(message: types.Message, state: FSMContext):
        """Обработчик диалога с Qwen"""
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            await message.answer(
                "Диалог завершен.",
                reply_markup=get_ai_selection_keyboard()
            )
            if chat_id in dialog_sessions:
                del dialog_sessions[chat_id]
            await state.clear()
            return

        sent_message = await message.answer("Генерация ответа...")
        response_text = ""

        try:
            # Сохраняем сообщение пользователя
            await db_manager.save_dialog_message(chat_id, "qwen", "user", message.text)
            print(f"[LOG] Сообщение пользователя сохранено: {message.text}")

            # Получаем историю диалога
            messages = dialog_sessions.get(chat_id, [])
            messages.append({"role": "user", "content": message.text})
            print(f"[LOG] История диалога: {messages}")

            # Таймер для обновления сообщений
            last_update_time = asyncio.get_event_loop().time()

            for chunk in get_qwen_response_stream(messages):
                if chunk:
                    response_text += chunk

                    # Обновляем сообщение каждые 2 секунды
                    if asyncio.get_event_loop().time() - last_update_time > 2:
                        try:
                            await sent_message.edit_text(f"Генерация ответа...\n\n{response_text[-500:]}")
                        except Exception:
                            pass  # Иногда API Telegram не дает обновлять сообщение слишком часто
                        last_update_time = asyncio.get_event_loop().time()

            if not response_text.strip():
                print("[ERROR] Получен пустой ответ от API")
                await message.answer("Получен пустой ответ от API. Попробуйте еще раз.")
                await sent_message.delete()
                return

            # Сохраняем ответ модели
            await db_manager.save_dialog_message(chat_id, "qwen", "assistant", response_text)
            print(f"[LOG] Ответ модели сохранен: {response_text[:100]}...")

            # Обновляем историю диалога
            messages.append({"role": "assistant", "content": response_text})
            dialog_sessions[chat_id] = messages

            # Отправляем ответ пользователю
            await sent_message.delete()
            await safe_send_message(message, response_text)

        except Exception as e:
            print(f"[ERROR] Ошибка в диалоге Qwen: {e}")
            await message.answer(
                "Произошла ошибка при обработке запроса. Попробуйте позже.",
                reply_markup=get_dialog_keyboard()
            )
            if sent_message:
                await sent_message.delete()

# Инициализация Mistral AI клиента
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
