# bot_handlers.py
import re
import threading
import time
import requests
import telebot
from telebot import types
import logging
import webbrowser
import subprocess
import os
from z.config import ADMIN_ID, POPULAR_SITES
import google.generativeai as genai
from z.config import GEMINI_API_KEY, BOT_TOKEN
from fuzzywuzzy import process
from z.app_control import open_application, get_closest_app, open_link
from g4f.client import Client
from deep_translator import GoogleTranslator
from telebot.types import Message
from z.keyboards import *
import psycopg2
from psycopg2 import sql
import json

#DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:XgFOPaWGkymuYpcXKkuSJwIlcPihcHKI@autorack.proxy.rlwy.net:36255/railway")
DATABASE_URL = os.environ.get("DB_URL")  # Получаем URL базы данных из переменной окружения
if not DATABASE_URL:
    print("Ошибка: Не найдена переменная окружения DB_URL.  Убедитесь, что она установлена.")
    exit()  # Или используйте другое действие для обработки этой ошибки

def create_tables():

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dialog_sessions (
            chat_id BIGINT PRIMARY KEY,
            messages JSONB
        );
    """)
    print("Database table dialog_sessions created successfully")
    conn.commit()

conn = None  # Инициализируем conn вне блока try
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("Успешно подключено к базе данных!")  # Выводим сообщение об успешном подключении
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
    def start(message):
        try:
            bot.send_message(
                message.chat.id,
                f"Привет, {message.from_user.first_name}!\n\n"
                "Я бот, который предоставляет доступ к различным нейросетям и другим полезным функциям.\n\n"
                "Вот что я умею:\n"
                "- Работа с текстом (генерация, перевод, суммаризация)\n"
                "- Генерация изображений\n"
                "- Доступ к различным AI-моделям (Gemini, G4F, ChatGPT и др.)\n\n"
                "Чтобы начать, выберите пункт в меню.",
                reply_markup=get_main_keyboard()
            )
            save_user_state(message.chat.id, 'main_menu')  # Сохраняем состояние
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            bot.send_message(message.chat.id, 'Произошла ошибка')

    def save_user_state(chat_id, state):
        """Сохраняет текущее состояние пользователя."""
        if chat_id not in user_states:
            user_states[chat_id] = []
        user_states[chat_id].append(state)

    def get_previous_user_state(chat_id):
        """Возвращает предыдущее состояние пользователя."""
        if chat_id in user_states and len(user_states[chat_id]) > 1:
            user_states[chat_id].pop()  # Убираем текущее состояние
            return user_states[chat_id][-1]  # Возвращаем предыдущее
        else:
            return None  # Если нет истории, возвращаем None

    def save_dialog_message(chat_id, role, content, ai_name="Unknown AI"):
        """Сохраняет сообщение в диалог пользователя (в БД и в память)."""

        if chat_id not in dialog_sessions:
            dialog_sessions[chat_id] = {
                "ai_name": ai_name,
                "messages": []
            }
        else:
            if dialog_sessions[chat_id].get("ai_name") == "Unknown AI":
                dialog_sessions[chat_id]["ai_name"] = ai_name

        dialog_sessions[chat_id]["messages"].append({"role": role, "parts": [content]})

        # Сохраняем сообщение и в БД:
        try:
            cursor.execute("""
                INSERT INTO dialog_sessions (chat_id, messages, ai_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id)
                DO UPDATE SET messages = dialog_sessions.messages || EXCLUDED.messages, ai_name = %s;
            """, (chat_id, json.dumps([{"role": role, "parts": [content]}], ensure_ascii=False), ai_name, ai_name)) 
            conn.commit()
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")

    def get_dialog_history(chat_id):
        """Получает всю историю диалога из БД."""
        cursor.execute("SELECT messages FROM dialog_sessions WHERE chat_id = %s", (chat_id,))
        result = cursor.fetchone()

        if result:
            return json.loads(result[0])  # Преобразуем JSON обратно в список Python
        return []


    @bot.message_handler(commands=['user_states'])
    def show_user_states(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "🚫 У вас нет прав для использования этой команды.")
            return

        bot.send_message(message.chat.id, f"👥 *Состояния пользователей:*\n{user_states}", parse_mode="Markdown")

    @bot.message_handler(commands=['dialog_sessions'])
    def show_dialog_sessions(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "🚫 У вас нет прав для использования этой команды.")
            return

        cursor.execute("SELECT * FROM dialog_sessions")
        users = cursor.fetchall()

        text = "💬 *История диалогов:*\n\n"
        for chat_id, messages in users:
            text += f"🔹 `{chat_id}`:\n"
            dialog = json.loads(messages)
            for msg in dialog[-5:]:  # Показываем последние 5 сообщений
                text += f"  - *{msg['role']}*: {msg['content'][:100]}...\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['active_generations'])
    def show_active_generations(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "🚫 У вас нет прав для использования этой команды.")
            return

        bot.send_message(message.chat.id, f"⚙️ *Активные генерации:*\n{active_generations}", parse_mode="Markdown")

    @bot.message_handler(func=lambda message: message.text == '⬅️ Назад')
    def back(message):
        chat_id = message.chat.id
        previous_state = get_previous_user_state(chat_id)

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
            save_user_state(chat_id, 'main_menu')

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

    def format_telegram_text(text):
        """Форматирует текст в Telegram HTML-разметку.  Удаляет незакрытые теги."""

        # Жирный **текст**
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)

        # Курсив *текст*
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text, flags=re.DOTALL)

        # Подчёркнутый __текст__
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text, flags=re.DOTALL)

        # Зачёркнутый ~~текст~~
        text = re.sub(r'~(.*?)~', r'<s>\1</s>', text, flags=re.DOTALL)

        # Цитаты > текст (каждую строку)
        text = re.sub(r'^> (.*?)$', r'<blockquote>\1</blockquote>',
                    text, flags=re.MULTILINE)

        # Моноширинный `код`
        text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)

        # Моноширинный `текст`
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text, flags=re.DOTALL)

        # Спойлер ||текст||
        text = re.sub(r'\|\|(.*?)\|\|',
                    r'<tg-spoiler>\1</tg-spoiler>', text, flags=re.DOTALL)

        return text

    class ChatBotG4F:
        def __init__(self):
            self.client = Client()
            self.messages = []

        def set_model(self, model_name):
            """Устанавливает модель для G4F"""
            self.model_name = model_name

        def ask(self, user_input):
            """Отправляет запрос в G4F и получает ответ"""
            self.messages.append({"role": "user", "content": user_input})

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.messages,
                )
                reply = response.choices[0].message.content
                self.messages.append({"role": "assistant", "content": reply})
                return reply
            except Exception as err:
                print(f"Ошибка при запросе к {self.model_name}: {err}")
                return "Не удалось получить ответ."

    # Создаем экземпляр бота для G4F
    g4f_bot = ChatBotG4F()

    @bot.message_handler(func=lambda message: message.text == 'Нейросети')
    def handle_ai(message):
        bot.send_message(message.chat.id, "Выберите AI:",
                         reply_markup=get_ai_selection_keyboard())
        save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(func=lambda message: message.text == '🦆 Нейросети в интернете')
    def handle_ai(message):
        bot.send_message(message.chat.id, "Открываю",
                         reply_markup=get_ai_selection_keyboard())
        save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(func=lambda message: message.text == '🤖 Выбор AI')
    def choose_ai(message):
        bot.send_message(message.chat.id, "Выберите AI:",
                         reply_markup=get_ai_selection_keyboard())
        save_user_state(message.chat.id, 'ai_selection')

    @bot.message_handler(func=lambda message: message.text in ['ChatGPT🌐', 'Gemini', 'G4F (Аналог ChatGPT)', 'Microsoft Copilot🌐', 'Github Copilot🌐'])
    def handle_ai_choice(message):
        if message.text == 'Gemini':
            bot.send_message(message.chat.id, "Вы выбрали Gemini.",
                             reply_markup=get_gemini_model_keyboard())
            save_user_state(message.chat.id, 'gemini_model_selection')
            bot.register_next_step_handler(message, handle_model_selection)
        elif message.text == 'G4F (Аналог ChatGPT)':
            bot.send_message(message.chat.id, "Вы выбрали G4F. Выберите модель:",
                             reply_markup=get_g4f_model_keyboard())
            save_user_state(message.chat.id, 'g4f_model_selection')
            bot.register_next_step_handler(message, handle_g4f_model_selection)
        elif message.text == '⬅️ Назад':
            bot.send_message(
                message.chat.id, "Возврат в главное меню.", reply_markup=get_main_keyboard())
            save_user_state(message.chat.id, 'main_menu')

    def handle_g4f_model_selection(message):
        if message.text == '⬅️ Назад':
            choose_ai(message)
            return

        model_mapping = {
            'GPT 4o mini': 'gpt-4o-mini',
        }

        model_name = model_mapping.get(message.text)

        if model_name:
            g4f_bot.set_model(model_name)
            bot.send_message(message.chat.id, f"Вы выбрали {model_name}. Введите ваш запрос:",
                             reply_markup=get_dialog_keyboard())
            save_user_state(message.chat.id, 'g4f_dialog')
            bot.register_next_step_handler(message, handle_g4f_dialog)
        else:
            bot.send_message(
                message.chat.id, "Неверный выбор модели. Попробуйте снова.")
            bot.register_next_step_handler(message, handle_g4f_model_selection)

    @bot.message_handler(func=lambda message: message.text == '📂 Открыть папку')
    def open_folder(message):
        action = message.text
        if action == '📂 Открыть папку':
            # УДАЛЕНО: "Введите путь к папке."
            bot.send_message(message.chat.id, "Функция недоступна на сервере.")
            save_user_state(message.chat.id, 'main_menu')  # Сохраняем состояние
            # УДАЛЕНО: bot.register_next_step_handler(message, handle_open_folder)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
    def stop_generation(call):
        chat_id = int(call.data.split("_")[1])
        active_generations[chat_id] = False
        bot.edit_message_text("⏹️ Генерация остановлена.",
                              chat_id, call.message.message_id)

    def handle_g4f_dialog(message):
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            bot.send_message(chat_id, "Диалог завершен.",
                             reply_markup=get_main_keyboard())
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            if chat_id in user_states:
                del user_states[chat_id]
            save_user_state(chat_id, 'main_menu')
            return

        elif message.text == '⬅️ Назад':
            bot.send_message(chat_id, "Возврат в меню выбора G4F модели.",
                             reply_markup=get_g4f_model_keyboard())
            save_user_state(chat_id, 'g4f_model_selection')
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            return

        query = message.text
        save_dialog_message(chat_id, "user", query, 'g4f')

        if chat_id not in g4f_dialog_sessions:
            g4f_dialog_sessions[chat_id] = []

        g4f_dialog_sessions[chat_id].append({"role": "user", "content": query})

        # Отправляем пустое сообщение с кнопкой "Stop"
        markup = types.InlineKeyboardMarkup()
        stop_button = types.InlineKeyboardButton(
            "⏹️ Stop", callback_data=f"stop_{chat_id}")
        markup.add(stop_button)

        sent_message = bot.send_message(
            chat_id, "Генерация ответа...", reply_markup=markup)

        active_generations[chat_id] = True  # Помечаем генерацию активной

        try:
            response = g4f_bot.ask(query)
            save_dialog_message(chat_id, "assistant", response, 'g4f')

            # Постепенная отправка текста
            response_text = response
            max_length = 4000  # Telegram ограничение
            generated_text = ""

            for i in range(0, len(response_text), max_length):
                # Если нажали "Stop"
                if not active_generations.get(chat_id, False):
                    bot.edit_message_text(
                        "⏹️ Генерация остановлена.", chat_id, sent_message.message_id)
                    return

                chunk = response_text[i:i + max_length]
                generated_text += chunk
                formatted_chunk = format_telegram_text(generated_text)

                # Редактируем предыдущее сообщение
                bot.edit_message_text(
                    formatted_chunk, chat_id, sent_message.message_id, parse_mode='HTML', reply_markup=markup)
                # Даем время для редактирования, чтобы избежать флуда
                time.sleep(0.5)

            # Добавляем ответ в историю
            g4f_dialog_sessions[chat_id].append(
                {"role": "assistant", "content": response_text})

            # Убираем кнопку Stop после завершения
            bot.edit_message_reply_markup(
                chat_id, sent_message.message_id, reply_markup=None)

            bot.register_next_step_handler(message, handle_g4f_dialog)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {str(e)}")

    def handle_model_selection(message):
        if message.text == 'Gemini 2.0 Experimental':
            model_name = 'gemini-2.0-flash-exp'
        elif message.text == 'Gemini 1.5 Pro':
            model_name = 'gemini-1.5-pro'
        elif message.text == 'Gemini 1.5 Flash':
            model_name = 'gemini-1.5-flash'
        elif message.text == 'Gemini 2.0 Pro Experimental 02-05':
            model_name = 'gemini-2.0-pro-exp-02-05'
        elif message.text == 'Gemini 2.0 Flash Thinking Experimental 01-21':
            model_name = 'gemini-2.0-flash-thinking-exp-01-21'
        elif message.text == 'Gemini 2.0 Flash-Lite Preview 02-05':
            model_name = 'gemini-2.0-flash-lite-preview-02-05'
        elif message.text == 'Gemini 2.0 Flash':
            model_name = 'gemini-2.0-flash'
        elif message.text == '⬅️ Назад':
            bot.send_message(
                message.chat.id, "Возврат в меню выбора AI.", reply_markup=get_ai_selection_keyboard())
            save_user_state(message.chat.id, 'ai_selection')
            return
        else:
            bot.send_message(
                message.chat.id, "Неверный выбор модели. Попробуйте снова.")
            return
        message.model_name = model_name
        bot.send_message(
            message.chat.id,
            f"Вы выбрали: {model_name}. Начните диалог.",
            reply_markup=get_dialog_keyboard()
        )
        save_user_state(message.chat.id, 'gemini_dialog')
        bot.register_next_step_handler(
            message, handle_dialog, model_name=model_name)


    def handle_dialog(message, model_name, test_query=None):
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            bot.send_message(chat_id, "Диалог завершен.",
                             reply_markup=get_ai_selection_keyboard())
            if chat_id in dialog_sessions:
                del dialog_sessions[chat_id]
            if chat_id in user_states:
                del user_states[chat_id]
            save_user_state(chat_id, 'ai_selection')
            return

        elif message.text == '⬅️ Назад':
            bot.send_message(chat_id, "Возврат в меню выбора Gemini модели.",
                             reply_markup=get_gemini_model_keyboard())
            save_user_state(chat_id, 'gemini_model_selection')
            if chat_id in dialog_sessions:
                del dialog_sessions[chat_id]
            return

        query = test_query if test_query else message.text
        save_dialog_message(chat_id, "user", query, 'gemini')

        # Кнопка "Stop"
        markup = types.InlineKeyboardMarkup()
        stop_button = types.InlineKeyboardButton(
            "⏹️ Stop", callback_data=f"stop_{chat_id}")
        markup.add(stop_button)

        sent_message = bot.send_message(
            chat_id, "Генерация ответа...", reply_markup=markup)
        active_generations[chat_id] = True

        try:
            model = genai.GenerativeModel(model_name)
            messages = []
            for item in dialog_sessions[chat_id]:
                messages.append(item)
            response = model.generate_content(messages)

            response_text = response.text
            save_dialog_message(chat_id, "assistant", response_text, 'gemini')

            max_length = 4000
            generated_text = ""

            for i in range(0, len(response_text), max_length):
                # Проверяем, остановлена ли генерация
                if not active_generations.get(chat_id, False):
                    bot.edit_message_text(
                        "⏹️ Генерация остановлена.", chat_id, sent_message.message_id)
                    return

                chunk = response_text[i:i + max_length]
                generated_text += chunk
                formatted_text = format_telegram_text(generated_text)

                bot.edit_message_text(
                    formatted_text, chat_id, sent_message.message_id, parse_mode='HTML', reply_markup=markup)
                time.sleep(0.5)
            bot.edit_message_reply_markup(
                chat_id, sent_message.message_id, reply_markup=None)

            bot.register_next_step_handler(
                message, handle_dialog, model_name=model_name)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {str(e)}")


    def translate_text(text, target_lang="en"):
        return GoogleTranslator(source="auto", target=target_lang).translate(text)

    @bot.message_handler(func=lambda message: message.text == 'Midjourney')
    def handle_midjourney_choice(message):
        bot.send_message(
            message.chat.id, "Вы выбрали Midjourney. Введите запрос для генерации изображения.", reply_markup=get_dialog_keyboard()
        )
        save_user_state(message.chat.id, 'midjourney_dialog')
        bot.register_next_step_handler(message, handle_midjourney)

    def handle_midjourney(message: Message):
        chat_id = message.chat.id
        if message.text == '⬅️ Назад' or message.text == '⏹️ Завершить диалог':
            bot.send_message(message.chat.id, "Возврат в меню нейросетей.",
                             reply_markup=get_ai_selection_keyboard())
            if chat_id in user_states:
                del user_states[chat_id]
            save_user_state(chat_id, 'ai_selection')

            return
        translated_text = translate_text(message.text)
        save_dialog_message(chat_id, "user", message.text, 'midjourney')


        # Отправляем сообщение с анимацией загрузки
        loading_message = bot.send_message(
            message.chat.id, "Генерация картинки."
        )

        # Запускаем поток для обновления анимации
        stop_event = threading.Event()
        loading_thread = threading.Thread(
            target=update_loading_message, args=(bot, loading_message, stop_event))
        loading_thread.start()

        start_time = time.time()  # Засекаем время начала генерации

        # 🖼️ Запрос к API для генерации картинки
        client = Client()
        response = client.images.generate(
            model="flux",
            prompt=translated_text,
            response_format="url"
        )

        image_url = response.data[0].url
        image_data = requests.get(image_url).content

        stop_event.set()  # Останавливаем анимацию
        loading_thread.join()  # Ждём завершения потока

        # 🕒 Подсчёт времени генерации
        elapsed_time = round(time.time() - start_time, 2)

        # Отправляем картинку вместо загрузочного сообщения
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=loading_message.message_id,
            text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
        )
        bot.send_photo(message.chat.id, photo=image_data)
        bot.register_next_step_handler(
            message, handle_midjourney)  # Рекурсивный вызов

    def update_loading_message(bot, message, stop_event):
        dots = ""
        counter = 0

        while not stop_event.is_set():
            dots = "." * (counter % 4)  # Меняем количество точек от 0 до 3
            elapsed_time = counter  # Время в секундах
            new_text = f"Генерация картинки{
                dots}\nГенерируется лишь: {elapsed_time} сек"

            try:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=new_text
                )
            except Exception:
                pass  # Если сообщение уже изменено, просто пропускаем

            counter += 1
            time.sleep(1)

    def handle_open_folder(message):
        folder_path = message.text
        # УДАЛЕНО: if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # УДАЛЕНО:   os.startfile(folder_path)
        # УДАЛЕНО:   bot.send_message(message.chat.id, f"Папка открыта: {folder_path}")
        # УДАЛЕНО:else:
        # УДАЛЕНО:    bot.send_message(
        # УДАЛЕНО:        message.chat.id, "Папка не найдена. Пожалуйста, проверьте путь.")
        bot.send_message(message.chat.id, "Выберите следующее действие",
                         reply_markup=get_gemini_model_keyboard())
        save_user_state(message.chat.id, 'gemini_model_selection')

    @bot.message_handler(func=lambda message: message.text == '🌐 Открыть сайт')
    def open_site_handler(message):
        bot.send_message(
            message.chat.id, 'Введите название сайта или приложения.')
        bot.register_next_step_handler(message, handle_site_or_app_input)

    def handle_site_or_app_input(message):
        query = message.text.strip().lower()
        if not query:
            bot.send_message(
                message.chat.id, "Вы не ввели название сайта или приложения.")
            return
        try:
            closest_site = get_closest_site(query)
            closest_app = get_closest_app(query)
            # Проверка на youtube (регистронезависимо)
            if "youtube" in query or "ютуб" in query:
                task_name = "RunAppAsAdmin"  # Имя задачи в Планировщике задач
                if open_link(query, task_name=task_name):
                    bot.send_message(message.chat.id, f"Открываю {query}...")
                    return
            if closest_app:
                if open_application(query):
                    bot.send_message(message.chat.id, "Открываю приложение...")
                else:
                    bot.send_message(
                        message.chat.id, f'Не удалось открыть приложение "{query}".')
            elif closest_site:
                open_webpage(closest_site, message.chat.id)
            else:
                bot.send_message(
                    message.chat.id, f'Не нашёл сайт "{query}" в списке популярных. Ищу в Яндексе.')
                search_url = f"https://yandex.ru/search/?text={query}"
                open_webpage(search_url, message.chat.id)
        except Exception as e:
            logger.error(f"Error while handling message: {e}")
            bot.send_message(message.chat.id, 'Произошла ошибка')

    def open_webpage(url, chat_id):
        try:
            webbrowser.open(url)
            bot.send_message(chat_id, f"Открываю: {url}")
        except Exception as e:
            logger.error(f"Failed to open URL: {url}. Error: {e}")
            bot.send_message(
                chat_id, f"Не удалось открыть URL: {url}. Произошла ошибка.")

    def get_closest_site(query):
        closest_match, score = process.extractOne(query, POPULAR_SITES.keys())
        if score > 70:
            return POPULAR_SITES[closest_match]
        return None



    def handle_ai_category(message, category, text, keyboard):
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)
        save_user_state(message.chat.id, category)

    @bot.message_handler(func=lambda message: message.text == 'Текст-Текст')
    def handle_ai_text_text(message):
        handle_ai_category(
            message, 'text_text',
            """📄 *Категория: Текст-Текст*

            Нейросети для работы с текстом:
            - *ChatGPT* – генерация и анализ текста.
            - *Gemini* – текстовая обработка от Google.
            - *G4F* – бесплатная альтернатива ChatGPT.
            - *Microsoft Copilot* – помощник для программистов.
            - *Github Copilot* – помощник для программистов.

            Выберите модель:""",
            get_text_text_button()
        )

    @bot.message_handler(func=lambda message: message.text == 'Текст-Изображение')
    def handle_ai_text_image(message):
        handle_ai_category(
            message, 'text_image',
            """🖼️ *Категория: Текст-Изображение*

            Нейросети для генерации изображений:
            - *Midjourney* – создание детализированных картинок.


            Выберите сервис:""",
            get_text_image_button()
        )

    @bot.message_handler(func=lambda message: message.text == 'Текст-Голос')
    def handle_ai_text_voice(message):
        handle_ai_category(
            message, 'text_voice', 
            """🔊 *Категория: Текст-Голос*

            Нейросети для озвучивания текста:
            - *Hailuo* – генерация естественной речи.
            - *Hugging Face Audiobook* – конвертация текста в аудиокниги.

            Выберите сервис:""", 
            get_text_voice_keyboard()
        )

    @bot.message_handler(func=lambda message: message.text == 'NoCode')
    def handle_ai_nocode(message):
        handle_ai_category(
            message, 'nocode', 
            """🛠️ *Категория: NoCode*

            Платформы для разработки без кода:
            - *Glide* – создание мобильных приложений.

            Выберите платформу:""", 
            get_nocode_keyboard()
        )

    @bot.message_handler(func=lambda message: message.text == 'Озвучка текста')
    def handle_ai_hailuo(message):
        chat_id = message.chat.id
        save_user_state(chat_id, 'text_voice')  

        markup = types.InlineKeyboardMarkup()
        hailuo_button = types.InlineKeyboardButton(text="Перейти к Озвучке текста", url="https://www.hailuo.ai/audio")
        markup.add(hailuo_button)

        bot.send_message(chat_id, "Нажмите кнопку ниже, чтобы перейти к озвучке текста:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == 'Внешность')
    def handle_ai_appearance(message):
        handle_ai_category(
            message, 'appearance', 
            """🎭 *Категория: Внешность*

            Сервисы для изменения внешности:
            - *Tough Tongue AI* – ваш ИИ-клон для онлайн-конференций.

            Выберите сервис:""", 
            get_appearance_keyboard()
        )

    @bot.message_handler(func=lambda message: message.text == 'Фото')
    def handle_ai_photo(message):
        handle_ai_category(
            message, 'photo', 
            """📸 *Категория: Фото*

            Сервисы для обработки изображений:
            - *Memenome* – создание видео с текстом для людей с СДВГ.

            Выберите сервис:""", 
            get_photo_keyboard()
        )
