# bot_handlers.py
import re
import threading
import time
import requests
import logging
import os
from src.handlers.mistral import register_mistral_handlers
from src.handlers.gemini import register_gemini_handlers
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
from src.handlers.qwen import register_qwen_handlers

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

    register_gemini_handlers(dp)

    register_mistral_handlers(dp)

    register_qwen_handlers(dp)
    
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

    @dp.message(Command('g4f'))
    async def handle_g4f_command(message: types.Message, state: FSMContext):
        """Запуск G4F по команде /g4f"""
        chat_id = message.chat.id
        g4f_bot.set_model("gpt-4o-mini")
        await message.answer("Вы выбрали G4F. Введите ваш запрос:", reply_markup=get_dialog_keyboard())
        await save_user_state(state, 'g4f_dialog')

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
