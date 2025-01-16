import telebot
import webbrowser
from telebot import types

# Создаем объект бота с указанным токеном
bot = telebot.TeleBot('7616648953:AAEbzkEo7zmVe1QALD3flEe_mtru7xfNtns')


@bot.message_handler(commands=['start', 'main', 'hello'])
def start(message):
    """
    Обработчик команды /start (а также /main и /hello).
    Создает клавиатуру с кнопками и отправляет приветственное сообщение и фото.
    """
    # Создаем клавиатуру с кнопками
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    site_button = types.KeyboardButton('Перейти на сайт')  # Кнопка для перехода на сайт
    delete_button = types.KeyboardButton('Удалить фото')   # Кнопка для удаления фото
    edit_button = types.KeyboardButton('Редактировать фото')  # Кнопка для редактирования фото
    markup.row(site_button)  # Добавляем кнопку в одну строку
    markup.add(edit_button, delete_button)  # Добавляем остальные кнопки

    # Отправляем приветственное сообщение с клавиатурой
    bot.send_message(message.chat.id, 'Привет', reply_markup=markup)

    # Отправляем фото, если файл доступен
    try:
        with open('./image.png', 'rb') as file:  # Открываем файл изображения в бинарном режиме
            bot.send_photo(message.chat.id, file)  # Отправляем фото пользователю
    except FileNotFoundError:  # Обрабатываем случай, если файл не найден
        bot.send_message(message.chat.id, 'Файл с изображением не найден.')


@bot.message_handler(func=lambda message: message.text in ['Перейти на сайт', 'Удалить фото', 'Редактировать фото'])
def on_click(message):
    """
    Обработчик текстовых сообщений, связанных с кнопками клавиатуры.
    Реагирует на текстовые команды: "Перейти на сайт", "Удалить фото", "Редактировать фото".
    """
    if message.text == 'Перейти на сайт':
        # Отправляем сообщение и открываем сайт в браузере
        bot.send_message(message.chat.id, 'Сайт открыт')
        webbrowser.open('https://github.com/daniilkostrykin?tab=repositories')
    elif message.text == 'Удалить фото':
        # Сообщаем пользователю, что фото удалено
        bot.send_message(message.chat.id, 'Фото удалено')
    elif message.text == 'Редактировать фото':
        # Уведомляем, что функция редактирования пока недоступна
        bot.send_message(message.chat.id, 'Редактирование фото пока не доступно.')


@bot.message_handler(content_types=['photo'])
def get_photo(message):
    """
    Обработчик сообщений с фотографиями.
    Отвечает пользователю и предлагает действия через инлайн-клавиатуру.
    """
    # Создаем инлайн-клавиатуру с кнопками
    markup = types.InlineKeyboardMarkup()
    site_button = types.InlineKeyboardButton('Перейти на сайт', url='https://github.com/daniilkostrykin?tab=repositories')  # Кнопка для перехода на сайт
    delete_button = types.InlineKeyboardButton('Удалить фото', callback_data='delete')  # Кнопка для удаления фото
    edit_button = types.InlineKeyboardButton('Редактировать фото', callback_data='edit')  # Кнопка для редактирования фото
    markup.add(site_button)  # Добавляем кнопку для сайта
    markup.add(edit_button, delete_button)  # Добавляем кнопки для редактирования и удаления

    # Отправляем сообщение с инлайн-клавиатурой
    bot.reply_to(message, 'Красивая фотка!', reply_markup=markup)


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    """
    Обработчик инлайн-кнопок.
    Реагирует на нажатие кнопок "Редактировать фото" и "Удалить фото".
    """
    if callback.data == 'edit':
        # Изменяем текст сообщения
        bot.edit_message_text('Edit text', callback.message.chat.id, callback.message.message_id)
    elif callback.data == 'delete':
        # Удаляем сообщение
        bot.delete_message(callback.message.chat.id, callback.message.message_id)


@bot.message_handler(commands=['help'])
def help_command(message):
    """
    Обработчик команды /help.
    Отправляет сообщение с текстом помощи.
    """
    bot.send_message(message.chat.id, 'Такому самостоятельному человеку, как ты, не нужна помощь')


@bot.message_handler()
def info(message):
    """
    Обработчик текстовых сообщений.
    Реагирует на сообщения "привет" и "id", а также на любые другие сообщения.
    """
    if message.text.lower() == 'привет':
        # Отвечаем приветствием
        bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}')
    elif message.text.lower() == 'id':
        # Отправляем ID пользователя
        bot.reply_to(message, f'ID: {message.from_user.id}')
    else:
        # Сообщаем, что команда не распознана
        bot.send_message(message.chat.id, 'Команда не распознана')


# Запускаем бота в режиме бесконечного опроса
bot.polling(none_stop=True)
