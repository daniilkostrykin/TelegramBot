"""
Модуль user_state содержит фильтры и классы для работы с состояниями пользователей.
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message


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
