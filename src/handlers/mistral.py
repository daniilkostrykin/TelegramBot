import logging
import os
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from mistralai import Mistral
import aiohttp
from src.formaters.format import safe_send_message
from src.models.dialog_state import DialogStates, dialog_manager
from src.database.db_manager import db_manager
from z.keyboards import get_ai_selection_keyboard, get_dialog_keyboard, get_mistral_model_keyboard
from src.models.user_state import user_state_manager
from dotenv import load_dotenv  # Добавляем импорт

logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Получаем API ключ и проверяем его наличие
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY не найден в переменных окружения")

# Инициализация Mistral AI клиента
mistral_client = Mistral(api_key=MISTRAL_API_KEY)

# Локальное хранилище диалогов
dialog_sessions = {}


async def save_user_state(state_or_chat_id, new_state: str):
    """Обертка для сохранения состояния пользователя"""
    await user_state_manager.save_user_state(state_or_chat_id, new_state)


async def handle_mistral_command(message: Message, state: FSMContext):
    """Запуск Mistral AI по команде /mistral"""
    chat_id = message.chat.id
    model_name = 'mistral-small-latest'
    await state.update_data(mistral_model=model_name)

    await message.answer(
        f"Вы выбрали Mistral AI (модель: {model_name}). Начните диалог:",
        reply_markup=get_dialog_keyboard()
    )
    await save_user_state(state, 'mistral_dialog')
    await state.set_state(DialogStates.waiting_for_mistral_dialog)


async def handle_mistral_dialog(message: Message, state: FSMContext):
    chat_id = message.chat.id

    if message.text == '⏹️ Завершить диалог':
        # Удаляем все диалоги пользователя из локального кэша
        keys_to_delete = [(cid, ai) for (cid, ai)
                          in dialog_sessions.keys() if cid == chat_id]
        for key in keys_to_delete:
            dialog_sessions.pop(key, None)

        await message.answer(
            "Диалог завершен.",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(state, 'ai_selection')
        await state.clear()  # Было finish(), заменено на clear()
        return

    elif message.text == '⬅️ Назад':
        # Удаляем все диалоги пользователя из локального кэша
        keys_to_delete = [(cid, ai) for (cid, ai)
                          in dialog_sessions.keys() if cid == chat_id]
        for key in keys_to_delete:
            dialog_sessions.pop(key, None)

        await message.answer(
            "Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(state, 'ai_selection')
        await state.clear()  # Было finish(), заменено на clear()
        return

    try:
        # Получаем выбранную модель из состояния
        data = await state.get_data()
        # По умолчанию используем mistral-small-latest
        model_name = data.get('mistral_model', 'mistral-small-latest')

        # Сохраняем сообщение пользователя
        await db_manager.save_dialog_message(chat_id, "mistral", "user", message.text)
        sent_message = await message.answer("Генерация ответа...")

        # Получаем историю диалога из локального кэша
        messages = dialog_sessions.get((chat_id, "mistral"), [])
        print(
            f"[LOG] Загруженная история диалога для {chat_id}: {messages}")

        # Добавляем текущее сообщение пользователя
        messages.append({
            "role": "user",
            "content": message.text
        })
        dialog_sessions[(chat_id, "mistral")] = messages

        # Преобразуем сообщения в формат Mistral
        mistral_messages = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and ("parts" in msg or "content" in msg):
                content = msg.get("parts", [None])[
                    0] if "parts" in msg else msg.get("content")
                if content:
                    mistral_messages.append({
                        "role": msg["role"],
                        "content": content
                    })

        # Если история пуста, добавляем хотя бы текущее сообщение
        if not mistral_messages:
            mistral_messages.append({
                "role": "user",
                "content": message.text
            })

        # Запрос к Mistral AI с выбранной моделью
        chat_response = mistral_client.chat.complete(
            model=model_name,
            messages=mistral_messages
        )

        response_text = chat_response.choices[0].message.content

        # Сохраняем ответ модели
        await db_manager.save_dialog_message(chat_id, "mistral", "assistant", response_text)

        # Сохраняем ответ в локальный кэш
        messages.append({
            "role": "assistant",
            "content": response_text
        })
        dialog_sessions[(chat_id, "mistral")] = messages

        # Отправляем ответ
        await sent_message.delete()
        await safe_send_message(message, response_text)

    except Exception as e:
        logger.error(f"Ошибка Mistral API: {e}")
        await message.answer(f"Произошла ошибка при генерации ответа: {str(e)}. Попробуйте позже.")


async def get_mistral_models(message: Message):
    """Получение списка доступных моделей Mistral AI"""
    try:
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.mistral.ai/v1/models", headers=headers) as response:
                if response.status == 200:
                    models_data = await response.json()

                    if "data" in models_data and models_data["data"]:
                        models_text = "Доступные модели Mistral AI:\n\n"
                        for model in models_data["data"]:
                            models_text += f"• {model['id']}"
                            if "description" in model:
                                models_text += f" - {model['description']}"
                            models_text += "\n"
                    else:
                        models_text = "Нет доступных моделей."
                else:
                    models_text = f"Ошибка при получении списка моделей. Код ответа: {response.status}"

                await message.answer(models_text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка моделей Mistral: {e}")
        await message.answer("Произошла ошибка при получении списка моделей. Попробуйте позже.")


async def handle_mistral_model_selection(message: Message, state: FSMContext):
    """Обработчик выбора модели Mistral AI"""
    chat_id = message.chat.id

    if message.text == '⬅️ Назад':
        await message.answer(
            "Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        await save_user_state(state, 'ai_selection')
        await state.clear()
        return

    model_mapping = {
        'Ministral 8b': 'ministral-8b-latest',
        'Mistral Medium': 'mistral-medium-latest',
        'Pixtral Large': 'pixtral-large-latest',
        'Codestral': 'codestral-latest',
        'Codestral Mamba': 'codestral-mamba-latest',
        'Pixtral 12b': 'pixtral-12b-latest',
        'Mistral Small': 'mistral-small-latest',
        'Mistral Saba': 'mistral-saba-latest',
        'Mistral Moderation': 'mistral-moderation-latest'
    }

    model_name = model_mapping.get(message.text)
    if not model_name:
        await message.answer("Пожалуйста, выберите модель из предложенных вариантов.")
        return

    await state.update_data(mistral_model=model_name)
    await message.answer(
        f"Вы выбрали модель {message.text}. Начните диалог:",
        reply_markup=get_dialog_keyboard()
    )
    await save_user_state(state, 'mistral_dialog')
    await state.set_state(DialogStates.waiting_for_mistral_dialog)


def register_mistral_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для Mistral"""
    dp.message.register(handle_mistral_command, Command('mistral'))
    dp.message.register(get_mistral_models, Command('get_mistral_models'))
    dp.message.register(handle_mistral_model_selection, StateFilter(
        DialogStates.waiting_for_mistral_model))
    dp.message.register(handle_mistral_dialog, StateFilter(
        DialogStates.waiting_for_mistral_dialog))
