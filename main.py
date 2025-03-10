import sys
import subprocess
import os
from threading import Thread
import time
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.methods import DeleteWebhook
from aiogram.fsm.storage.memory import MemoryStorage
from src.handlers.bot_handlers import setup_handlers, dp
from dotenv import load_dotenv
import os

load_dotenv()  # загружаем переменные из .env
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)

# Флаг работы бота
is_running = True


async def start_bot():
    """Запускает бота."""
    try:
        # Удаляем вебхук и пропускаем необработанные обновления
        await bot(DeleteWebhook(drop_pending_updates=True))

        # Регистрируем обработчики
        await setup_handlers(bot)

        # Запускаем поллинг
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)


async def main():
    """Основная функция для запуска бота."""
    global is_running 

    logger.info("Бот запущен. Чтобы остановить бота, нажмите Ctrl+C.")

    try:
        # Запускаем бота
        await start_bot()
    except KeyboardInterrupt:
        logger.info("\nПолучен сигнал остановки. Остановка бота...")
        is_running = False
        await bot.session.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        is_running = False
        await bot.session.close()
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Запускаем асинхронный цикл событий
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
        sys.exit(0)
