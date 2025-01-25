import time
import pyautogui
from telebot import types
import telebot
import webbrowser
import subprocess
import config
import logging
import os
from pywinauto import Application, findwindows
from fuzzywuzzy import process
from pywinauto import Application, findwindows
import pygetwindow as gw
import shlex
from config import POPULAR_SITES, TRANSLATIONS
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN)




def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    video_button = types.KeyboardButton('Видео')
    computer_button = types.KeyboardButton('Компьютер')
    markup.row(video_button, computer_button)
    return markup

def open_webpage(url, chat_id):
    """Открывает веб-страницу в браузере и отправляет уведомление."""
    try:
        webbrowser.open(url)
        bot.send_message(chat_id, f"Открываю: {url}")
    except Exception as e:
        logger.error(f"Failed to open URL: {url}. Error: {e}")
        bot.send_message(chat_id, f"Не удалось открыть URL: {url}. Произошла ошибка.")


@bot.message_handler(commands=['start'])
def start(message):
    try:
        bot.send_message(
            message.chat.id, f'Привет, {message.from_user.first_name}', reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


@bot.message_handler(func=lambda message: message.text == 'Назад')
def back(message):
    bot.send_message(message.chat.id, "Назад",
                     reply_markup=get_main_keyboard())
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(func=lambda message: message.text == 'Видео')
def handle_video(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    pause_button = types.KeyboardButton('⏯️ Пауза / ⏸️ Воспроизведение')
    fast_forward = types.KeyboardButton('▶️ Перемотать вперед')
    fast_backward = types.KeyboardButton('◀️ Перемотать назад')

    back_button = types.KeyboardButton('Назад')

    markup.row(pause_button)
    markup.row(fast_backward, fast_forward)
    markup.add(back_button)
    bot.send_message(message.chat.id, "Управление видео", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == 'Компьютер')
def handle_computer(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    off_button = types.KeyboardButton('Выключить компьютер')
    restart_button = types.KeyboardButton('Перезагрузить компьютер')
    open_site_button = types.KeyboardButton('Открыть сайт')
    full_screen_button = types.KeyboardButton('📺 На весь экран')
    mouse_button = types.KeyboardButton('Мышь')
    back_button = types.KeyboardButton('Назад')
    markup.add(off_button, restart_button)
    markup.add(open_site_button, full_screen_button, mouse_button)
    markup.add(back_button)
    bot.send_message(
        message.chat.id, "Управление компьютером", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '⏯️ Пауза / ⏸️ Воспроизведение')
def video_pause(message):
    pyautogui.press('space')
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(func=lambda message: message.text == '▶️ Перемотать вперед')
def fast_forward(message):
    pyautogui.press('right')
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(func=lambda message: message.text == '◀️ Перемотать назад')
def fast_backward(message):
    pyautogui.press('left')
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(func=lambda message: message.text == 'Мышь')
def mouse(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    left_button = types.KeyboardButton('Лево')
    right_button = types.KeyboardButton('Право')
    back_button = types.KeyboardButton('Назад')
    markup.add(left_button, right_button)
    markup.add(back_button)
    bot.delete_message(message.chat.id, message.message_id)

    msg = bot.send_message(
        message.chat.id, "Управление мышью", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in ['Лево', 'Право'])
def handle_mouse(message):
    if message.text == 'Лево':
        pyautogui.click(button='left')
        bot.delete_message(message.chat.id, message.message_id)
    elif message.text == 'Право':
        pyautogui.click(button='right')
        bot.delete_message(message.chat.id, message.message_id)


def get_closest_site(query):
    """Функция для поиска наиболее близкого сайта по названию."""
    closest_match, score = process.extractOne(query, POPULAR_SITES.keys())
    if score > 70:
        return POPULAR_SITES[closest_match]
    return None


@bot.message_handler(func=lambda message: message.text == '📺 На весь экран')
def fullscreen(message):
    bot.send_message(
        message.chat.id, 'Открываю текущее приложение на весь экран.')
    active_window = gw.getActiveWindow()
    if active_window:
        active_window.maximize()
    else:
        print("Нет активного окна")

def get_closest_app(query):
    """Функция для поиска наиболее близкого приложения по названию."""
    closest_match, score = process.extractOne(query, TRANSLATIONS.keys())
    if score > 60:
        return TRANSLATIONS[closest_match]
    return None

def open_file(path):
    """Открывает файл или папку по пути."""
    try:
        os.startfile(path)
        print(f"Открываю: {path}")
        return True
    except Exception as e:
         print(f"Ошибка при открытии файла или папки: {e}")
         return False


def open_application(query):
    """Открывает приложение или папку по указанной команде."""
    query = query.lower().strip()
    print(f"Команда в open_application: {query}")
    closest_app = get_closest_app(query)  # Найти ближайшее приложение
    if closest_app:
        if os.path.exists(closest_app):
            if closest_app.endswith(".exe"):
                try:
                    subprocess.Popen([closest_app])
                    print(f"Открываю {query} через subprocess...")
                    return True
                except Exception as e:
                    print(f"Ошибка при открытии {query}: {e}")
                    return False
            elif closest_app.endswith(".lnk"):
                return open_file(closest_app)
            else:  # Если это папка
                 return open_file(closest_app)

        else:
            print(f"Путь для {query} не существует: {closest_app}")
    else:
        print(f"Не найдено подходящего приложения для команды '{query}'")
    return False

def handle_shutdown_restart_choice(message, action):
    """Общий обработчик для подтверждения перезагрузки и выключения."""
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
        bot.send_message(message.chat.id, f'Ошибка при {action} компьютера')
    except Exception as e:
         logger.error(f"Error in {action} command: {e}")
         bot.send_message(message.chat.id, 'Произошла ошибка')
    finally:
        bot.send_message(message.chat.id, 'Вернулся к основному меню',
                         reply_markup=get_main_keyboard())
        

@bot.message_handler(func=lambda message: message.text == 'Выключить компьютер')
def shutdown(message):
    try:
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(text='Да'),
                   types.KeyboardButton(text='Нет'))
        bot.send_message(
            message.chat.id, 'Вы хотите выключить компьютер?', reply_markup=markup)
        bot.register_next_step_handler(message, lambda msg: handle_shutdown_restart_choice(msg, 'выключение'))
    except Exception as e:
        logger.error(f"Error in shutdown command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')

@bot.message_handler(func=lambda message: message.text == 'Перезагрузить компьютер')
def restart(message):
    try:
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(text='Да'),
                   types.KeyboardButton(text='Нет'))
        bot.send_message(
            message.chat.id, 'Вы хотите перезагрузить компьютер?', reply_markup=markup)
        bot.register_next_step_handler(message,  lambda msg: handle_shutdown_restart_choice(msg, 'перезагрузка'))
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Ошибка при перезагрузке компьютера')
    except Exception as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


@bot.message_handler(func=lambda message: message.text == 'Открыть сайт')
def open_site_handler(message):
    """Обработчик нажатия на кнопку 'Открыть сайт'. Запрашивает у пользователя название."""
    bot.send_message(message.chat.id, 'Введите название сайта или приложения.')
    bot.register_next_step_handler(message, handle_site_or_app_input)


def handle_site_or_app_input(message):
    """Обрабатывает ввод пользователя после нажатия на кнопку 'Открыть сайт'."""
    query = message.text.strip().lower()
    if not query:
        bot.send_message(message.chat.id, "Вы не ввели название сайта или приложения.")
        return
    try:
        closest_site = get_closest_site(query)
        closest_app = get_closest_app(query)

        if closest_app:  # Если нашли приложение
            if open_application(query):
                bot.send_message(message.chat.id, "Открываю приложение...")
            else:
                bot.send_message(
                    message.chat.id, f'Не удалось открыть приложение "{query}".')
        elif closest_site:  # Если нашли сайт
           open_webpage(closest_site, message.chat.id)
        else:  # Если не нашли ни приложение, ни сайт
            bot.send_message(
                message.chat.id, f'Не нашёл сайт "{query}" в списке популярных. Ищу в Яндексе.')
            search_url = f"https://yandex.ru/search/?text={query}"
            open_webpage(search_url, message.chat.id)

    except Exception as e:
        logger.error(f"Error while handling message: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


try:
    bot.polling(none_stop=True)
except Exception as e:
    logger.critical(f"Polling stopped due to error: {e}")