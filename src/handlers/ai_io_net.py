import logging
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import requests

from src.states.dialog_state import DialogStates
from src.keyboard.keyboards import get_ai_io_net_keyboard, get_ai_io_net_model_keyboard, get_ai_selection_keyboard, get_dialog_keyboard
from src.handlers.ai_io_get_models import get_models_by_category
from src.formaters.format import safe_send_message_with_keyboard
from src.database.db_manager import db_manager

from dotenv import load_dotenv
import os

load_dotenv()
AI_IO_API_KEY = os.getenv("AI_IO_API_KEY")

# Глобальная переменная для хранения моделей
models_cache = {}

# Кэш для хранения рассуждений
thinking_cache = {}


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
        chat_id = message.chat.id

        if message.text == "⬅️ Назад":
            await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())
            await state.set_state(DialogStates.ai_io_net_category)
            return

        if message.text == "⏹️ Завершить диалог":
            await message.answer("Выберите категорию моделей:", reply_markup=get_ai_io_net_keyboard())
            await state.set_state(DialogStates.ai_io_net_category)
            return

        # Проверяем, является ли сообщение выбором модели
        selected_model = None
        for category_models in models_cache.values():
            if message.text in category_models:
                selected_model = message.text
                await state.update_data(selected_model=selected_model)
                await message.answer(
                    f"Модель {selected_model} выбрана. Отправьте ваше сообщение.",
                    reply_markup=get_dialog_keyboard()
                )
                # Сохраняем начало диалога в БД
                await db_manager.save_dialog_message(chat_id, selected_model, "system", f"Диалог начат с моделью {selected_model}")
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

        # Сохраняем сообщение пользователя в БД
        await db_manager.save_dialog_message(chat_id, selected_model, "user", message.text)

        # Отправляем сообщение о генерации
        loading_message = await message.answer("Генерация ответа...")

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

            await loading_message.delete()

            if 'error' in response_data:
                error_message = f"Произошла ошибка при обращении к API: {response_data['error']}"
                await message.answer(error_message)
                await db_manager.save_dialog_message(chat_id, selected_model, "error", error_message)
                return

            if 'choices' not in response_data or not response_data['choices']:
                error_message = "Извините, не удалось получить ответ от нейросети. Попробуйте позже."
                await message.answer(error_message)
                await db_manager.save_dialog_message(chat_id, selected_model, "error", error_message)
                return

            text = response_data['choices'][0]['message']['content']
            logging.info("\n" + "="*50 + "\nИсходный ответ нейронки:\n" +
                         "="*50 + f"\n{text}\n" + "="*50)
            bot_text, thoughts = process_ai_response(text)
            logging.info("\nПосле обработки:" +
                         "\n---Текст---\n" + bot_text +
                         "\n---Рассуждения---\n" + (thoughts if thoughts else "Нет рассуждений") +
                         "\n" + "="*50)

            # Создаем клавиатуру, если есть рассуждения
            reply_markup = None
            if thoughts:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Показать рассуждения",
                            callback_data=f"show_thinking_{message.message_id}"
                        )
                    ]]
                )
                reply_markup = keyboard

            # Сохраняем ответ модели в БД
            await db_manager.save_dialog_message(chat_id, selected_model, "assistant", bot_text)
            sent_message = await safe_send_message_with_keyboard(message, bot_text, reply_markup=reply_markup)

            # Сохраняем рассуждения в кэш, если они есть
            if thoughts and sent_message:
                cache_key = f"{message.message_id}_{sent_message.message_id}"
                thinking_cache[cache_key] = thoughts

        except requests.exceptions.RequestException as e:
            error_message = f"Ошибка при обращении к API: {str(e)}"
            await loading_message.delete()
            await message.answer(error_message)
            await db_manager.save_dialog_message(chat_id, selected_model, "error", error_message)
            logging.error(f"API request error: {str(e)}")
        except Exception as e:
            error_message = "Произошла внутренняя ошибка. Попробуйте позже."
            await loading_message.delete()
            await message.answer(error_message)
            await db_manager.save_dialog_message(chat_id, selected_model, "error", error_message)
            logging.error(f"Internal error: {str(e)}")

    @dp.message(F.text.startswith("/deepseek"))
    async def handle_deepseek_command(message: Message, state: FSMContext):
        global models_cache

        if not models_cache:
            models_cache = get_models_by_category()

        deepseek_models = models_cache.get("deepseek", [])
        if not deepseek_models:
            await message.answer("К сожалению, модели DeepSeek сейчас недоступны.")
            return

        # Выбираем первую доступную модель DeepSeek
        selected_model = list(deepseek_models)[0]
        await state.update_data(selected_model=selected_model)

        # Получаем текст запроса после команды
        user_text = message.text.replace("/deepseek", "").strip()

        if not user_text:
            await message.answer(
                f"Модель {selected_model} выбрана. Отправьте ваше сообщение.",
                reply_markup=get_dialog_keyboard()
            )
            await state.set_state(DialogStates.ai_io_net_chat)
            # Сохраняем начало диалога в БД
            await db_manager.save_dialog_message(message.chat.id, selected_model, "system", f"Диалог начат с моделью {selected_model}")
            return

        # Если текст есть, сразу отправляем запрос к API
        await state.set_state(DialogStates.ai_io_net_chat)
        loading_message = await message.answer("Генерация ответа...")

        try:
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
                        "content": user_text
                    }
                ],
            }

            # Сохраняем сообщение пользователя в БД
            await db_manager.save_dialog_message(message.chat.id, selected_model, "user", user_text)

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            await loading_message.delete()

            if 'choices' in response_data and response_data['choices']:
                text = response_data['choices'][0]['message']['content']
                logging.info(
                    "\n" + "="*50 + "\nИсходный ответ нейронки:\n" + "="*50 + f"\n{text}\n" + "="*50)
                bot_text, thoughts = process_ai_response(text)
                logging.info("\nПосле обработки:" +
                             "\n---Текст---\n" + bot_text +
                             "\n---Рассуждения---\n" + (thoughts if thoughts else "Нет рассуждений") +
                             "\n" + "="*50)

                # Создаем клавиатуру, если есть рассуждения
                reply_markup = None
                if thoughts:
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(
                                text="Показать рассуждения",
                                callback_data=f"show_thinking_{message.message_id}"
                            )
                        ]]
                    )
                    reply_markup = keyboard

                # Сохраняем ответ модели в БД
                await db_manager.save_dialog_message(message.chat.id, selected_model, "assistant", bot_text)
                sent_message = await safe_send_message_with_keyboard(message, bot_text, reply_markup=reply_markup)

                # Сохраняем рассуждения в кэш, если они есть
                if thoughts and sent_message:
                    cache_key = f"{message.message_id}_{sent_message.message_id}"
                    thinking_cache[cache_key] = thoughts
            else:
                error_message = "Извините, не удалось получить ответ от нейросети. Попробуйте позже."
                await message.answer(error_message)
                await db_manager.save_dialog_message(message.chat.id, selected_model, "error", error_message)

        except Exception as e:
            error_message = "Произошла ошибка при обработке запроса. Попробуйте позже."
            await loading_message.delete()
            await message.answer(error_message)
            await db_manager.save_dialog_message(message.chat.id, selected_model, "error", str(e))
            logging.error(f"DeepSeek error: {str(e)}")

    @dp.callback_query(lambda c: c.data.startswith('show_thinking_'))
    async def process_thinking_callback(callback_query: CallbackQuery):
        message_id = callback_query.data.split('_')[2]
        cache_key = f"{message_id}_{callback_query.message.message_id}"

        thinking_text = thinking_cache.get(cache_key)

        if thinking_text:
            await callback_query.message.answer(
                f"💭 Рассуждения:\n\n{thinking_text}",
                reply_to_message_id=callback_query.message.message_id
            )
            await callback_query.answer()
        else:
            await callback_query.answer("Рассуждения не найдены или истекли", show_alert=True)

    return dp


def process_ai_response(text: str) -> tuple[str, str]:
    """
    Обрабатывает ответ AI, разделяя рассуждения и финальный ответ
    Returns: (response, thoughts)
    """
    if '<think>' in text and '</think>' in text:
        try:
            thoughts = text[text.find('<think>') +
                            7:text.find('</think>')].strip()
            response = text[text.find('</think>') + 8:].strip()
            return response, thoughts
        except Exception:
            return text, ""
    return text, ""
