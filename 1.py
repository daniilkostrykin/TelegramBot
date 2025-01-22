import telebot
import webbrowser
from telebot import types
import subprocess
import config
import logging
from fuzzywuzzy import process  # Библиотека для поиска ближайшего совпадения

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN)

# Словарь популярных сайтов России
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


def get_closest_site(query):
    """Функция для поиска наиболее близкого сайта по названию."""
    closest_match, score = process.extractOne(query, popular_sites.keys())
    if score > 70:  # Порог совпадения
        return popular_sites[closest_match]
    return None


@bot.message_handler(commands=['start'])
def start(message):
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        off_button = types.KeyboardButton('Выключить компьютер')
        restart_button = types.KeyboardButton('Перезагрузить компьютер')
        open_site_button = types.KeyboardButton('Открыть сайт')
        markup.row(off_button, restart_button)
        markup.add(open_site_button)
        bot.send_message(message.chat.id, 'Привет', reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


@bot.message_handler(func=lambda message: message.text == 'Выключить компьютер')
def shutdown(message):
    try:
        bot.send_message(message.chat.id, 'Выключение компьютера...')
        subprocess.run(["shutdown", "/s", "/t", "1"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in shutdown command: {e}")
        bot.send_message(message.chat.id, 'Ошибка при выключении компьютера')
    except Exception as e:
        logger.error(f"Error in shutdown command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


@bot.message_handler(func=lambda message: message.text == 'Перезагрузить компьютер')
def restart(message):
    try:
        bot.send_message(message.chat.id, 'Перезагрузка компьютера...')
        subprocess.run(["shutdown", "/r", "/t", "1"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Ошибка при перезагрузке компьютера')
    except Exception as e:
        logger.error(f"Error in restart command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


# Обработчик для всех текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    query = message.text.strip().lower()
    try:
        # Ищем наиболее близкий сайт
        closest_site = get_closest_site(query)
        if closest_site:
            bot.send_message(message.chat.id, f'Открываю {closest_site}')
            webbrowser.open(closest_site)
        else:
            # Если сайт не найден, выполняем поиск
            bot.send_message(
                message.chat.id, f'Не нашёл сайт "{query}" в списке популярных. Попробую поискать в Яндексе.')
            search_url = f"https://yandex.ru/search/?text={query}"
            bot.send_message(message.chat.id, f'Ищу по запросу: {search_url}')
            webbrowser.open(search_url)
    except Exception as e:
        logger.error(f"Error while handling message: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')


# Запуск бота
try:
    bot.polling(none_stop=True)
except Exception as e:
    logger.critical(f"Polling stopped due to error: {e}")
