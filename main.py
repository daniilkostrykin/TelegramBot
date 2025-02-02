import sys
import subprocess
from threading import Thread
import tkinter as tk
import logging
import telebot
from config import BOT_TOKEN
from bot_handlers import setup_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
setup_handlers(bot)

bot_running = False


def start_bot():
    """Запускает бота в отдельном потоке."""
    global bot_running
    try:
        bot_running = True
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        sys.exit(1)


def stop_vcxsrv():
    """Завершает процесс vcxsrv.exe."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "vcxsrv.exe"], check=True)
        print("VcXsrv успешно завершён.")
    except subprocess.CalledProcessError:
        print("Не удалось завершить VcXsrv. Возможно, процесс уже закрыт.")


def on_closing():
    """Обработчик закрытия окна."""
    global bot_running
    print("Окно закрыто. Остановка бота...")
    
    if bot_running:
        bot.stop_polling()

    stop_vcxsrv() 
    root.destroy()
    sys.exit(0)


# Создаём окно
root = tk.Tk()
root.title("Telegram Bot")
root.geometry("300x60")
root.configure(bg="black")

label = tk.Label(
    root,
    text="Бот запущен. Закройте окно, чтобы остановить бота.",
    fg="green",
    bg="black"
)
label.pack(pady=20)

# Запускаем бота в отдельном потоке
bot_thread = Thread(target=start_bot)
bot_thread.daemon = True
bot_thread.start()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
