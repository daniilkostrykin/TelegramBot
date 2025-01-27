# main.py

import sys
from threading import Thread
import tkinter as tk
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


# Флаг для отслеживания состояния бота
bot_running = False


def start_bot():
    """Запускает бота в отдельном потоке."""
    global bot_running
    try:
        bot_running = True  # Устанавливаем флаг, что бот запущен
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        sys.exit(1)


def on_closing():
    """Обработчик события закрытия окна."""
    global bot_running
    print("Окно закрыто. Остановка бота...")
    if bot_running:
        bot.stop_polling()  # Останавливаем бота, если он был запущен
    root.destroy()  # Закрываем окно
    sys.exit(0)  # Завершаем программу


# Создаем главное окно
root = tk.Tk()
root.title("Telegram Bot")
root.geometry("300x60")
root.configure(bg="black")  # Устанавливаем черный фон окна

# Добавляем текст в окно
label = tk.Label(
    root,
    text="Бот запущен. Закройте окно, чтобы остановить бота.",
    fg="white",  # Белый текст
    bg="black"   # Черный фон
)
label.pack(pady=20)

# Запускаем бота в отдельном потоке
bot_thread = Thread(target=start_bot)
bot_thread.daemon = True  # Поток завершится при закрытии основного потока
bot_thread.start()

# Назначаем обработчик закрытия окна
root.protocol("WM_DELETE_WINDOW", on_closing)

# Запускаем главный цикл окна
root.mainloop()
