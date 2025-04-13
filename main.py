import sys
import logging
import asyncio
import nest_asyncio
import streamlit as st
from aiogram import Bot
from aiogram.methods import DeleteWebhook
from src.handlers.bot_handlers import setup_handlers, dp
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

# Применяем patch, чтобы можно было запускать asyncio в Streamlit
nest_asyncio.apply()


async def start_bot():
    try:
        await bot(DeleteWebhook(drop_pending_updates=True))
        await setup_handlers(bot)
        await dp.start_polling(bot, handle_signals=False)  # 💥 вот это главное
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        if "database" not in str(e).lower():
            raise
        logger.info("Продолжаем работу без базы данных")

# UI Streamlit
st.title("🤖 Telegram Bot Controller")

# Инициализация состояния сессии, если оно не существует
if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

# Автоматический запуск бота при первой загрузке страницы, если не запущен
if not st.session_state.bot_running:
    # Устанавливаем флаг, чтобы избежать повторных запусков
    st.session_state.bot_running = True
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())  # Запускаем асинхронную функцию
    st.success("Бот автоматически запущен при загрузке страницы!")

# Опциональная кнопка для ручного запуска или перезапуска
# Если хочешь, чтобы была возможность перезапустить бот вручную, раскомментируй эту часть:
if st.button("🚀 Запустить бота заново"):
    st.session_state.bot_running = False  # Сброс флага
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())  # Перезапуск
    st.success("Бот перезапущен!")
