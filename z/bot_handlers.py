# bot_handlers.py
import re
import threading
import time
import requests
import telebot
from telebot import types
import logging
import os
from z.config import ADMIN_ID, POPULAR_SITES
import google.generativeai as genai
from z.config import GEMINI_API_KEY, BOT_TOKEN
from g4f.client import Client
from deep_translator import GoogleTranslator
from telebot.types import Message
from z.keyboards import *
import psycopg2
import json
import traceback
from aiogram import types, State, StatesGroup
from aiogram.dispatcher import Dispatcher
from aiogram.utils import markdown
from aiogram.dispatcher import FSMContext
import asyncio
from aiogram.dispatcher import FSMContext
import asyncio


class DialogStates(StatesGroup):
    waiting_for_dialog = State()
    waiting_for_g4f_dialog = State()
    waiting_for_model_selection = State()
    waiting_for_g4f_model = State()


# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:XgFOPaWGkymuYpcXKkuSJwIlcPihcHKI@autorack.proxy.rlwy.net:36255/railway")
# Получаем URL базы данных из переменной окружения
DATABASE_URL = os.environ.get("DB_URL")
if not DATABASE_URL:
    print("Ошибка: Не найдена переменная окружения DB_URL из системы.  Убедитесь, что она установлена.")
    DATABASE_URL = "postgresql://postgres:UxAgpKnoEDeQGLsAODlFNlVOirCaoCIa@gondola.proxy.rlwy.net:54556/railway"

dp = Dispatcher()

def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dialog_sessions (
            chat_id BIGINT,
            ai_name TEXT,
            messages JSONB,
            PRIMARY KEY (chat_id, ai_name)
        );
    """)
    print("Database table dialog_sessions created successfully")
    bot.send_message(ADMIN_ID, "✅Бот запущен)")
    conn.commit()


conn = None  # Инициализируем conn вне блока try
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # Выводим сообщение об успешном подключении
    print("Успешно подключено к базе данных!")
    create_tables()
except psycopg2.Error as e:
    print(f"Ошибка при подключении к базе данных: {e}")


logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

dialog_sessions = {}  # Словарь для хранения истории диалогов
g4f_dialog_sessions = {}
active_generations = {}  # Словарь для отслеживания генерации сообщений
user_states = {}  # {chat_id: [state1, state2, ...]}

bot = telebot.TeleBot(BOT_TOKEN)


def setup_handlers(bot):
    @bot.message_handler(commands=['start'])
    async def start(message: types.Message):
        try:
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

    @bot.message_handler(commands=['test'])
    async def test(message: types.Message):
        text = "* Это *не жирный* и не *курсив*, но **это жирный**, а *это курсив*."
        clean_text = clean_text  # Предполагается, что эта переменная определена где-то выше

        # Отправляем сообщение без форматирования
        await message.answer(clean_text)

        # Отправляем сообщение с HTML форматированием
        await message.answer(clean_text, parse_mode=types.ParseMode.HTML)

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

            elif message.text == '⬅️ Назад':
                await message.answer(
                    "Возврат в меню выбора Gemini модели.",
                    reply_markup=get_gemini_model_keyboard()
                )
                await save_user_state(state, 'gemini_model_selection')
                if (chat_id, model_name) in dialog_sessions:
                    print(
                        f"[WARNING] Удаляю dialog_sessions[{(chat_id, model_name)}]")
                    del dialog_sessions[(chat_id, model_name)]
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

                async def safe_send_message(text: str):
                    MAX_LENGTH = 4000
                    try:
                        # Удаляем незакрытые маркеры в конце
                        text = re.sub(r'[*_`][*_`]*$', '', text)

                        # Разбиваем на части если текст длинный
                        for i in range(0, len(text), MAX_LENGTH):
                            chunk = text[i:i + MAX_LENGTH]
                            # Проверяем и закрываем открытые теги форматирования
                            chunk = close_formatting_tags(chunk)
                            await message.answer(
                                chunk,
                                parse_mode=types.ParseMode.MARKDOWN_V2
                            )
                            await asyncio.sleep(0.5)  # Асинхронная задержка
                    except Exception as e:
                        # Если всё ещё есть ошибка, отправляем без форматирования
                        print(f"Ошибка форматирования: {e}")
                        await message.answer(text)

                def close_formatting_tags(text: str) -> str:
                    # Подсчёт открытых тегов
                    open_bold = text.count('*') - text.count('**')
                    open_italic = text.count('_')
                    open_code = text.count('`')

                    # Закрываем открытые теги
                    if open_bold % 2:
                        text += '*'
                    if open_italic % 2:
                        text += '_'
                    if open_code % 2:
                        text += '`'
                    return text

                await safe_send_message(response_text)
                await sent_message.delete()

                # Сохраняем состояние для следующего сообщения
                await DialogStates.waiting_for_dialog.set()
                await save_user_state(state, model_name)

            except Exception as e:
                logger.error(
                    f"Ошибка генерации контента: {type(e).__name__} - {str(e)}")
                await message.answer(
                    f"Произошла ошибка генерации контента: {str(e)}\nПожалуйста, попробуйте снова."
                )
                # Сохраняем состояние для следующего сообщения
                await DialogStates.waiting_for_dialog.set()
                await save_user_state(state, model_name)

        except Exception as e:
            logger.error(
                f"Ошибка в диалоге Gemini: {type(e).__name__} - {str(e)}\n{traceback.format_exc()}"
            )
            await message.answer(f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова.")
            await DialogStates.waiting_for_dialog.set()
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
            await DialogStates.waiting_for_g4f_dialog.set()

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
            await DialogStates.waiting_for_g4f_dialog.set()

    async def save_user_state(state: FSMContext, new_state: str):
        """
        Сохраняет текущее состояние пользователя в FSM.

        Args:
            state: FSMContext объект для работы с состоянием
            new_state: Новое состояние для сохранения
        """
        async with state.proxy() as data:
            if 'states_history' not in data:
                data['states_history'] = []
            data['states_history'].append(new_state)
            data['current_state'] = new_state

    async def get_previous_user_state(state: FSMContext) -> str | None:
        """
        Возвращает предыдущее состояние пользователя из FSM.

        Args:
            state: FSMContext объект для работы с состоянием

        Returns:
            str | None: Предыдущее состояние или None если истории нет
        """
        async with state.proxy() as data:
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

            # Сохраняем обновленную историю
            cursor.execute("""
                INSERT INTO dialog_sessions (chat_id, ai_name, messages)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, ai_name)
                DO UPDATE SET messages = %s;
            """, (
                chat_id,
                ai_name,
                json.dumps(new_messages, ensure_ascii=False),
                json.dumps(new_messages, ensure_ascii=False)
            ))
            await asyncio.to_thread(conn.commit)
            print("[LOG] Сообщение успешно сохранено в БД.")

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

    @bot.message_handler(commands=['user_states'])
    def show_user_states(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(
                message.chat.id, "🚫 У вас нет прав для использования этой команды.")
            return

        bot.send_message(
            message.chat.id, f"👥 *Состояния пользователей:*\n{user_states}", parse_mode="Markdown")

    @bot.message_handler(commands=['dialog_sessions'])
    async def show_dialog_sessions(message: types.Message):
        """Показывает историю диалогов (только для админа)."""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        cursor.execute("SELECT * FROM dialog_sessions")
        users = cursor.fetchall()

        text = "💬 *История диалогов:*\n\n"
        for chat_id, messages in users:
            text += f"🔹 `{chat_id}`:\n"
            dialog = json.loads(messages)
            for msg in dialog[-5:]:  # Показываем последние 5 сообщений
                text += f"  - *{msg['role']}*: {msg['content'][:100]}...\n"

        await message.answer(text, parse_mode=types.ParseMode.MARKDOWN_V2)

    @bot.message_handler(commands=['active_generations'])
    async def show_active_generations(message: types.Message):
        """Показывает активные генерации (только для админа)."""
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 У вас нет прав для использования этой команды.")
            return

        await message.answer(
            f"⚙️ *Активные генерации:*\n{active_generations}",
            parse_mode=types.ParseMode.MARKDOWN_V2
        )

    @bot.message_handler(func=lambda message: message.text == '⬅️ Назад')
    def back(message):
        chat_id = message.chat.id
        previous_state = get_previous_user_state(message)

        if previous_state == 'ai_selection':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_ai_selection_keyboard())
        elif previous_state == 'text_text':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_text_text_button())
        elif previous_state == 'text_image':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_text_image_button())
        elif previous_state == 'text_voice':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_text_voice_keyboard())
        elif previous_state == 'nocode':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_nocode_keyboard())
        elif previous_state == 'gemini_model_selection':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_gemini_model_keyboard())
        elif previous_state == 'g4f_model_selection':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_g4f_model_keyboard())
        elif previous_state == 'appearance':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_appearance_keyboard())
        elif previous_state == 'photo':
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_photo_keyboard())

        else:
            bot.send_message(message.chat.id, "⬅️ Назад",
                             reply_markup=get_main_keyboard())
            save_user_state(message.chat.id, 'main_menu')

    @bot.message_handler(func=lambda message: message.text == 'Видео')
    def handle_video(message):
        bot.send_message(message.chat.id, "Видео недоступно на сервере.",
                         reply_markup=get_main_keyboard())
        save_user_state(message.chat.id, 'main_menu')  # Сохраняем состояние

    @bot.message_handler(func=lambda message: message.text == 'Компьютер')
    def handle_computer(message):
        bot.send_message(message.chat.id, "Функции управления компьютером недоступны.",
                         reply_markup=get_main_keyboard())
        save_user_state(message.chat.id, 'main_menu')  # Сохраняем состояние

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

    @bot.message_handler(func=lambda message: message.text == 'Нейросети')
    async def handle_ai(message: types.Message):
        await message.answer(
            "Выберите AI:",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(func=lambda message: message.text == '🦆 Нейросети в интернете')
    async def handle_ai_web(message: types.Message):
        await message.answer(
            "Открываю",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(func=lambda message: message.text == '🤖 Выбор AI')
    async def choose_ai(message: types.Message):
        await message.answer(
            "Выберите AI:",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(lambda message: message.text in ['ChatGPT🌐', 'Gemini', 'G4F (Аналог ChatGPT)', 'Microsoft Copilot🌐', 'Github Copilot🌐'])
    async def handle_ai_choice(message: types.Message, state: FSMContext):
        if message.text == 'Gemini':
            await message.answer(
                "Вы выбрали Gemini.",
                reply_markup=get_gemini_model_keyboard()
            )
            await save_user_state(state, 'gemini_model_selection')
            await DialogStates.waiting_for_model_selection.set()

        elif message.text == 'G4F (Аналог ChatGPT)':
            await message.answer(
                "Вы выбрали G4F. Выберите модель:",
                reply_markup=get_g4f_model_keyboard()
            )
            await save_user_state(state, 'g4f_model_selection')
            await DialogStates.waiting_for_g4f_model.set()

        elif message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в главное меню.",
                reply_markup=get_main_keyboard()
            )
            await save_user_state(state, 'main_menu')

    @bot.message_handler(state=DialogStates.waiting_for_g4f_model)
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
            await DialogStates.waiting_for_g4f_dialog.set()
        else:
            await message.answer("Неверный выбор модели. Попробуйте снова.")

    @bot.callback_query_handler(lambda call: call.data.startswith("stop_"))
    async def stop_generation(call: types.CallbackQuery):
        chat_id = int(call.data.split("_")[1])
        active_generations[chat_id] = False
        await call.message.edit_text("⏹️ Генерация остановлена.")

    @dp.message_handler(state=DialogStates.waiting_for_model_selection)
    async def handle_model_selection(message: types.Message, state: FSMContext):
        model_name = None

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

        if message.text == '⬅️ Назад':
            await message.answer(
                "Возврат в меню выбора AI.",
                reply_markup=get_ai_selection_keyboard()
            )
            await save_user_state(state, 'ai_selection')
            await state.finish()
            return

        model_name = model_mapping.get(message.text)

        if not model_name:
            await message.answer("Неверный выбор модели. Попробуйте снова.")
            return

        # Сохраняем выбранную модель в состояние
        async with state.proxy() as data:
            data['model_name'] = model_name

        await message.answer(
            f"Вы выбрали: {model_name}. Начните диалог.",
            reply_markup=get_dialog_keyboard()
        )
        await save_user_state(state, 'gemini_dialog')
        await DialogStates.waiting_for_dialog.set()

    def translate_text(text, target_lang="en"):
        return GoogleTranslator(source="auto", target=target_lang).translate(text)


    @dp.message_handler(lambda message: message.text == 'Midjourney')
    async def handle_midjourney_choice(message: Message):
        await message.answer(
            "Вы выбрали Midjourney. Введите запрос для генерации изображения.",
            reply_markup=get_dialog_keyboard()
        )
        user_states[message.chat.id] = 'midjourney_dialog'

    @dp.message_handler(lambda message: user_states.get(message.chat.id) == 'midjourney_dialog')
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
            target=lambda: asyncio.run(update_loading_message(loading_message, stop_event))
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

        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=loading_message.message_id,
            text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
        )
        await bot.send_photo(message.chat.id, photo=image_data)
        
    def translate_text(text, target_lang="en"):
        return GoogleTranslator(source="auto", target=target_lang).translate(text)

    async def update_loading_message(message: Message, stop_event):
        dots = ""
        counter = 0

        while not stop_event.is_set():
            dots = "." * (counter % 4)  # Меняем количество точек от 0 до 3
            elapsed_time = counter  # Время в секундах
            new_text = f"Генерация картинки{dots}\nГенерируется лишь: {elapsed_time} сек"

            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=new_text
                )
            except Exception:
                pass  # Если сообщение уже изменено, просто пропускаем

            counter += 1
            await asyncio.sleep(1)

    @dp.message_handler(lambda message: message.text == 'Midjourney')
    async def handle_midjourney_choice(message: Message):
        await message.answer(
            "Вы выбрали Midjourney. Введите запрос для генерации изображения.",
            reply_markup=get_dialog_keyboard()
        )
        user_states[message.chat.id] = 'midjourney_dialog'

    @dp.message_handler(lambda message: user_states.get(message.chat.id) == 'midjourney_dialog')
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
            target=lambda: asyncio.run(update_loading_message(loading_message, stop_event))
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

        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=loading_message.message_id,
            text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
        )
        await bot.send_photo(message.chat.id, photo=image_data)

    @dp.message_handler(lambda message: message.text == 'Текст-Текст')
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
            parse_mode="Markdown",
            reply_markup=get_text_text_button()
        )
    async def handle_ai_category(message: types.Message, category: str, text: str, keyboard):
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        save_user_state(message.chat.id, category)

    @dp.message_handler(lambda message: message.text == 'Текст-Изображение')
    async def handle_ai_text_image(message: types.Message):
        await handle_ai_category(
            message, 'text_image',
            """🖼️ *Категория: Текст-Изображение*

            Нейросети для генерации изображений:
            - *Midjourney* – создание детализированных картинок.

            Выберите сервис:""",
            get_text_image_button()
        )

    @dp.message_handler(lambda message: message.text == 'Текст-Голос')
    async def handle_ai_text_voice(message: types.Message):
        await handle_ai_category(
            message, 'text_voice',
            """🔊 *Категория: Текст-Голос*

            Нейросети для озвучивания текста:
            - *Hailuo* – генерация естественной речи.
            - *Hugging Face Audiobook* – конвертация текста в аудиокниги.

            Выберите сервис:""",
            get_text_voice_keyboard()
        )

    @dp.message_handler(lambda message: message.text == 'NoCode')
    async def handle_ai_nocode(message: types.Message):
        await handle_ai_category(
            message, 'nocode',
            """🛠️ *Категория: NoCode*

            Платформы для разработки без кода:
            - *Glide* – создание мобильных приложений.

            Выберите платформу:""",
            get_nocode_keyboard()
        )

    @dp.message_handler(lambda message: message.text == 'Озвучка текста')
    async def handle_ai_hailuo(message: types.Message):
        chat_id = message.chat.id
        save_user_state(chat_id, 'text_voice')

        markup = types.InlineKeyboardMarkup()
        hailuo_button = types.InlineKeyboardButton(
            text="Перейти к Озвучке текста", url="https://www.hailuo.ai/audio"
        )
        markup.add(hailuo_button)

        await message.answer("Нажмите кнопку ниже, чтобы перейти к озвучке текста:", reply_markup=markup)

    @dp.message_handler(lambda message: message.text == 'Внешность')
    async def handle_ai_appearance(message: types.Message):
        await handle_ai_category(
            message, 'appearance',
            """🎭 *Категория: Внешность*

            Сервисы для изменения внешности:
            - *Tough Tongue AI* – ваш ИИ-клон для онлайн-конференций.

            Выберите сервис:""",
            get_appearance_keyboard()
        )

    @dp.message_handler(lambda message: message.text == 'Фото')
    async def handle_ai_photo(message: types.Message):
        await handle_ai_category(
            message, 'photo',
            """📸 *Категория: Фото*

            Сервисы для обработки изображений:
            - *Memenome* – создание видео с текстом для людей с СДВГ.

            Выберите сервис:""",
            get_photo_keyboard()
        )

    @dp.message_handler(commands=['gemini'])
    async def handle_gemini_command(message: types.Message):
        """Запуск Gemini по команде /gemini"""
        chat_id = message.chat.id
        await message.answer("Вы выбрали Gemini.\nВведите запрос:", reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'gemini_dialog')

    @dp.message_handler(commands=['g4f'])
    async def handle_g4f_command(message: types.Message):
        """Запуск G4F по команде /g4f"""
        chat_id = message.chat.id
        g4f_bot.set_model("gpt-4o-mini")
        await message.answer("Вы выбрали G4F. Введите ваш запрос:", reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'g4f_dialog')

    @dp.message_handler(commands=['midjourney'])
    async def handle_midjourney_command(message: types.Message):
        """Запуск Midjourney по команде /midjourney"""
        chat_id = message.chat.id
        await message.answer("Вы выбрали Midjourney. Введите запрос для генерации изображения:",
                            reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'midjourney_dialog')
