# bot_handlers.py

import telebot
from telebot import types
import logging
import webbrowser
import subprocess
import pyautogui
import os
import requests
import pygetwindow as gw
from config import POPULAR_SITES, TRANSLATIONS
from pywinauto import Application, findwindows
from openai import OpenAI
import google.generativeai as genai
from config import GEMINI_API_KEY
from fuzzywuzzy import process
from keyboards import get_deepseek_keyboard, get_main_keyboard, get_video_keyboard, get_computer_keyboard, get_mouse_keyboard, get_volume_keyboard
from audio_control import is_muted, mute_volume, unmute_volume, increase_volume, decrease_volume
from app_control import open_application, get_closest_app, open_link
from config import DEEPSEEK_API_KEY, DEEPSEEK_SEARCH_URL, DEEPSEEK_INTERNET_SEARCH_URL
# Глобальная переменная для хранения message_id последнего сообщения с клавиатурой
last_keyboard_message_id = None

logger = logging.getLogger(__name__)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

genai.configure(api_key=GEMINI_API_KEY)

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
        bot.send_message(message.chat.id, "⬅️ Назад",
                         reply_markup=get_main_keyboard())
        bot.delete_message(message.chat.id, message.message_id)

    @bot.message_handler(func=lambda message: message.text == 'Видео')
    def handle_video(message):
        bot.send_message(message.chat.id, "Управление видео",
                         reply_markup=get_video_keyboard())

    @bot.message_handler(func=lambda message: message.text == 'Компьютер')
    def handle_computer(message):
        bot.send_message(message.chat.id, "Управление компьютером",
                         reply_markup=get_computer_keyboard())

    @bot.message_handler(func=lambda message: message.text == 'DeepSeek')
    def handle_deepseek(message):
        bot.send_message(message.chat.id, "DeepSeek",
                         reply_markup=get_deepseek_keyboard())

    @bot.message_handler(func=lambda message: message.text in ['🔍 Поиск', '🔍 Поиск в интернете', '📂 Открыть папку', '⬅️ Назад'])
    def handle_deepseek_controls(message):
        action = message.text
        if action == '🔍 Поиск':
            bot.send_message(message.chat.id, "Введите запрос для поиска.")
            bot.register_next_step_handler(message, handle_search_query)
        elif action == '🔍 Поиск в интернете':
            bot.send_message(
                message.chat.id, "Введите запрос для поиска в интернете.")
            bot.register_next_step_handler(
                message, handle_internet_search_query)
        elif action == '📂 Открыть папку':
            bot.send_message(message.chat.id, "Введите путь к папке.")
            bot.register_next_step_handler(message, handle_open_folder)
        bot.delete_message(message.chat.id, message.message_id)

    def handle_search_query(message):
        query = message.text
        try:
            # Вызов Gemini API для поиска
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(
                f"Найди информацию: {query}"
            )
            # Объединяем все части ответа в одну строку
            response_text = "".join(part.text for part in response.parts)
        except Exception as e:
            response_text = f"Ошибка при выполнении поиска: {str(e)}"
        
        bot.send_message(message.chat.id, response_text)
        bot.send_message(message.chat.id, "Выберите следующее действие:", reply_markup=get_deepseek_keyboard())

    def handle_internet_search_query(message):
        query = message.text
        try:
            # Вызов Gemini API для поиска в интернете
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(
                f"Найди информацию в интернете: {query}"
            )
            # Объединяем все части ответа в одну строку
            response_text = "".join(part.text for part in response.parts)
        except Exception as e:
            response_text = f"Ошибка при выполнении поиска в интернете: {str(e)}"
        
        bot.send_message(message.chat.id, response_text)
        bot.send_message(message.chat.id, "Выберите следующее действие:", reply_markup=get_deepseek_keyboard())   



    # Обработчик запроса для открытия папки
    def handle_open_folder(message):
        folder_path = message.text
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            os.startfile(folder_path)
            bot.send_message(message.chat.id, f"Папка открыта: {folder_path}")
        else:
            bot.send_message(message.chat.id, "Папка не найдена. Пожалуйста, проверьте путь.")
        bot.send_message(message.chat.id, "Выберите следующее действие:", reply_markup=get_deepseek_keyboard())
    
    @bot.message_handler(func=lambda message: message.text in ['⏯️ Пауза / ⏸️ Воспроизведение', '▶️ Перемотать вперед', '◀️ Перемотать назад'])
    def handle_video_controls(message):
        action = message.text
        if action == '⏯️ Пауза / ⏸️ Воспроизведение':
            pyautogui.press('space')
        elif action == '▶️ Перемотать вперед':
            pyautogui.press('right')
        elif action == '◀️ Перемотать назад':
            pyautogui.press('left')
        bot.delete_message(message.chat.id, message.message_id)

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
        bot.delete_message(message.chat.id, message.message_id)

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
        global last_keyboard_message_id
        try:
            if last_keyboard_message_id:
                # Редактируем сообщение, обновляя только клавиатуру
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=last_keyboard_message_id,
                    reply_markup=get_volume_keyboard(is_muted())
                )
            else:
                # Если message_id не сохранен, отправляем новое сообщение
                sent_message = bot.send_message(
                    chat_id=message.chat.id,
                    text="Управление громкостью",
                    reply_markup=get_volume_keyboard(is_muted())
                )
                last_keyboard_message_id = sent_message.message_id
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
            response = f'Громкость повышена. Текущая громкость: {current_volume_percent}%'
        elif action == '🔉 Понизить громкость':
            current_volume_percent = decrease_volume()
            response = f'Громкость понижена. Текущая громкость: {current_volume_percent}%'
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
                    return  # Завершаем функцию, если все успешно
            else:
                bot.send_message(
                    message.chat.id, "Не удалось запустить YouTube через задачу планировщика.")
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
