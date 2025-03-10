import threading
import time
import asyncio
import requests
import aiohttp
import logging
from deep_translator import GoogleTranslator
from aiogram.types import Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from g4f.client import Client
from src.keyboard.keyboards import get_ai_selection_keyboard, get_dialog_keyboard
from src.states.user_state import user_state_manager
from aiogram.fsm.context import FSMContext
from src.states.dialog_state import DialogStates
from aiogram import Dispatcher, F
from aiogram.filters import Command, StateFilter
from src.database.db_manager import db_manager

logger = logging.getLogger(__name__)

active_generations = {}  # {chat_id: {"stop_event": Event, "loading_thread": Thread}}


def translate_text(text, target_lang="en"):
    return GoogleTranslator(source="auto", target=target_lang).translate(text)


async def save_user_state(state_or_chat_id, new_state: str):
    """Обертка для сохранения состояния пользователя через менеджер состояний"""
    await user_state_manager.save_user_state(state_or_chat_id, new_state)


async def handle_midjourney_command(message: Message, state: FSMContext):
    """Запуск Midjourney по команде /midjourney"""
    await message.answer(
        "Вы выбрали Midjourney. Введите запрос для генерации изображения:",
        reply_markup=get_dialog_keyboard()
    )
    await save_user_state(state, 'midjourney_dialog')
    await state.set_state(DialogStates.waiting_for_midjourney)


async def handle_midjourney(message: Message):
    """Обработчик генерации изображения"""
    chat_id = message.chat.id
    if message.text in ['⬅️ Назад', '⏹️ Завершить диалог']:
        await message.answer(
            "Возврат в меню нейросетей.",
            reply_markup=get_ai_selection_keyboard()
        )
        return

    translated_text = translate_text(message.text)
    loading_message = await message.answer("Генерация картинки...")

    stop_event = threading.Event()
    loading_thread = threading.Thread(
        target=lambda: asyncio.run(
            update_loading_message(loading_message, stop_event))
    )
    loading_thread.start()

    start_time = time.time()

    # 🖼️ Запрос к API для генерации картинки
    client = Client()
    response = client.images.generate(
        model="flux",
        prompt=translated_text,
        response_format="url"
    )

    image_url = response.data[0].url
    image_data = requests.get(image_url).content

    stop_event.set()
    loading_thread.join()

    elapsed_time = round(time.time() - start_time, 2)

    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=loading_message.message_id,
        text=f"✅ Картинка сгенерирована за {elapsed_time} сек!"
    )
    await message.bot.send_photo(message.chat.id, photo=image_data)


async def update_loading_message(message: Message, stop_event: asyncio.Event):
    """Обновление сообщения о загрузке"""
    counter = 0
    last_text = ""
    update_interval = 5  # увеличиваем интервал до 5 секунд

    while not stop_event.is_set():
        try:
            # Обновляем только каждые 5 секунд
            new_text = f"Картинка генерируется лишь {counter} сек"

            if new_text != last_text:
                try:
                    await message.edit_text(new_text)
                    last_text = new_text
                except Exception as e:
                    if "message is not modified" not in str(e):
                        logger.debug(f"Update error: {e}")

            # Увеличиваем счетчик каждую секунду, но обновляем сообщение реже
            await asyncio.sleep(1)
            counter += 1

        except Exception as e:
            await asyncio.sleep(1)
            counter += 1


async def handle_midjourney_choice(message: Message, state: FSMContext):
    """Обработчик выбора Midjourney из меню"""
    await message.answer(
        "Вы выбрали Midjourney. Введите запрос для генерации изображения.",
        reply_markup=get_dialog_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_midjourney)


async def handle_midjourney_dialog(message: Message, state: FSMContext):
    chat_id = message.chat.id

    if message.text in ['⬅️ Назад', '⏹️ Завершить диалог']:
        await message.answer(
            "Возврат в меню нейросетей.",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(state, 'ai_selection')
        await state.clear()
        return

    if chat_id in active_generations:
        await message.answer("У вас уже есть активная генерация. Дождитесь её завершения.")
        return

    await db_manager.save_dialog_message(chat_id, "midjourney", "user", message.text)
    translated_text = translate_text(message.text)

    loading_message = await message.answer("Генерация картинки...")

    stop_event = asyncio.Event()
    update_task = asyncio.create_task(
        update_loading_message(loading_message, stop_event))

    active_generations[chat_id] = {
        "stop_event": stop_event,
        "update_task": update_task
    }

    start_time = time.time()

    try:
        client = Client()
        async with aiohttp.ClientSession() as session:
            response = await client.images.async_generate(
                model="flux",
                prompt=translated_text,
                response_format="url"
            )

            image_url = response.data[0].url
            async with session.get(image_url) as img_response:
                image_data = await img_response.read()

            input_file = BufferedInputFile(
                file=image_data,
                filename="generated_image.png"
            )

            stop_event.set()
            await update_task

            elapsed_time = round(time.time() - start_time, 2)
            await loading_message.edit_text(
                f"✅ Картинка сгенерирована за {elapsed_time} сек!"
            )
            await message.answer_photo(photo=input_file)

    except Exception as e:
        stop_event.set()
        await update_task

        await loading_message.edit_text(
            f"❌ Ошибка при генерации изображения: {str(e)}"
        )
        logger.error(f"Error in Midjourney generation: {str(e)}")

    finally:
        if chat_id in active_generations:
            del active_generations[chat_id]


def register_midjourney_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для Midjourney"""
    dp.message.register(handle_midjourney_command, Command('midjourney'))
    dp.message.register(handle_midjourney_dialog, StateFilter(
        DialogStates.waiting_for_midjourney))
    dp.message.register(handle_midjourney_choice, F.text == 'Midjourney')
