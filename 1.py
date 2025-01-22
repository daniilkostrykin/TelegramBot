import telebot
import webbrowser
from telebot import types
import subprocess
import config
import logging  # Импортируем модуль logging
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
# Для новых версий Selenium
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN)


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


@bot.message_handler(func=lambda message: message.text == 'Открыть сайт')
def open_site(message):
    try:
        bot.send_message(message.chat.id, 'Какой сайт открыть?')
        bot.register_next_step_handler(message, fetch_site_content)
    except Exception as e:
        logger.error(f"Error in open_site command: {e}")
        bot.send_message(message.chat.id, 'Произошла ошибка')

def fetch_site_content(message):
    query = message.text
    try:
        url = f"https://yandex.ru/search/?text={query}"
        bot.send_message(message.chat.id, f'Ищу "{query}"... вот ссылка: {url}')
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Error while fetching site: {e}")
        bot.send_message(message.chat.id, 'Ошибка при запросе к сайту')


try:
    bot.polling(none_stop=True)
except Exception as e:
    logger.critical(f"Polling stopped due to error: {e}")