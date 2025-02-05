# bot_handlers.py
import re
import time
import telebot
from telebot import types
import logging
import webbrowser
import subprocess
import pyautogui
import os
import pygetwindow as gw
from config import POPULAR_SITES
import google.generativeai as genai
from config import GEMINI_API_KEY, BOT_TOKEN
from fuzzywuzzy import process
from keyboards import get_gemini_model_keyboard, get_gemini_model_keyboard, get_main_keyboard, get_video_keyboard, get_computer_keyboard, get_mouse_keyboard, get_volume_keyboard, get_dialog_keyboard
from keyboards import get_ai_selection_keyboard, get_g4f_model_keyboard
from audio_control import is_muted, mute_volume, unmute_volume, increase_volume, decrease_volume
from app_control import open_application, get_closest_app, open_link
from g4f.client import Client

last_keyboard_message_id = None

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
dialog_sessions = {}  # Словарь для хранения истории диалогов
g4f_dialog_sessions = {}

bot = telebot.TeleBot(BOT_TOKEN)


def setup_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start(message):
        try:
            bot.send_message(
                message.chat.id, f'Привет, {message.from_user.first_name}', reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            bot.send_message(message.chat.id, 'Произошла ошибка')

    @bot.message_handler(func=lambda message: message.text == '⬅️ Назад')
    def back(message):
        global window_menu_active
        window_menu_active = False  # сбрасываем флаг при возврате
        bot.send_message(message.chat.id, "⬅️ Назад",
                         reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda message: message.text == 'Видео')
    def handle_video(message):
        bot.send_message(message.chat.id, "Управление видео",
                         reply_markup=get_video_keyboard())

    @bot.message_handler(func=lambda message: message.text == 'Компьютер')
    def handle_computer(message):
        bot.send_message(message.chat.id, "Управление компьютером",
                         reply_markup=get_computer_keyboard())

    def format_bold_text(text):
        """Форматирует текст, заменяя **текст** на жирный."""
        def replace_bold(match):
            return f'<b>{match.group(1)}</b>'

        formatted_text = re.sub(
            r'\*\*(.*?)\*\*', replace_bold, text, flags=re.DOTALL)
        return formatted_text

    # --- Класс ChatBotG4F ---

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

    # --- Функции форматирования ---
    def format_bold_text(text):
        """Форматирует текст, заменяя **текст** на жирный."""
        def replace_bold(match):
            return f'<b>{match.group(1)}</b>'

        formatted_text = re.sub(
            r'\*\*(.*?)\*\*', replace_bold, text, flags=re.DOTALL)
        return formatted_text

    @bot.message_handler(func=lambda message: message.text == 'Нейросети')
    def handle_ai(message):
        bot.send_message(message.chat.id, "Выберите AI:",
                         reply_markup=get_ai_selection_keyboard())

    @bot.message_handler(func=lambda message: message.text == '🤖 Выбор AI')
    def choose_ai(message):
        bot.send_message(message.chat.id, "Выберите AI:",
                         reply_markup=get_ai_selection_keyboard())

    @bot.message_handler(func=lambda message: message.text in ['ChatGPT', 'Gemini', 'G4F (Аналог ChatGPT)'])
    def handle_ai_choice(message):
        if message.text == 'Gemini':
            bot.send_message(message.chat.id, "Вы выбрали Gemini.",
                             reply_markup=get_gemini_model_keyboard())
            bot.register_next_step_handler(message, handle_model_selection)
        elif message.text == 'G4F (Аналог ChatGPT)':
            bot.send_message(message.chat.id, "Вы выбрали G4F. Выберите модель:",
                             reply_markup=get_g4f_model_keyboard())
            bot.register_next_step_handler(message, handle_g4f_model_selection)
        elif message.text == 'ChatGPT':
            bot.send_message(
                message.chat.id, "Функционал ChatGPT пока не реализован.")  # TODO
        elif message.text == '⬅️ Назад':
            bot.send_message(
                message.chat.id, "Возврат в главное меню.", reply_markup=get_main_keyboard())

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
            bot.register_next_step_handler(message, handle_g4f_dialog)
        else:
            bot.send_message(
                message.chat.id, "Неверный выбор модели. Попробуйте снова.")
            bot.register_next_step_handler(message, handle_g4f_model_selection)

    def handle_g4f_query(message):
        try:
            response = g4f_bot.ask(message.text)
            formatted_response = format_bold_text(response)
            bot.send_message(
                message.chat.id, formatted_response, parse_mode='HTML')
            bot.register_next_step_handler(message, handle_g4f_query)
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {str(e)}")

    @bot.message_handler(func=lambda message: message.text == '📂 Открыть папку')
    def open_folder(message):
        action = message.text
        if action == '📂 Открыть папку':
            bot.send_message(message.chat.id, "Введите путь к папке.")
            bot.register_next_step_handler(message, handle_open_folder)

    def handle_g4f_dialog(message):
        chat_id = message.chat.id

        if message.text == '⏹️ Завершить диалог':
            bot.send_message(chat_id, "Диалог завершен.",
                             reply_markup=get_g4f_model_keyboard())
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            return

        elif message.text == '⬅️ Назад':
            bot.send_message(chat_id, "Возврат в главное меню.",
                             reply_markup=get_ai_selection_keyboard())
            if chat_id in g4f_dialog_sessions:
                del g4f_dialog_sessions[chat_id]
            return

        else:
            query = message.text

            if chat_id not in g4f_dialog_sessions:
                g4f_dialog_sessions[chat_id] = []

            g4f_dialog_sessions[chat_id].append(
                {"role": "user", "content": query})

            try:
                response = g4f_bot.ask(query)

                formatted_response = format_bold_text(response)
                bot.send_message(chat_id, formatted_response,
                                 parse_mode='HTML')

                g4f_dialog_sessions[chat_id].append(
                    {"role": "assistant", "content": response})

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
                message.chat.id, "Возврат в главное меню.", reply_markup=get_gemini_model_keyboard())
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
        bot.register_next_step_handler(
            message, handle_dialog, model_name=model_name)

    def handle_dialog(message, model_name):  # Обработчик диалога
        chat_id = message.chat.id
        if message.text == '⏹️ Завершить диалог':
            bot.send_message(
                chat_id, "Диалог завершен.", reply_markup=get_gemini_model_keyboard()
            )
            if chat_id in dialog_sessions:
                del dialog_sessions[chat_id]
            return
        elif message.text == '⬅️ Назад':
            bot.send_message(
                chat_id, "Возврат в главное меню.", reply_markup=get_gemini_model_keyboard()
            )
            if chat_id in dialog_sessions:
                del dialog_sessions[chat_id]
            return
        else:
            query = message.text

            if chat_id not in dialog_sessions:
                dialog_sessions[chat_id] = []

            dialog_sessions[chat_id].append({"role": "user", "parts": [query]})

        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(dialog_sessions[chat_id])

            # Разделение ответа на части и отправка
            response_text = response.text
            max_length = 4000  # Максимальная длина сообщения Telegram
            for i in range(0, len(response_text), max_length):
                chunk = response_text[i:i + max_length]
                formatted_chunk = format_bold_text(chunk)
                bot.send_message(chat_id, formatted_chunk, parse_mode='HTML')
                time.sleep(0.3)  # Небольшая задержка для избежания флуда

            dialog_sessions[chat_id].append(
                {"role": "model", "parts": [response_text]})  # Сохраняем полный ответ

            bot.register_next_step_handler(
                message, handle_dialog, model_name=model_name)

        except Exception as e:
            logger.error(f"Ошибка при вызове API Gemini: {e}")
            bot.send_message(
                chat_id,
                f"Ошибка при выполнении запроса: {str(e)}"
            )
            return
        
    def handle_open_folder(message):
        folder_path = message.text
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            os.startfile(folder_path)
            bot.send_message(message.chat.id, f"Папка открыта: {folder_path}")
        else:
            bot.send_message(
                message.chat.id, "Папка не найдена. Пожалуйста, проверьте путь.")
        bot.send_message(message.chat.id, "Выберите следующее действие",
                         reply_markup=get_gemini_model_keyboard())

    @bot.message_handler(func=lambda message: message.text in ['⏯️ Пауза / ⏸️ Воспроизведение', '▶️ Перемотать вперед', '◀️ Перемотать назад'])
    def handle_video_controls(message):
        action = message.text
        if action == '⏯️ Пауза / ⏸️ Воспроизведение':
            pyautogui.press('space')
        elif action == '▶️ Перемотать вперед':
            pyautogui.press('right')
        elif action == '◀️ Перемотать назад':
            pyautogui.press('left')

    @bot.message_handler(func=lambda message: message.text == '🖱️ Мышь')
    def mouse(message):
        bot.send_message(message.chat.id, "Управление мышью",
                         reply_markup=get_mouse_keyboard())

    @bot.message_handler(func=lambda message: message.text in ['Лево', 'Право'])
    def handle_mouse(message):
        if message.text == 'Лево':
            pyautogui.click(button='left')
        elif message.text == 'Право':
            pyautogui.click(button='right')

    @bot.message_handler(func=lambda message: message.text == '🔊 Громкость')
    def volume(message):
        global last_keyboard_message_id
        try:
            # Отправляем сообщение с клавиатурой и сохраняем его message_id
            sent_message = bot.send_message(
                chat_id=message.chat.id,
                text="Управление громкостью",
                reply_markup=get_volume_keyboard(is_muted())
            )
            last_keyboard_message_id = sent_message.message_id
        except Exception as e:
            logger.error(f"Ошибка при отправке клавиатуры: {e}")

    def update_volume_keyboard(message):
        try:
            bot.send_message(
                chat_id=message.chat.id,
                text="Управление громкостью",
                reply_markup=get_volume_keyboard(is_muted())
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении клавиатуры: {e}")

    @bot.message_handler(func=lambda message: message.text in ['🔇 Выключить звук', '🔊 Включить звук', '🔊 Повысить громкость', '🔉 Понизить громкость'])
    def handle_volume_controls(message):
        action = message.text
        if action == '🔇 Выключить звук':
            mute_volume()
            response = "Звук выключен."
            update_volume_keyboard(message)

        elif action == '🔊 Включить звук':
            unmute_volume()
            response = "Звук включен."
            update_volume_keyboard(message)

        elif action == '🔊 Повысить громкость':
            current_volume_percent = increase_volume()
            response = f'Громкость повышена. Текущая громкость: {
                current_volume_percent}%'
        elif action == '🔉 Понизить громкость':
            current_volume_percent = decrease_volume()
            response = f'Громкость понижена. Текущая громкость: {
                current_volume_percent}%'
        bot.send_message(message.chat.id, response)

    @bot.message_handler(func=lambda message: message.text == '📺 На весь экран')
    def fullscreen(message):
        bot.send_message(
            message.chat.id, 'Открываю текущее приложение на весь экран.')
        active_window = gw.getActiveWindow()
        if active_window:
            active_window.maximize()
        else:
            print("Нет активного окна")

    @bot.message_handler(func=lambda message: message.text == '❌ Выключить компьютер')
    def shutdown(message):
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(text='Да'),
                   types.KeyboardButton(text='Нет'))
        bot.send_message(
            message.chat.id, 'Вы хотите выключить компьютер?', reply_markup=markup)
        bot.register_next_step_handler(
            message, lambda msg: handle_shutdown_restart_choice(msg, 'выключение'))

    @bot.message_handler(func=lambda message: message.text == '🔄 Перезагрузить компьютер')
    def restart(message):
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(text='Да'),
                   types.KeyboardButton(text='Нет'))
        bot.send_message(
            message.chat.id, 'Вы хотите перезагрузить компьютер?', reply_markup=markup)
        bot.register_next_step_handler(
            message, lambda msg: handle_shutdown_restart_choice(msg, 'перезагрузка'))

    def handle_shutdown_restart_choice(message, action):
        try:
            if message.text == 'Да':
                bot.send_message(
                    message.chat.id, f'{action.capitalize()} компьютера...')
                if action == 'выключение':
                    subprocess.run(["shutdown", "/s", "/t", "5"], check=True)
                elif action == 'перезагрузка':
                    subprocess.run(["shutdown", "/r", "/t", "5"], check=True)
            elif message.text == 'Нет':
                bot.send_message(
                    message.chat.id, f'Отмена {action} компьютера.')
            else:
                bot.send_message(
                    message.chat.id, 'Пожалуйста, выберите "Да" или "Нет".')
        except subprocess.CalledProcessError as e:
            logger.error(f"Error in {action} command: {e}")
            bot.send_message(
                message.chat.id, f'Ошибка при {action} компьютера')
        except Exception as e:
            logger.error(f"Error in {action} command: {e}")
            bot.send_message(message.chat.id, 'Произошла ошибка')
        finally:
            bot.send_message(
                message.chat.id, 'Вернулся к основному меню', reply_markup=get_main_keyboard())

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
