import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from z.config import BOT_TOKEN
# Укажите ваш токен бота

# Создаем объект бота
bot = telebot.TeleBot(BOT_TOKEN)

# Хендлер для команды /start
@bot.message_handler(commands=['start'])
def start(message):
    # Создаем клавиатуру с кнопкой
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton(
            text='Открыть сайт',
            web_app=WebAppInfo(url='https://remotedesktop.google.com/access/')
        )
    )
    # Отправляем приветственное сообщение с клавиатурой
    bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}!', reply_markup=markup)

# Запуск бота
if __name__ == '__main__':
    bot.polling(none_stop=True)
