import logging
import asyncio
import re
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from g4f.client import Client
from src.formaters.format import safe_send_message
from src.states.dialog_state import DialogStates
from src.database.db_manager import db_manager
from src.keyboard.keyboards import get_ai_selection_keyboard, get_g4f_model_keyboard, get_dialog_keyboard, get_ai_selection_keyboard
from src.states.user_state import user_state_manager
from aiogram import Dispatcher, Bot, types, F
from asyncio import TimeoutError
logger = logging.getLogger(__name__)

# Локальное хранилище диалогов
g4f_dialog_sessions = {}


class ChatBotG4F:
    def __init__(self):
        self.client = Client()
        self.messages = []

    def set_model(self, model_name: str):
        """Устанавливает модель для G4F"""
        self.model_name = model_name

    async def ask(self, user_input: str) -> str:
        """Отправляет запрос в G4F и получает ответ"""
        self.messages.append({"role": "user", "content": user_input})

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=self.messages,
            )
            reply = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": reply})
            return reply
        except Exception as err:
            logger.error(f"Ошибка при запросе к {self.model_name}: {err}")
            return "Не удалось получить ответ."


# Создаем экземпляр бота для G4F
g4f_bot = ChatBotG4F()


async def save_user_state(state_or_chat_id, new_state: str):
    """Обертка для сохранения состояния пользователя"""
    await user_state_manager.save_user_state(state_or_chat_id, new_state)


async def handle_g4f_command(message: Message, state: FSMContext):
    # print(f"[DEBUG] handle_g4f_command: {message.text}")
    g4f_bot.set_model("gpt-4o-mini")
    await message.answer("Вы выбрали G4F. Введите ваш запрос:", reply_markup=get_dialog_keyboard())
    # await save_user_state(state, 'g4f_dialog')
    await state.set_state(DialogStates.waiting_for_g4f_dialog)

    # Логируем текущее состояние
    current_state = await state.get_state()
    print(f"[DEBUG] Текущее состояние: {current_state}")


async def handle_g4f_choice(message: Message, state: FSMContext):
    """Обработчик выбора G4F из меню AI"""
    logger.info("Вызван handle_g4f_choice")
    chat_id = message.chat.id

    if chat_id in g4f_dialog_sessions:
        g4f_dialog_sessions[chat_id] = []

    await message.answer(
        "Вы выбрали G4F. Выберите модель:",
        reply_markup=get_g4f_model_keyboard()
    )
    await state.set_state(DialogStates.waiting_for_g4f_model)


async def handle_g4f_model_selection(message: Message, state: FSMContext):
    """Обработчик выбора модели G4F"""
    logger.info(f"Выбор модели G4F: {message.text}")

    if message.text == '⬅️ Назад':
        await message.answer(
            "Возврат в меню выбора AI.",
            reply_markup=get_ai_selection_keyboard()
        )
        await state.clear()
        return

    model_mapping = {
        'GPT 4o mini': 'gpt-4o-mini',
    }

    model_name = model_mapping.get(message.text)

    if model_name:
        logger.info(f"Установка модели G4F: {model_name}")
        g4f_bot.set_model(model_name)
        await state.update_data(model=model_name)
        await message.answer(
            f"Вы выбрали {model_name}. Введите ваш запрос:",
            reply_markup=get_dialog_keyboard()
        )
        await state.set_state(DialogStates.waiting_for_g4f_dialog)
    else:
        await message.answer("Неверный выбор модели. Попробуйте снова.")


async def handle_g4f_dialog(message: Message, state: FSMContext):
    """Обработчик диалога с G4F"""
    logger.info("Вызван handle_g4f_dialog")
    chat_id = message.chat.id

    if message.text == '⏹️ Завершить диалог':
        await message.answer(
            "Диалог завершен.",
            reply_markup=get_ai_selection_keyboard()
        )
        if chat_id in g4f_dialog_sessions:
            del g4f_dialog_sessions[chat_id]
        await save_user_state(state, 'main_menu')
        await state.clear()
        return

    elif message.text == '⬅️ Назад':
        await message.answer(
            "Возврат в меню выбора G4F модели.",
            reply_markup=get_g4f_model_keyboard()
        )
        await save_user_state(state, 'g4f_model_selection')
        if chat_id in g4f_dialog_sessions:
            del g4f_dialog_sessions[chat_id]
        await state.clear()
        return

    try:
        logger.info(f"Отправка запроса к G4F: {message.text[:50]}...")
        loading_message = await message.answer("Генерация ответа...")

        try:
            # Устанавливаем таймаут в 60 секунд для запроса
            response = await asyncio.wait_for(
                g4f_bot.ask(message.text),
                timeout=60.0
            )

            # Сохраняем в БД
            await db_manager.save_dialog_message(chat_id, "g4f", "user", message.text)
            await db_manager.save_dialog_message(chat_id, "g4f", "assistant", response)

            logger.info(
                f"Получен ответ от G4F длиной {len(response)} символов")

            # Удаляем сообщение о генерации
            await loading_message.delete()

            # Отправляем ответ
            await safe_send_message(message, response)

        except TimeoutError:
            logger.error("Превышено время ожидания ответа от G4F")
            await loading_message.delete()
            await message.answer(
                "Извините, генерация ответа заняла слишком много времени. Попробуйте задать вопрос короче или перефразировать его.",
                reply_markup=get_dialog_keyboard()
            )

        except Exception as e:
            logger.error(f"Ошибка при получении ответа от G4F: {e}")
            await loading_message.delete()
            await message.answer(
                "Произошла ошибка при генерации ответа. Попробуйте еще раз.",
                reply_markup=get_dialog_keyboard()
            )

    except Exception as e:
        logger.error(f"Общая ошибка в обработчике G4F: {e}")
        try:
            await loading_message.delete()
        except:
            pass
        await message.answer(
            "Произошла ошибка. Попробуйте еще раз или выберите другую модель.",
            reply_markup=get_dialog_keyboard()
        )


def register_g4f_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для G4F"""
    logger.info("Регистрация обработчиков G4F")
    dp.message.register(handle_g4f_command, Command('g4f'))
    dp.message.register(handle_g4f_choice, F.text == "G4F (Аналог ChatGPT)")
    dp.message.register(
        handle_g4f_model_selection,
        StateFilter(DialogStates.waiting_for_g4f_model)
    )
    dp.message.register(
        handle_g4f_dialog,
        StateFilter(DialogStates.waiting_for_g4f_dialog)
    )
