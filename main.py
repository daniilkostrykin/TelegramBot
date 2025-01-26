# main.py

import logging
import telebot
from config import BOT_TOKEN
from bot_handlers import setup_handlers
from pywinauto import Application, findwindows

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
setup_handlers(bot)

if __name__ == '__main__':
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.critical(f"Polling stopped due to error: {e}")
