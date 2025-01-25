import time
import pyautogui
from telebot import types
import telebot
import webbrowser
import subprocess
import config
import logging
import os
from fuzzywuzzy import process
from pywinauto import Application, findwindows
import pygetwindow as gw
import shlex
from config import POPULAR_SITES, TRANSLATIONS
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

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
        bot.send_message(
            chat_id, f"Не удалось открыть URL: {url}. Произошла ошибка.")


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
    volume_button = types.KeyboardButton('Громкость')
    back_button = types.KeyboardButton('Назад')
    markup.add(off_button, restart_button)
    markup.add(open_site_button, full_screen_button,
               mouse_button, volume_button)
    markup.add(back_button)
    bot.send_message(
        message.chat.id, "Управление компьютером", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in ['⏯️ Пауза / ⏸️ Воспроизведение', '▶️ Перемотать вперед', '◀️ Перемотать назад'])
def handle_video_controls(message):
    """Обрабатывает управление видео: пауза/воспроизведение, перемотка вперед и назад."""
    action = message.text
    if action == '⏯️ Пауза / ⏸️ Воспроизведение':
        pyautogui.press('space')
    elif action == '▶️ Перемотать вперед':
        pyautogui.press('right')
    elif action == '◀️ Перемотать назад':
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


@bot.message_handler(func=lambda message: message.text == 'Громкость')
def volume(message):
    """Отображает клавиатуру управления громкостью."""
    update_volume_keyboard(message)

def update_volume_keyboard(message):
    """Обновляет клавиатуру в зависимости от состояния звука."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    mute_button = types.KeyboardButton('🔊 Включить звук' if is_muted() else '🔇 Выключить звук')
    up_button = types.KeyboardButton('🔊 Повысить громкость')
    down_button = types.KeyboardButton('🔉 Понизить громкость')
    back_button = types.KeyboardButton('Назад')
    markup.add(mute_button)
    markup.add(up_button, down_button)
    markup.add(back_button)
    bot.send_message(message.chat.id, "Управление громкостью", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['🔇 Выключить звук', '🔊 Включить звук', '🔊 Повысить громкость', '🔉 Понизить громкость'])
def handle_volume_controls(message):
    """Обрабатывает управление громкостью."""
    action = message.text
    if action == '🔇 Выключить звук':
        mute_volume()
        response = "Звук выключен."
    elif action == '🔊 Включить звук':
        unmute_volume()
        response = "Звук включен."
    elif action == '🔊 Повысить громкость':
        increase_volume(message=message)
        return 
    elif action == '🔉 Понизить громкость':
        decrease_volume(message=message)
        return 

    bot.send_message(message.chat.id, response)
    update_volume_keyboard(message)

def get_audio_endpoint():
    """Получает основной аудио-интерфейс."""
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return volume

def is_muted():
    """Проверяет, выключен ли звук."""
    volume = get_audio_endpoint()
    return volume.GetMute()

def set_volume(volume_level):
    """Устанавливает уровень громкости (от 0 до 1)."""
    volume = get_audio_endpoint()
    volume.SetMasterVolumeLevelScalar(volume_level, None)

def mute_volume():
    """Выключает звук."""
    volume = get_audio_endpoint()
    volume.SetMute(1, None)

def unmute_volume():
    """Включает звук."""
    volume = get_audio_endpoint()
    volume.SetMute(0, None)

def increase_volume(increment=0.1, message=None):
    """Увеличивает громкость на указанную величину и отправляет сообщение."""
    volume = get_audio_endpoint()
    current_volume = volume.GetMasterVolumeLevelScalar()
    new_volume = min(1, current_volume + increment)
    set_volume(new_volume)
    current_volume_percent = int(new_volume * 100)
    bot.send_message(
        message.chat.id, f'Громкость повышена. Текущая громкость: {current_volume_percent}%')

def decrease_volume(decrement=0.1, message=None):
    """Уменьшает громкость на указанную величину и отправляет сообщение."""
    volume = get_audio_endpoint()
    current_volume = volume.GetMasterVolumeLevelScalar()
    new_volume = max(0, current_volume - decrement)
    set_volume(new_volume)
    current_volume_percent = int(new_volume * 100)
    bot.send_message(
        message.chat.id, f'Громкость понижена. Текущая громкость: {current_volume_percent}%')


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
        bot.register_next_step_handler(
            message, lambda msg: handle_shutdown_restart_choice(msg, 'выключение'))
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
        bot.register_next_step_handler(
            message, lambda msg: handle_shutdown_restart_choice(msg, 'перезагрузка'))
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
        bot.send_message(
            message.chat.id, "Вы не ввели название сайта или приложения.")
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
