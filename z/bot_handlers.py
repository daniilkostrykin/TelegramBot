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
from src.handlers.g4f import register_g4f_handlers

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
    """Обновляет клавиатуру у всех пользователей"""
    try:
        users = await db_manager.get_all_users()
        logger.info(f"Обновление клавиатуры для {len(users)} пользователей...")

        for chat_id in users:
            try:
                # Получаем ID последнего сообщения
                last_message_id = await db_manager.get_last_message(chat_id)

                if last_message_id:
                    try:
                        # Пробуем обновить клавиатуру в последнем сообщении
                        await bot.edit_message_reply_markup(
                            chat_id=chat_id,
                            message_id=last_message_id,
                            reply_markup=get_main_keyboard()
                        )
                        continue  # Если успешно, переходим к следующему пользователю
                    except Exception as e:
                        logger.debug(f"Не удалось обновить клавиатуру: {e}")

                # Если не получилось обновить, отправляем новое сообщение
                message = await bot.send_message(
                    chat_id=chat_id,
                    text="Бот был перезапущен",
                    reply_markup=get_main_keyboard()
                )
                # Сохраняем ID нового сообщения
                await db_manager.update_last_message(chat_id, message.message_id)

            except Exception as e:
                logger.error(
                    f"Ошибка при обработке пользователя {chat_id}: {e}")

            await asyncio.sleep(0.1)

        logger.info("Клавиатура обновлена для всех пользователей")
    except Exception as e:
        logger.error(f"Ошибка при обновлении клавиатур: {e}")

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

    register_g4f_handlers(dp)

    # Настраиваем административные обработчики
    await setup_admin_handlers(dp, db_manager, dialog_sessions, active_generations)

    # Отправляем клавиатуру всем пользователям при запуске
    await send_keyboard_to_all_users(bot, db_manager)

    @dp.message(Command('start'))
    async def start(message: types.Message):
        try:
            await save_user(message)
            sent_message = await message.answer(
                f"Привет, {message.from_user.first_name}!\n\n"
                "Я бот, который предоставляет доступ к различным нейросетям и другим полезным функциям.\n\n"
                "Вот что я умею:\n"
                "- Работа с текстом (генерация, перевод, суммаризация)\n"
                "- Генерация изображений\n"
                "- Доступ к различным AI-моделям (Gemini, G4F, ChatGPT и др.)\n\n"
                "Чтобы начать, выберите пункт в меню.",
                reply_markup=get_main_keyboard()
            )
            # Сохраняем ID отправленного сообщения
            await db_manager.update_last_message(message.chat.id, sent_message.message_id)
            await save_user_state(message.chat.id, 'main_menu')
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await message.answer('Произошла ошибка')

    async def save_user_state(state_or_chat_id, new_state: str):
        """
        Обертка для сохранения состояния пользователя через менеджер состояний
        """
        await user_state_manager.save_user_state(state_or_chat_id, new_state)

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

    @dp.message(F.text.in_(['ChatGPT', 'Gemini', 'Microsoft Copilot', 'Github Copilot', 'Mistral AI', 'Qwen']))
    async def handle_ai_choice(message: types.Message, state: FSMContext):
        chat_id = message.chat.id

        # Очищаем предыдущие состояния и истории диалогов
        if chat_id in dialog_sessions:
            dialog_sessions.pop(chat_id, None)
        await state.clear()

        if message.text == 'Gemini':
            await message.answer(
                "Вы выбрали Gemini.",
                reply_markup=get_gemini_model_keyboard()
            )
            await save_user_state(state, 'gemini_model_selection')
            await state.set_state(DialogStates.waiting_for_model_selection)

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
            await state.clear()

    @dp.message(lambda message: message.text == 'Текст-Текст')
    async def handle_ai_text_text(message: Message):
        await message.answer(
            """📄 *Категория: Текст-Текст*

            Доступные нейросети:
            
            - *Gemini* – текстовая модель от Google:
              • Gemini Pro – мощная модель для сложных задач
              • Gemini Pro Vision – работа с текстом и изображениями
            
            - *G4F* – бесплатная альтернатива ChatGPT:
              • GPT-4o mini – компактная версия GPT-4
              • Поддержка контекстных диалогов
            
            - *Mistral AI* – европейская языковая модель:
              • Mistral Small – быстрые ответы
              • Mistral Medium – улучшенное качество
              • Mistral Large – максимальная точность
              • Codestral – специализация на коде
            
            - *Qwen* – модель от Alibaba:
              • Высокая производительность
              • Поддержка многих языков
              • Специализация на бизнес-задачах

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
