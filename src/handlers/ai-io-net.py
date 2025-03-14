from keyboard.keyboards import get_ai_io_net_keyboard, get_ai_io_net_model_keyboard
from handlers.ai_io_get_models import get_models_by_category
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.methods import DeleteWebhook
from aiogram.types import Message
import requests
from dotenv import load_dotenv
import os
import sys
import os.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_IO_API_KEY = os.getenv("AI_IO_API_KEY")

# Глобальная переменная для хранения моделей
models_cache = {}


@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())


@dp.message()
async def handle_messages(message: Message):
    global models_cache

    if message.text == "⬅️ Назад":
        await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())
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

        await message.answer(
            f"Выберите модель из категории {message.text}:",
            reply_markup=get_ai_io_net_model_keyboard(models)
        )
        return

    # Обработка запроса к модели
    url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_IO_API_KEY}",
    }

    # Проверяем, является ли сообщение выбором модели
    selected_model = None
    for category_models in models_cache.values():
        if message.text in category_models:
            selected_model = message.text
            break

    if not selected_model:
        selected_model = list(models_cache['mistral'])[
            0] if models_cache.get('mistral') else None

    if not selected_model:
        await message.answer("Не удалось найти доступную модель. Пожалуйста, выберите модель из списка.",
                             reply_markup=get_ai_io_net_keyboard())
        return

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
        data = response.json()

        if 'error' in data:
            await message.answer(f"Произошла ошибка при обращении к API: {data['error']}")
            return

        if 'choices' not in data or not data['choices']:
            await message.answer("Извините, не удалось получить ответ от нейросети. Попробуйте позже.")
            return

        text = data['choices'][0]['message']['content']
        if '</think>' in text:
            bot_text = text.split('</think>\n\n')[1]
        else:
            bot_text = text

        await message.answer(bot_text, parse_mode="Markdown")

    except requests.exceptions.RequestException as e:
        await message.answer(f"Ошибка при обращении к API: {str(e)}")
        logging.error(f"API request error: {str(e)}")
    except Exception as e:
        await message.answer("Произошла внутренняя ошибка. Попробуйте позже.")
        logging.error(f"Internal error: {str(e)}")


async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
