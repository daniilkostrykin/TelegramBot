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

# Применяем patch для asyncio в Streamlit
nest_asyncio.apply()

# Глобальная переменная для задачи поллинга
polling_task = None

async def start_bot():
    global polling_task
    try:
        await bot(DeleteWebhook(drop_pending_updates=True))
        await setup_handlers(bot)
        # Запускаем поллинг в отдельной задаче
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
        logger.info("Бот запущен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        if "database" not in str(e).lower():
            raise
        logger.info("Продолжаем работу без базы данных")
        return False

async def stop_bot():
    global polling_task
    try:
        if polling_task:
            dp.stop_polling()
            polling_task.cancel()
            await polling_task
            polling_task = None
        await bot.session.close()
        logger.info("Бот остановлен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}")
        return False

# UI Streamlit
st.title("🤖 Telegram Bot Controller")

# Инициализация состояния
if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

# Автоматический запуск бота при загрузке страницы
if not st.session_state.bot_running:
    st.session_state.bot_running = True
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(start_bot())
    if success:
        st.success("Бот автоматически запущен!")
    else:
        st.error("Не удалось запустить бота.")

# Кнопка для ручного перезапуска бота
if st.button("🔄 Перезапустить бота"):
    if st.session_state.bot_running:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_bot())
    success = loop.run_until_complete(start_bot())
    st.session_state.bot_running = success
    if success:
        st.success("Бот перезапущен!")
    else:
        st.error("Не удалось перезапустить бота.")

# Кнопка для остановки бота
if st.session_state.bot_running and st.button("🛑 Остановить бота"):
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(stop_bot())
    if success:
        st.session_state.bot_running = False
        st.success("Бот остановлен!")
    else:
        st.error("Не удалось остановить бота.")