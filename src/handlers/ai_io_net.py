import logging
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import requests

from src.states.dialog_state import DialogStates
from src.keyboard.keyboards import get_ai_io_net_keyboard, get_ai_io_net_model_keyboard, get_ai_selection_keyboard
from src.handlers.ai_io_get_models import get_models_by_category
from src.formaters.format import safe_send_message

from dotenv import load_dotenv
import os

load_dotenv()
AI_IO_API_KEY = os.getenv("AI_IO_API_KEY")

# Глобальная переменная для хранения моделей
models_cache = {}


def register_ai_io_net_handlers(dp: Dispatcher):

    @dp.message(F.text == "AI.IO.NET")
    async def start_ai_io_net(message: Message, state: FSMContext):
        await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())
        await state.set_state(DialogStates.ai_io_net_category)

    @dp.message(DialogStates.ai_io_net_category)
    async def handle_category_selection(message: Message, state: FSMContext):
        global models_cache

        if message.text == "⬅️ Назад":
            await state.clear()
            await message.answer("Выберите AI:", reply_markup=get_ai_selection_keyboard())
            return

        # Обработка выбора категории
        if message.text in ["DeepSeek модели", "Qwen модели", "Mistral модели", "LLaMA модели", "Другие модели"]:
            if not models_cache:
                models_cache = get_models_by_category()

            category_map = {
                "DeepSeek модели": "deepseek",
                "Qwen модели": "qwen",
                "Mistral модели": "mistral",
                "LLaMA модели": "llama",
                "Другие модели": "other"
            }

            category = category_map[message.text]
            models = models_cache.get(category, [])

            if not models:
                await message.answer("В данной категории нет доступных моделей.", reply_markup=get_ai_io_net_keyboard())
                return

            await state.update_data(selected_category=category)
            await message.answer(
                f"Выберите модель из категории {message.text}:",
                reply_markup=get_ai_io_net_model_keyboard(models)
            )
            await state.set_state(DialogStates.ai_io_net_chat)
            return

    @dp.message(DialogStates.ai_io_net_chat)
    async def handle_chat(message: Message, state: FSMContext):
        if message.text == "⬅️ Назад":
            await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())
            await state.set_state(DialogStates.ai_io_net_category)
            return

        # Проверяем, является ли сообщение выбором модели
        selected_model = None
        for category_models in models_cache.values():
            if message.text in category_models:
                selected_model = message.text
                await state.update_data(selected_model=selected_model)
                await message.answer(f"Модель {selected_model} выбрана. Отправьте ваше сообщение.")
                return

        # Если это не выбор модели, обрабатываем как запрос к API
        data = await state.get_data()
        selected_model = data.get('selected_model')

        if not selected_model:
            selected_model = list(models_cache['mistral'])[
                0] if models_cache.get('mistral') else None

        if not selected_model:
            await message.answer(
                "Не удалось найти доступную модель. Пожалуйста, выберите модель из списка.",
                reply_markup=get_ai_io_net_keyboard()
            )
            await state.set_state(DialogStates.ai_io_net_category)
            return

        url = "https://api.intelligence.io.solutions/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_IO_API_KEY}",
        }

        data = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": message.text
                }
            ],
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            if 'error' in response_data:
                await message.answer(f"Произошла ошибка при обращении к API: {response_data['error']}")
                return

            if 'choices' not in response_data or not response_data['choices']:
                await message.answer("Извините, не удалось получить ответ от нейросети. Попробуйте позже.")
                return

            text = response_data['choices'][0]['message']['content']
            if '</think>' in text:
                bot_text = text.split('</think>\n\n')[1]
            else:
                bot_text = text

            await safe_send_message(message, bot_text)

        except requests.exceptions.RequestException as e:
            await message.answer(f"Ошибка при обращении к API: {str(e)}")
            logging.error(f"API request error: {str(e)}")
        except Exception as e:
            await message.answer("Произошла внутренняя ошибка. Попробуйте позже.")
            logging.error(f"Internal error: {str(e)}")

    return dp
