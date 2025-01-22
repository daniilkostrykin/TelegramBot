import telebot
import webbrowser
from telebot import types
import sqlite3
import config
# Создаем объект бота с указанным токеном
bot = telebot.TeleBot(config.BOT_TOKEN)
name = ''
@bot.message_handler(commands=['start', 'main', 'hello'])
def start(message):
    bot.send_message(message.chat.id, 'Hi')
bot.polling(none_stop=True)
