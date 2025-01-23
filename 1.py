from telebot import types  # Импортируем правильный тип из telebot
import telebot
import webbrowser
import subprocess
import config
import logging
import os
from pywinauto import Application, findwindows
from fuzzywuzzy import process
from pywinauto import Application, findwindows

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN)

popular_sites = {
    "вк": "https://vk.com",
    "одноклассники": "https://ok.ru",
    "яндекс": "https://yandex.ru",
    "гугл": "https://google.com",
    "мейл": "https://mail.ru",
    "ютуб": "https://youtube.com",
    "твиттер": "https://twitter.com",
    "инстаграм": "https://instagram.com",
    "тг": "https://web.telegram.org",
    "авито": "https://avito.ru",
    "цукерберг позвонит": "https://dtf.ru",
    "хабр": "https://habr.com",
    "музыка": "https://music.yandex.ru",
    "карты": "https://yandex.ru/maps",
    "госуслуги": "https://www.gosuslugi.ru"
}

translations = {
    "рабочий стол": os.path.join(os.path.expanduser("~"), "Desktop"),
    "загрузки": os.path.join(os.path.expanduser("~"), "Downloads"),
    "документы": os.path.join(os.path.expanduser("~"), "Documents"),
    "изображения": os.path.join(os.path.expanduser("~"), "Pictures"),
    "видео": os.path.join(os.path.expanduser("~"), "Videos"),
    "telegram": "C:\\Users\\Daniil\\Downloads\\Telegram Desktop\\AyuGram\\AyuGram.exe",
    "телеграм": "C:\\Users\\Daniil\\Downloads\\Telegram Desktop\\AyuGram\\AyuGram.exe",
    "браузер": "C:\\Users\\Daniil\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Yandex.lnk",
    "блокнот": "C:\\Windows\\System32\\notepad.exe",
    "зона": "C:\\Users\\Daniil\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Zona.lnk",
}


@bot.message_handler(commands=['start'])
def start(message):
    try:
        bot.send_message(
            message.chat.id, f'Привет, {message.from_user.first_name}', reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    off_button = types.KeyboardButton('Выключить компьютер')
    restart_button = types.KeyboardButton('Перезагрузить компьютер')
    open_site_button = types.KeyboardButton('Открыть сайт')
    full_screen_button = types.KeyboardButton('Развернуть окно на весь экран')
    markup.add(off_button, restart_button)
    markup.add(open_site_button, full_screen_button)
    return markup


def get_closest_site(query):
    """Функция для поиска наиболее близкого сайта по названию."""
    closest_match, score = process.extractOne(query, popular_sites.keys())
    if score > 70:
        return popular_sites[closest_match]
    return None


def get_closest_app(query):
    """Функция для поиска наиболее близкого сайта по названию."""
    closest_match, score = process.extractOne(query, translations.keys())
    if score > 60:
        return translations[closest_match]
    return None


def open_application(query):
    """Открывает приложение или папку по указанной команде."""
    query = query.lower().strip()
    print(f"Команда в open_application: {query}")  # Добавленная строка

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
            elif closest_app.endswith(".lnk"):
                try:
                    os.startfile(closest_app)
                    print(f"Открываю {query} через os.startfile...")
                    return True
                except Exception as e:
                    print(f"Ошибка при открытии ярлыка {query}: {e}")
            else:  # Если это папка
                try:
                    os.startfile(closest_app)
                    print(f"Открываю папку {query}...")
                    return True
                except Exception as e:
                    print(f"Ошибка при открытии папки {query}: {e}")
        else:
            print(f"Путь для {query} не существует: {closest_app}")
    else:
        print(f"Не найдено подходящего приложения для команды '{query}'")
    return False


@bot.message_handler(func=lambda message: message.text == 'Выключить компьютер')
def shutdown(message):
    try:
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(text='Да'),
                   types.KeyboardButton(text='Нет'))
        bot.send_message(
            message.chat.id, 'Вы хотите выключить компьютер?', reply_markup=markup)
        bot.register_next_step_handler(message, handle_shutdown_choice)
    except Exception as e:
        logger.error(f"Error in shutdown command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


def handle_shutdown_choice(message):
    try:
        if message.text == 'Да':
            bot.send_message(message.chat.id, 'Выключение компьютера...')
            subprocess.run(["shutdown", "/s", "/t", "5"], check=True)
        elif message.text == 'Нет':
            bot.send_message(message.chat.id, 'Отмена выключения компьютера.')
        else:
            bot.send_message(
                message.chat.id, 'Пожалуйста, выберите "Да" или "Нет".')
        bot.send_message(message.chat.id, 'Вернулся к основному меню',
                         reply_markup=get_main_keyboard())

    except subprocess.CalledProcessError as e:
        logger.error(f"Error in shutdown command: {e}")
        bot.send_message(message.chat.id, 'Ошибка при выключении компьютера')
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
        bot.register_next_step_handler(message, handle_restart_choice)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Ошибка при перезагрузке компьютера')
    except Exception as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


def handle_restart_choice(message):
    try:
        if message.text == 'Да':
            bot.send_message(message.chat.id, 'Перезагрузка компьютера...')
            subprocess.run(["shutdown", "/r", "/t", "5"], check=True)
        elif message.text == 'Нет':
            bot.send_message(
                message.chat.id, 'Отмена перезагрузки компьютера.')
        else:
            bot.send_message(
                message.chat.id, 'Пожалуйста, выберите "Да" или "Нет".')
        bot.send_message(message.chat.id, reply_markup=get_main_keyboard())

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
    try:
        closest_site = get_closest_site(query)
        closest_app = get_closest_app(query)

        if closest_app:  # Если нашли приложение
            if open_application(query):
                bot.send_message(message.chat.id, "Открываю приложение...")
                return
            else:
                bot.send_message(
                    message.chat.id, f'Не удалось открыть приложение "{query}".')
        elif closest_site:  # Если нашли сайт
            bot.send_message(message.chat.id, f'Открываю сайт {closest_site}')
            webbrowser.open(closest_site)
        else:  # Если не нашли ни приложение, ни сайт
            bot.send_message(
                message.chat.id, f'Не нашёл сайт "{query}" в списке популярных. Попробую поискать в Яндексе.')
            search_url = f"https://yandex.ru/search/?text={query}"
            bot.send_message(message.chat.id, f'Ищу по запросу: {search_url}')
            webbrowser.open(search_url)

    except Exception as e:
        logger.error(f"Error while handling message: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


try:
    bot.polling(none_stop=True)
except Exception as e:
    logger.critical(f"Polling stopped due to error: {e}")
 