# bot_handlers.py
import html
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
import traceback
from collections import Counter

# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:XgFOPaWGkymuYpcXKkuSJwIlcPihcHKI@autorack.proxy.rlwy.net:36255/railway")
# Получаем URL базы данных из переменной окружения
DATABASE_URL = os.environ.get("DB_URL")
if not DATABASE_URL:
    print("Ошибка: Не найдена переменная окружения DB_URL.  Убедитесь, что она установлена.")
    exit()  # Или используйте другое действие для обработки этой ошибки


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
    bot.send_message(ADMIN_ID, "Бот запущен)" )
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
            # Сохраняем состояние
            save_user_state(message.chat.id, 'main_menu')
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            bot.send_message(message.chat.id, 'Произошла ошибка')

    @bot.message_handler(commands=['test'])
    def test(message):
        text = "* Это *не жирный* и не *курсив*, но **это жирный**, а *это курсив*."
        clean_text = format_telegram_text(clean_text)
        bot.send_message(message.chat.id, clean_text)
        bot.send_message(message.chat.id, clean_text, parse_mode='HTML')



    def format_telegram_text(text):
        """
        Форматирует текст для Telegram:
        1. Удаляет одиночные `*` и `` ` ``, но сохраняет `**жирный**`, `*курсив*`, `` `код` `` и ```блок кода```.
        2. Конвертирует Markdown в HTML (Telegram-совместимый).
        3. Обрабатывает кодовые блоки (```python → <pre><code>).
        4. Делает `моноширинный текст` с `<code>`, убирая из него `<b>` и `<i>`.
        5. Удаляет текст между `"""  """`.
        6. Проверяет незакрытые и неподдерживаемые теги.
        """

        # 1. Удаляем текст внутри `""" ... """`
        #text = remove_docstrings(text)

        # 2. Удаляем одиночные `*`, но не `**жирный**` и `*курсив*`
        text = re.sub(r'(?<!\*)\*(?!\*)', '', text)

        # 3. Удаляем одиночные `` ` ``, но не `` `код` `` и ```блок кода```
        #text = re.sub(r'(?<!`)\`(?!`)', '', text)

        # 4. Markdown → HTML
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)  # Жирный
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)      # Курсив
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)      # Подчеркнутый
        text = re.sub(r'~(.*?)~', r'<s>\1</s>', text)        # Зачеркнутый

        # 5. Делаем `инлайн-код` моноширинным
        text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)

        # 6. Убираем `<b>` и `<i>` внутри `<code>`
        #text = remove_formatting_inside_code(text)

        # 7. Обрабатываем блоки кода (```python → <pre><code>)
        text = re.sub(r'```(?:python)?(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)

        # 8. Проверяем незакрытые теги
        check_unmatched_tags(text)

        return text


    def remove_docstrings(text):
        """Удаляет текст между `"""  """`, включая сами кавычки."""
        return re.sub(r'""".*?"""', '', text, flags=re.DOTALL)


    def remove_formatting_inside_code(text):
        """
        Если внутри `<b>` или `<i>` есть `<code>`, удаляет `<b>` и `<i>`, оставляя только `<code>`.
        """

        # **`код`** → `<b><code>код</code></b>` → `<code>код</code>`
        text = re.sub(r'<b>\s*(<code>.*?</code>)\s*</b>', r'\1', text)  
        text = re.sub(r'<i>\s*(<code>.*?</code>)\s*</i>', r'\1', text)  

        return text


    def check_unmatched_tags(text):
        """Ищет незакрытые или неподдерживаемые HTML-теги."""
        tags = re.findall(r'</?(\w+)>', text)
        counts = Counter(tags)

        for tag in counts:
            if text.count(f"<{tag}>") != text.count(f"</{tag}>"):
                print(f"[ERROR] Незакрытый или лишний тег: <{tag}>")

        # Проверяем, есть ли неподдерживаемые теги
        supported_tags = {"b", "i", "u", "s", "a", "code", "pre", "blockquote", "tg-spoiler"}
        for tag in counts:
            if tag not in supported_tags:
                print(f"[WARNING] Неподдерживаемый тег: <{tag}>")




    def handle_dialog(message, model_name, test_query=None):
        chat_id = message.chat.id
        try:
            if message.text == '⏹️ Завершить диалог':
                bot.send_message(chat_id, "Диалог завершен.", reply_markup=get_ai_selection_keyboard())
                if (chat_id, model_name) in dialog_sessions:
                    print(f"[WARNING] Удаляю dialog_sessions[{(chat_id, model_name)}]")
                    del dialog_sessions[(chat_id, model_name)]
                if chat_id in user_states:
                    del user_states[chat_id]
                save_user_state(chat_id, 'ai_selection')
                return

            elif message.text == '⬅️ Назад':
                bot.send_message(chat_id, "Возврат в меню выбора Gemini модели.", reply_markup=get_gemini_model_keyboard())
                save_user_state(chat_id, 'gemini_model_selection')
                if (chat_id, model_name) in dialog_sessions:
                    print(f"[WARNING] Удаляю dialog_sessions[{(chat_id, model_name)}]")
                    del dialog_sessions[(chat_id, model_name)]
                return

            query = test_query if test_query else message.text
            save_dialog_message(chat_id, model_name, "user", query)

            # Кнопка "Stop"
            markup = types.InlineKeyboardMarkup()
            stop_button = types.InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{chat_id}")
            markup.add(stop_button)

            sent_message = bot.send_message(chat_id, "Генерация ответа...", reply_markup=markup)
            active_generations[chat_id] = True

            try:
                model = genai.GenerativeModel(model_name)

                # ✅ Используем правильный ключ
                messages = dialog_sessions.get((chat_id, model_name), [])
                print(f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

                response = model.generate_content(messages)
                response_text = response.text
                save_dialog_message(chat_id, model_name, "model", response_text)

                max_length = 4000
                generated_text = ""

                for i in range(0, len(response_text), max_length):
                    if not active_generations.get(chat_id, False):
                        bot.edit_message_text("⏹️ Генерация остановлена.", chat_id, sent_message.message_id)
                        return

                    chunk = response_text[i:i + max_length]
                    generated_text += chunk
                    formatted_text = format_telegram_text(generated_text)
                    print(f"[DEBUG] Отформатированный ответ: {formatted_text}")


                    try:
                        bot.edit_message_text(formatted_text, chat_id, sent_message.message_id, parse_mode='HTML', reply_markup=markup)
                        time.sleep(0.5)
                    except telebot.apihelper.ApiTelegramException as e:
                        logger.error(f"Ошибка Telegram API при отправке сообщения: {type(e).__name__} - {str(e)}\n")
                        plain_text = re.sub(r'<[^>]+>', '', formatted_text)
                        bot.send_message(chat_id, plain_text)

                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения: {type(e).__name__} - {str(e)}\n{traceback.format_exc()}")
                        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}. Попробуйте снова.")
                        break

                    bot.edit_message_reply_markup(chat_id, sent_message.message_id, reply_markup=None)
                    bot.register_next_step_handler(message, handle_dialog, model_name=model_name)

            except Exception as e:
                logger.error(f"Ошибка генерации контента: {type(e).__name__} - {str(e)}")
                bot.send_message(chat_id, f"Произошла ошибка генерации контента: {str(e)}")

        except Exception as e:
            logger.error(f"Ошибка в диалоге Gemini: {type(e).__name__} - {str(e)}\n{traceback.format_exc()}")
            bot.send_message(message.chat.id, f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте позже.")


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
        save_dialog_message(chat_id, "g4f", "user", query)

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
            save_dialog_message(chat_id, "g4f", "assistant", response)

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

        except telebot.apihelper.ApiTelegramException as e:
            error_message = f"Ошибка Telegram API при отправке сообщения: {type(e).__name__} - {str(e)}\n"
            logger.error(error_message)
            print(error_message)

            # Попробуем убрать форматирование и повторить отправку
            # Удаляем все HTML-теги
            plain_text = re.sub(r'<[^>]+>', '', formatted_chunk)

            try:
                # Отправляем без форматирования
                bot.send_message(chat_id, plain_text)
            except telebot.apihelper.ApiTelegramException as e2:
                logger.error(
                    f"Повторная ошибка при отправке без форматирования: {e2}")
                bot.send_message(
                    chat_id, "Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.")

            # Перезапускаем обработчик диалога
            bot.register_next_step_handler(message, handle_g4f_dialog)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {str(e)}. Попробуй снова)")
            bot.register_next_step_handler(message, handle_g4f_dialog)

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

    def save_dialog_message(chat_id, ai_name, role, content):
        """Сохраняет сообщение в диалог пользователя (в БД и в память)."""

        print(f"[LOG] save_dialog_message вызван с: chat_id={chat_id}, ai_name={ai_name}, role={role}, content={content}")

        # Проверяем, есть ли диалог в памяти
        if (chat_id, ai_name) not in dialog_sessions:
            print(f"[ERROR] dialog_sessions НЕ содержит ({chat_id}, {ai_name}). Создаю новый ключ.")
            dialog_sessions[(chat_id, ai_name)] = []

        #print(f"[LOG] dialog_sessions перед добавлением сообщения: {dialog_sessions}")

        # Добавляем сообщение в локальный кэш
        try:
            dialog_sessions[(chat_id, ai_name)].append({"role": role, "parts": [content]})
        except KeyError as e:
            print(f"[CRITICAL ERROR] KeyError при добавлении сообщения! {e}")
            #print(f"[DEBUG] Содержимое dialog_sessions на момент ошибки: {dialog_sessions}")
            raise  # Повторно вызываем ошибку, чтобы видеть стек вызова

        #print(f"[LOG] Обновленный dialog_sessions[{(chat_id, ai_name)}]: {dialog_sessions[(chat_id, ai_name)]}")

        # Получаем текущую историю сообщений из БД
        try:
            cursor.execute(
                "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s", 
                (chat_id, ai_name)
            )
            result = cursor.fetchone()

            #print(f"[LOG] Полученный результат из БД: {result}")

            # Загружаем данные из БД только если они есть
            old_messages = []
            if result and result[0]:
                if isinstance(result[0], list):
                    old_messages = result[0]  # Уже список, можно использовать напрямую
                elif isinstance(result[0], str):
                    try:
                        old_messages = json.loads(result[0])  # Пробуем загрузить JSON
                    except json.JSONDecodeError:
                        print("[ERROR] JSONDecodeError! Старый формат данных в БД. Используем пустой список.")
                        old_messages = []

            # Объединяем старые и новые сообщения
            new_messages = old_messages + [{"role": role, "parts": [content]}]
            #print(f"[LOG] Сформирован новый список сообщений: {new_messages}")

            # Сохраняем обновленную историю в БД
            cursor.execute("""
                INSERT INTO dialog_sessions (chat_id, ai_name, messages)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, ai_name)
                DO UPDATE SET messages = %s;
            """, (chat_id, ai_name, json.dumps(new_messages, ensure_ascii=False), json.dumps(new_messages, ensure_ascii=False)))
            conn.commit()

            print("[LOG] Сообщение успешно сохранено в БД.")

        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении в БД: {e}")
            print(traceback.format_exc())  # Выводим полный стек ошибки


    def get_dialog_history(chat_id, ai_name):
        """Получает всю историю диалога из БД."""
        cursor.execute(
            "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s", (chat_id, ai_name))
        result = cursor.fetchone()

        if result:
            # Преобразуем JSON обратно в список Python
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
    def show_dialog_sessions(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(
                message.chat.id, "🚫 У вас нет прав для использования этой команды.")
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
            bot.send_message(
                message.chat.id, "🚫 У вас нет прав для использования этой команды.")
            return

        bot.send_message(
            message.chat.id, f"⚙️ *Активные генерации:*\n{active_generations}", parse_mode="Markdown")

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

    @bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
    def stop_generation(call):
        chat_id = int(call.data.split("_")[1])
        active_generations[chat_id] = False
        bot.edit_message_text("⏹️ Генерация остановлена.",
                              chat_id, call.message.message_id)

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
        save_dialog_message(chat_id, "midjourney", "user", translated_text)

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

    def handle_ai_category(message, category, text, keyboard):
        bot.send_message(message.chat.id, text,
                         parse_mode="Markdown", reply_markup=keyboard)
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
        hailuo_button = types.InlineKeyboardButton(
            text="Перейти к Озвучке текста", url="https://www.hailuo.ai/audio")
        markup.add(hailuo_button)

        bot.send_message(
            chat_id, "Нажмите кнопку ниже, чтобы перейти к озвучке текста:", reply_markup=markup)

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

    @bot.message_handler(commands=['gemini'])
    def handle_gemini_command(message):
        """Запуск Gemini по команде /gemini"""
        chat_id = message.chat.id
        bot.send_message(chat_id, "Вы выбрали Gemini.\nВведите запрос:",
                         reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'gemini_dialog')
        bot.register_next_step_handler(
            message, handle_dialog, model_name="gemini-1.5-pro")

    @bot.message_handler(commands=['g4f'])
    def handle_g4f_command(message):
        """Запуск G4F по команде /g4f"""
        chat_id = message.chat.id
        # Устанавливаем модель перед началом работы
        g4f_bot.set_model("gpt-4o-mini")
        bot.send_message(chat_id, "Вы выбрали G4F. Введите ваш запрос:",
                         reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'g4f_dialog')
        bot.register_next_step_handler(message, handle_g4f_dialog)

    @bot.message_handler(commands=['midjourney'])
    def handle_midjourney_command(message):
        """Запуск Midjourney по команде /midjourney"""
        chat_id = message.chat.id
        bot.send_message(chat_id, "Вы выбрали Midjourney. Введите запрос для генерации изображения:",
                         reply_markup=get_dialog_keyboard())
        save_user_state(chat_id, 'midjourney_dialog')
        bot.register_next_step_handler(message, handle_midjourney)
