import logging
import os
import json
import requests
import asyncio
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from src.formaters.format import safe_send_message
from src.models.dialog_state import DialogStates
from src.database.db_manager import db_manager
from z.keyboards import get_ai_selection_keyboard, get_dialog_keyboard

logger = logging.getLogger(__name__)

# Константы для Qwen
API_URL = "https://api.together.xyz/inference"
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

# Локальное хранилище диалогов
dialog_sessions = {}


def get_qwen_response_stream(messages):
    """Получение потокового ответа от Qwen API"""
    if not TOGETHER_API_KEY:
        raise ValueError("TOGETHER_API_KEY не настроен в .env файле")

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "messages": messages,
        "stream": True
    }

    try:
        response = requests.post(
            API_URL, headers=headers, json=data, stream=True)

        if response.status_code != 200:
            logger.error(
                f"Error: {response.status_code}, Response: {response.text}")
            yield None
            return

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8').strip()
                if decoded_line.startswith('data: '):
                    json_data = decoded_line[len('data: '):].strip()
                    if json_data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(json_data)
                        if 'choices' in chunk and chunk['choices']:
                            content = chunk['choices'][0].get('text', '')
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        logger.error(f"Ошибка декодирования JSON: {json_data}")
                        continue

    except Exception as e:
        logger.error(f"Error in get_qwen_response_stream: {e}")
        raise


async def handle_qwen_command(message: Message, state: FSMContext):
    """Обработчик команды /qwen"""
    chat_id = message.chat.id
    dialog_sessions[chat_id] = []

    await message.answer(
        "Начинаю диалог с Qwen. Отправьте ваше сообщение.",
        reply_markup=get_dialog_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_qwen_dialog)


async def handle_qwen_dialog(message: Message, state: FSMContext):
    """Обработчик диалога с Qwen"""
    chat_id = message.chat.id

    if message.text == '⏹️ Завершить диалог':
        await message.answer(
            "Диалог завершен.",
            reply_markup=get_ai_selection_keyboard()
        )
        if chat_id in dialog_sessions:
            del dialog_sessions[chat_id]
        await state.clear()
        return

    sent_message = await message.answer("Генерация ответа...")
    response_text = ""

    try:
        await db_manager.save_dialog_message(chat_id, "qwen", "user", message.text)
        logger.info(f"[LOG] Сообщение пользователя сохранено: {message.text}")

        messages = dialog_sessions.get(chat_id, [])
        messages.append({"role": "user", "content": message.text})
        logger.info(f"[LOG] История диалога: {messages}")

        last_update_time = asyncio.get_event_loop().time()

        for chunk in get_qwen_response_stream(messages):
            if chunk:
                response_text += chunk

                if asyncio.get_event_loop().time() - last_update_time > 2:
                    try:
                        await sent_message.edit_text(f"Генерация ответа...\n\n{response_text[-500:]}")
                    except Exception:
                        pass
                    last_update_time = asyncio.get_event_loop().time()

        if not response_text.strip():
            logger.error("[ERROR] Получен пустой ответ от API")
            await message.answer("Получен пустой ответ от API. Попробуйте еще раз.")
            await sent_message.delete()
            return

        await db_manager.save_dialog_message(chat_id, "qwen", "assistant", response_text)
        logger.info(f"[LOG] Ответ модели сохранен: {response_text[:100]}...")

        messages.append({"role": "assistant", "content": response_text})
        dialog_sessions[chat_id] = messages

        await sent_message.delete()
        await safe_send_message(message, response_text)

    except Exception as e:
        logger.error(f"[ERROR] Ошибка в диалоге Qwen: {e}")
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте позже.",
            reply_markup=get_dialog_keyboard()
        )
        if sent_message:
            await sent_message.delete()


def register_qwen_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для Qwen"""
    dp.message.register(handle_qwen_command, Command('qwen'))
    dp.message.register(handle_qwen_dialog, StateFilter(
        DialogStates.waiting_for_qwen_dialog))
