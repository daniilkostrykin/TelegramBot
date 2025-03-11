import logging
import os
import asyncio
import traceback
import PIL.Image
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
import google.generativeai as genai
from src.formaters.format import safe_send_message
from src.states.dialog_state import DialogStates, dialog_manager
from src.database.db_manager import db_manager
from src.keyboard.keyboards import get_ai_selection_keyboard, get_dialog_keyboard, get_gemini_model_keyboard
from src.states.user_state import user_state_manager

logger = logging.getLogger(__name__)

# Конфигурация Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


async def save_user_state(state_or_chat_id, new_state: str):
    """Обертка для сохранения состояния пользователя через менеджер состояний"""
    await user_state_manager.save_user_state(state_or_chat_id, new_state)


async def handle_gemini_command(message: Message, state: FSMContext):
    """Запуск Gemini по команде /gemini"""
    chat_id = message.chat.id
    dialog_manager.clear_dialog_history(chat_id)

    model_name = 'gemini-2.0-flash-exp'
    await state.update_data(model_name=model_name)
    await message.answer(
        "Вы выбрали Gemini.\nВведите запрос:",
        reply_markup=get_dialog_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_dialog)


async def handle_gemini_choice(message: Message, state: FSMContext):
    """Обработчик выбора Gemini из меню"""
    chat_id = message.chat.id
    dialog_manager.clear_dialog_history(chat_id)

    await message.answer(
        "Вы выбрали Gemini.",
        reply_markup=get_gemini_model_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_model_selection)


async def handle_model_selection(message: Message, state: FSMContext):
    """Обработчик выбора модели Gemini"""
    chat_id = message.chat.id

    if message.text == '⬅️ Назад':
        await message.answer(
            "Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        dialog_manager.clear_dialog_history(chat_id)
        await state.clear()
        return

    model_mapping = {
        'Gemini 2.0 Experimental': 'gemini-2.0-flash-exp',
        'Gemini 1.5 Pro': 'gemini-1.5-pro',
        'Gemini 1.5 Flash': 'gemini-1.5-flash',
        'Gemini 2.0 Pro Experimental 02-05': 'gemini-2.0-pro-exp-02-05',
        'Gemini 2.0 Flash': 'gemini-2.0-flash'
    }

    model_name = model_mapping.get(message.text)
    if not model_name:
        await message.answer("Неверный выбор модели. Попробуйте снова.")
        return

    await state.update_data(model_name=model_name)
    await message.answer(
        f"Вы выбрали: {model_name}. Начните диалог.",
        reply_markup=get_dialog_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_dialog)


async def handle_dialog(message: Message, state: FSMContext):
    """Обработчик диалога с Gemini"""
    chat_id = message.chat.id

    if message.text == '⏹️ Завершить диалог':
        await message.answer(
            "Диалог завершен.",
            reply_markup=get_ai_selection_keyboard()
        )
        dialog_manager.clear_dialog_history(chat_id)
        await state.clear()
        return

    if message.text == '⬅️ Назад':
        await message.answer(
            "Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        dialog_manager.clear_dialog_history(chat_id)
        await state.clear()
        return

    data = await state.get_data()
    model_name = data.get('model_name', 'gemini-2.0-flash-exp')

    query = message.text
    await db_manager.save_dialog_message(chat_id, model_name, "user", query)

    sent_message = await message.answer("Генерация ответа...")
    dialog_manager.set_active_generation(chat_id, True)

    try:
        model = genai.GenerativeModel(model_name)
        messages = await db_manager.get_dialog_history(chat_id, model_name)
        print(
            f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

        response = await asyncio.to_thread(model.generate_content, messages)
        response_text = response.text
        await db_manager.save_dialog_message(chat_id, model_name, "model", response_text)

        await safe_send_message(message, response_text)
        await sent_message.delete()

        # Сохраняем состояние для следующего сообщения
        await state.set_state(DialogStates.waiting_for_dialog)
        await save_user_state(state, model_name)

    except Exception as e:
        logger.error(
            f"Ошибка генерации контента: {type(e).__name__} - {str(e)}")
        await message.answer(
            f"Произошла ошибка генерации контента: {str(e)}\nПожалуйста, попробуйте снова."
        )
        # Сохраняем состояние для следующего сообщения
        await state.set_state(DialogStates.waiting_for_dialog)
        await save_user_state(state, model_name)


async def process_dialog_message(message: Message, state: FSMContext):
    """Обработчик сообщений в состоянии диалога с Gemini"""
    logger.info(
        f"process_dialog_message вызван: chat_id={message.chat.id}, текст={message.text}")
    data = await state.get_data()
    logger.info(f"Данные состояния: {data}")
    model_name = data.get('model_name')
    logger.info(f"Выбранная модель: {model_name}")

    if not model_name:
        model_name = 'gemini-2.0-flash-exp'
        logger.warning(
            f"Модель не найдена в состоянии, используем {model_name}")

    # Проверяем, есть ли изображения в сообщении
    if message.photo or message.media_group_id:
        try:
            images = []
            temp_files = []

            if message.media_group_id:
                # Получаем все фото из группы
                media_group = message.photo
                for i, photo in enumerate(media_group):
                    file_info = await message.bot.get_file(photo.file_id)
                    downloaded_file = await message.bot.download_file(file_info.file_path)

                    # Создаем уникальное имя файла для каждого изображения
                    temp_filename = f"temp_image_{message.chat.id}_{i}.jpg"
                    temp_files.append(temp_filename)

                    with open(temp_filename, "wb") as new_file:
                        new_file.write(downloaded_file.read())

                    img = PIL.Image.open(temp_filename)
                    images.append(img)
            else:
                # Обработка одиночного изображения
                photo = message.photo[-1]
                file_info = await message.bot.get_file(photo.file_id)
                downloaded_file = await message.bot.download_file(file_info.file_path)

                temp_filename = f"temp_image_{message.chat.id}_0.jpg"
                temp_files.append(temp_filename)

                with open(temp_filename, "wb") as new_file:
                    new_file.write(downloaded_file.read())

                img = PIL.Image.open(temp_filename)
                images.append(img)

            # Если есть текст с изображениями
            prompt = message.caption if message.caption else "Опишите эти изображения"

            # Создаем модель и генерируем ответ
            model = genai.GenerativeModel(model_name)

            # Формируем запрос с изображениями
            request = [prompt] + images
            response = await asyncio.to_thread(model.generate_content, request)

            # Удаляем временные файлы
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(
                        f"Не удалось удалить временный файл {temp_file}: {e}")

            # Отправляем ответ
            await safe_send_message(message, response.text)

        except Exception as e:
            logger.error(f"Ошибка при обработке изображения: {e}")
            await message.answer(f"Произошла ошибка при обработке изображения: {str(e)}")

            # Пытаемся удалить временные файлы в случае ошибки
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.warning(
                        f"Не удалось удалить временный файл {temp_file}: {e}")
    else:
        # Обычная обработка текстового сообщения
        await handle_dialog(message, state)


def register_gemini_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для Gemini"""
    dp.message.register(handle_gemini_command, Command('gemini'))
    dp.message.register(handle_gemini_choice, F.text == 'Gemini')
    dp.message.register(handle_model_selection, StateFilter(
        DialogStates.waiting_for_model_selection))
    dp.message.register(process_dialog_message, StateFilter(
        DialogStates.waiting_for_dialog))
