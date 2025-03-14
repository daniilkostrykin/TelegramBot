"""
Модуль dialog_state содержит классы состояний для диалогов с различными AI моделями.
"""

from aiogram.fsm.state import State, StatesGroup
from typing import Optional, Dict, List
import json
import logging

logger = logging.getLogger(__name__)


class DialogStates(StatesGroup):
    """Группа состояний для диалогов с различными AI моделями"""
    waiting_for_dialog = State()
    waiting_for_g4f_dialog = State()
    waiting_for_g4f_model = State()
    waiting_for_model_selection = State()
    waiting_for_mistral_model = State()
    waiting_for_mistral_dialog = State()
    waiting_for_qwen_dialog = State()
    waiting_for_text_image = State()
    waiting_for_text_voice = State()
    waiting_for_nocode = State()
    waiting_for_appearance = State()
    waiting_for_photo = State()
    waiting_for_midjourney = State()
    deepseek_dialog = State()
    # Новые состояния для ai-io-net
    ai_io_net_category = State()
    ai_io_net_chat = State()


class DialogSessionManager:
    """Менеджер для управления сессиями диалогов"""

    def __init__(self):
        self.dialog_sessions: Dict[tuple, List[dict]] = {}
        self.g4f_dialog_sessions: Dict[int, List[dict]] = {}
        self.active_generations: Dict[int, bool] = {}

    async def save_dialog_message(self, chat_id: int, ai_name: str, role: str, content: str, cursor=None, conn=None):
        """Сохраняет сообщение в диалог пользователя (в БД и в память)"""
        key = (chat_id, ai_name)

        # Сохраняем в память
        if key not in self.dialog_sessions:
            self.dialog_sessions[key] = []

        self.dialog_sessions[key].append({"role": role, "parts": [content]})

        # Сохраняем в БД, если предоставлено подключение
        if cursor and conn:
            try:
                cursor.execute(
                    "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
                    (chat_id, ai_name)
                )
                result = cursor.fetchone()

                old_messages = []
                if result and result[0]:
                    if isinstance(result[0], list):
                        old_messages = result[0]
                    elif isinstance(result[0], str):
                        try:
                            old_messages = json.loads(result[0])
                        except json.JSONDecodeError:
                            logger.error(
                                "JSONDecodeError при чтении старых сообщений")
                            old_messages = []

                new_messages = old_messages + \
                    [{"role": role, "parts": [content]}]

                cursor.execute("""
                    INSERT INTO dialog_sessions (chat_id, ai_name, messages)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chat_id, ai_name)
                    DO UPDATE SET messages = %s;
                """, (
                    chat_id,
                    ai_name,
                    json.dumps(new_messages, ensure_ascii=False),
                    json.dumps(new_messages, ensure_ascii=False)
                ))
                conn.commit()
                logger.info(
                    f"Сообщение сохранено в БД для чата {chat_id} и AI {ai_name}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении в БД: {e}")

    async def get_dialog_history(self, chat_id: int, ai_name: str, cursor=None) -> List[dict]:
        """Получает историю диалога из БД или памяти"""
        if cursor:
            cursor.execute(
                "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
                (chat_id, ai_name)
            )
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])

        # Если нет БД или записи не найдены, возвращаем из памяти
        return self.dialog_sessions.get((chat_id, ai_name), [])

    def clear_dialog_history(self, chat_id: int, ai_name: Optional[str] = None):
        """Очищает историю диалога для пользователя"""
        if ai_name:
            self.dialog_sessions.pop((chat_id, ai_name), None)
        else:
            # Очищаем все диалоги пользователя
            keys_to_delete = [(cid, ai) for (
                cid, ai) in self.dialog_sessions.keys() if cid == chat_id]
            for key in keys_to_delete:
                self.dialog_sessions.pop(key, None)
            self.g4f_dialog_sessions.pop(chat_id, None)

    def set_active_generation(self, chat_id: int, active: bool):
        """Устанавливает статус активной генерации для пользователя"""
        self.active_generations[chat_id] = active

    def is_generation_active(self, chat_id: int) -> bool:
        """Проверяет, активна ли генерация для пользователя"""
        return self.active_generations.get(chat_id, False)


# Создаем глобальный экземпляр менеджера диалогов
dialog_manager = DialogSessionManager()
