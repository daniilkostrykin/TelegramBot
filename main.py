import sys
import subprocess
import os
from threading import Thread
import time
import logging
import telebot
from z.config import BOT_TOKEN
from z.bot_handlers import setup_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
setup_handlers(bot)

bot_running = False  # Флаг работы бота
#vcxsrv_process = None  # Переменная для процесса VcXsrv


#def start_vcxsrv():
#    """Запускает сервер VcXsrv."""
#    global vcxsrv_process
#    try:
#        vcxsrv_process = subprocess.Popen(
#            [r"C:\Program Files\VcXsrv\vcxsrv.exe",
#                ":0", "-ac", "-multiwindow", "-wgl"],
#            stdout=subprocess.DEVNULL,
#            stderr=subprocess.DEVNULL
#        )
#        os.environ["DISPLAY"] = "localhost:0"
#        print("VcXsrv запущен.")
#        time.sleep(2)  # Небольшая пауза, чтобы сервер успел запуститься
#    except Exception as e:
#        print(f"Ошибка при запуске VcXsrv: {e}")
#        sys.exit(1)


#def stop_vcxsrv():
#    """Останавливает сервер VcXsrv."""
#    try:
#        subprocess.run(["taskkill", "/F", "/IM", "vcxsrv.exe"], check=True)
#        print("VcXsrv успешно завершён.")
#    except subprocess.CalledProcessError:
#        print("VcXsrv уже был закрыт или произошла ошибка.")


def start_bot():
    """Запускает бота в отдельном потоке."""
    global bot_running
    try:
        bot_running = True
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        sys.exit(1)


def main():
    """Основная функция для запуска бота."""
    global bot_running

    # === Запускаем VcXsrv ===
    #start_vcxsrv()

    # === Запускаем бота в отдельном потоке ===
    bot_thread = Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()

    print("Бот запущен.  Чтобы остановить бота, нажмите Ctrl+C.")

    try:
        while True:
            time.sleep(1)  # Даём боту работать
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки.  Остановка бота...")
        bot_running = False
        bot.stop_polling()
        #stop_vcxsrv()
        sys.exit(0)

if __name__ == "__main__":
    main()