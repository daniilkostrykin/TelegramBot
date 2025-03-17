import os
import json
import requests
from dotenv import load_dotenv
from aiogram import types
from aiogram.fsm.context import FSMContext
from src.keyboard.keyboards import get_dialog_keyboard, get_ai_selection_keyboard
from src.states.dialog_state import DialogStates
from src.states.user_state import user_state_manager
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.enums import ParseMode
from src.database.db_manager import db_manager
from src.formaters.format import safe_send_message
from src.handlers.ai_io_get_models import get_models_by_category

# Загрузка переменных окружения
load_dotenv()
AI_IO_API_KEY = os.getenv("AI_IO_API_KEY")

# Получаем список моделей DeepSeek
models_cache = get_models_by_category()
DEEPSEEK_MODELS = models_cache.get('deepseek', [])
DEFAULT_MODEL = DEEPSEEK_MODELS[0] if DEEPSEEK_MODELS else "deepseek-coder-33b-instruct"


def process_content(content):
    """Очищает контент от специальных тегов и разметки"""
    if not content:
        return "Извините, произошла ошибка при генерации ответа."
    content = content.replace('<think>', '').replace('</think>', '')
    content = content.replace('\\boxed{', '').replace('}', '')
    content = content.replace('```text', '').replace('```', '')
    return content.strip()


async def deepseek_request(messages):
    url = "https://api.intelligence.io.solutions/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_IO_API_KEY}"
    }

    data = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()

        if 'error' in response_data:
            return f"Ошибка API: {response_data['error']}"

        if 'choices' not in response_data or not response_data['choices']:
            return "Извините, не удалось получить ответ от нейросети. Попробуйте позже."

        content = response_data['choices'][0]['message']['content']
        return process_content(content)

    except requests.exceptions.RequestException as e:
        return f"Ошибка при обращении к API: {str(e)}"
    except Exception as e:
        return f"Непредвиденная ошибка: {str(e)}"


async def handle_deepseek_dialog(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    if message.text == '⏹️ Завершить диалог' or message.text == '⬅️ Назад':
        await message.answer(
            "Диалог завершен. Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        await user_state_manager.save_user_state(chat_id, 'ai_selection')
        await state.clear()
        return

    # Получаем историю диалога
    data = await state.get_data()
    messages = data.get("messages", [])

    # Добавляем системный промпт, если это начало диалога
    if not messages:
        messages.append({
            "role": "system",
            "content": "Ты - полезный ассистент, который всегда отвечает на русском языке. Ты должен быть дружелюбным и помогать пользователю."
        })

    user_message = message.text
    print(f"[DEBUG] Получено сообщение от пользователя: {user_message}")

    # Добавляем сообщение пользователя
    messages.append({
        "role": "user",
        "content": user_message
    })

    print(f"[DEBUG] История сообщений перед отправкой: {messages}")

    # Отправляем индикатор набора текста
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Отправляем промежуточное сообщение
    generating_message = await message.answer("Генерация ответа...")

    # Получаем ответ от DeepSeek
    response = await deepseek_request(messages)
    print(f"[DEBUG] Получен ответ от DeepSeek: {response}")

    # Добавляем ответ ассистента в историю
    messages.append({
        "role": "assistant",
        "content": response
    })

    # Сохраняем обновленную историю
    await state.update_data(messages=messages)

    # Сохраняем диалог в базу данных через существующий менеджер
    await db_manager.save_dialog_message(
        chat_id,
        "deepseek",
        "user",
        user_message
    )
    await db_manager.save_dialog_message(
        chat_id,
        "deepseek",
        "model",
        response
    )

    # Удаляем промежуточное сообщение
    if generating_message:
        await generating_message.delete()

    # Отправляем ответ пользователю с помощью safe_send_message
    await safe_send_message(message, response)

    # Ограничиваем историю диалога
    if len(messages) > 11:  # 1 системный промпт + 10 сообщений
        messages = [messages[0]] + messages[-10:]
        await state.update_data(messages=messages)


def register_deepseek_handlers(dp):
    """
    Регистрация всех обработчиков DeepSeek
    """
    # Обработчик команды /deepseek
    #dp.message.register(handle_deepseek_model_selection,Command("deepseek"))

    # Обработчик выбора через кнопку
    dp.message.register(
        handle_deepseek_model_selection,
        lambda message: message.text == "DeepSeek"
    )

    # Обработчик диалога
    dp.message.register(
        handle_deepseek_dialog,
        StateFilter(DialogStates.deepseek_dialog),
        lambda message: message.text != "⬅️ Назад"
    )


async def handle_deepseek_model_selection(message: types.Message, state: FSMContext):
    """
    Обработчик выбора модели DeepSeek
    """
    # Форматируем текст сообщения
    formatted_text = f"🤖 DeepSeek AI\n\n" + \
        f"Модель: {DEFAULT_MODEL}\n" + \
        "Отправьте ваше сообщение:"

    # Отправляем сообщение с клавиатурой
    await message.answer(
        formatted_text,
        reply_markup=get_dialog_keyboard()
    )
    await state.set_state(DialogStates.deepseek_dialog)
    await user_state_manager.save_user_state(message.chat.id, 'deepseek_dialog')
