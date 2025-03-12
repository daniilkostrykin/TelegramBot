import os
import json
import requests
from dotenv import load_dotenv
from aiogram import types
from aiogram.fsm.context import FSMContext
from src.states.dialog_state import DialogStates
from src.states.user_state import user_state_manager
from aiogram.filters import Command, CommandStart, StateFilter

# Загрузка переменных окружения
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = "deepseek/deepseek-r1"


def process_content(content):
    return content.replace('<think>', '').replace('</think>', '')


async def deepseek_request(messages):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code != 200:
            error_data = response.json()
            error_message = f"Ошибка API DeepSeek (код {response.status_code}): {error_data.get('error', {}).get('message', 'Неизвестная ошибка')}"
            print(f"Детали ошибки: {error_data}")  # Для отладки
            return error_message

        try:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except KeyError as e:
            return f"Ошибка в структуре ответа API: {str(e)}"

    except requests.exceptions.RequestException as e:
        return f"Ошибка сети при обращении к API: {str(e)}"
    except json.JSONDecodeError as e:
        return f"Ошибка при разборе JSON ответа: {str(e)}"
    except Exception as e:
        return f"Непредвиденная ошибка: {str(e)}"


def register_deepseek_handlers(dp):
    @dp.message(lambda message: message.text == "DeepSeek")
    async def handle_deepseek_choice(message: types.Message, state: FSMContext):
        await message.answer(
            "Вы выбрали DeepSeek AI. Отправьте ваше сообщение:",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(DialogStates.deepseek_dialog)
        await user_state_manager.save_user_state(message.chat.id, 'deepseek_dialog')

    @dp.message(lambda message: message.text != "⬅️ Назад", StateFilter(DialogStates.deepseek_dialog))
    async def handle_deepseek_message(message: types.Message, state: FSMContext):
        # Получаем историю диалога
        data = await state.get_data()
        messages = data.get("messages", [])

        # Добавляем системный промпт, если это начало диалога
        if not messages:
            messages.append({
                "role": "system",
                "content": "Ты - полезный ассистент, который всегда отвечает на русском языке. Ты должен быть дружелюбным и помогать пользователю."
            })

        # Добавляем сообщение пользователя
        messages.append({
            "role": "user",
            "content": message.text
        })

        # Отправляем индикатор набора текста
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Получаем ответ от DeepSeek
        response = await deepseek_request(messages)

        # Добавляем ответ ассистента в историю
        messages.append({
            "role": "assistant",
            "content": response
        })

        # Сохраняем обновленную историю
        await state.update_data(messages=messages)

        # Отправляем ответ пользователю
        await message.answer(response)

        # Ограничиваем историю диалога
        if len(messages) > 11:  # 1 системный промпт + 10 сообщений
            messages = [messages[0]] + messages[-10:]
            await state.update_data(messages=messages)
