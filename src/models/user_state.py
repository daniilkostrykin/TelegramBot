"""
Модуль user_state содержит фильтры и классы для работы с состояниями пользователей.
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Dict, List, Optional
from aiogram.fsm.context import FSMContext
import logging

logger = logging.getLogger(__name__)


class UserStateFilter(BaseFilter):
    """Фильтр для проверки состояния пользователя."""

    def __init__(self, state_name: str):
        """
        Инициализация фильтра.

        Args:
            state_name (str): Название состояния для проверки
        """
        self.state_name = state_name

    async def __call__(self, message: Message) -> bool:
        """
        Проверяет, соответствует ли текущее состояние пользователя заданному.

        Args:
            message (Message): Сообщение от пользователя

        Returns:
            bool: True если состояние соответствует, False в противном случае
        """
        from z.bot_handlers import user_states  # Импортируем здесь во избежание циклических импортов
        return user_states.get(message.chat.id) == self.state_name


class UserStateManager:
    """Менеджер для управления состояниями пользователей"""

    def __init__(self):
        self.user_states: Dict[int, str] = {}

    async def save_user_state(self, state_or_chat_id, new_state: str):
        """
        Сохраняет текущее состояние пользователя.
        Args:
            state_or_chat_id: FSMContext объект или chat_id пользователя
            new_state: Новое состояние для сохранения
        """
        if isinstance(state_or_chat_id, int):
            # Если передан chat_id, просто сохраняем состояние в словарь
            self.user_states[state_or_chat_id] = new_state
            logger.debug(
                f"Сохранено состояние {new_state} для пользователя {state_or_chat_id}")
        else:
            # Если передан FSMContext, сохраняем в FSM
            state = state_or_chat_id
            data = await state.get_data()
            if 'states_history' not in data:
                data['states_history'] = []
            data['states_history'].append(new_state)
            data['current_state'] = new_state
            await state.update_data(data)

            # Также сохраняем в словарь для совместимости
            try:
                chat_id = state.key.chat_id
                self.user_states[chat_id] = new_state
                logger.debug(
                    f"Сохранено состояние {new_state} для пользователя {chat_id} в FSM")
            except Exception as e:
                logger.error(f"Ошибка при сохранении состояния в FSM: {e}")

    async def get_user_state(self, chat_id: int) -> Optional[str]:
        """Получает текущее состояние пользователя"""
        return self.user_states.get(chat_id)

    async def get_previous_user_state(self, state: FSMContext) -> Optional[str]:
        """
        Возвращает предыдущее состояние пользователя из FSM.
        Args:
            state: FSMContext объект для работы с состоянием
        Returns:
            str | None: Предыдущее состояние или None если истории нет
        """
        data = await state.get_data()
        if 'states_history' in data and len(data['states_history']) > 1:
            data['states_history'].pop()  # Убираем текущее состояние
            previous_state = data['states_history'][-1]  # Берем предыдущее
            data['current_state'] = previous_state
            await state.update_data(data)
            return previous_state
        return None

    def clear_user_state(self, chat_id: int):
        """Очищает состояние пользователя"""
        self.user_states.pop(chat_id, None)

    def get_all_user_states(self) -> Dict[int, str]:
        """Возвращает состояния всех пользователей"""
        return self.user_states.copy()


# Создаем глобальный экземпляр менеджера состояний пользователей
user_state_manager = UserStateManager()
