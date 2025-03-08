import psycopg2
from psycopg2.extras import Json
import json
from datetime import datetime
from typing import List, Optional
from src.models import User, DialogSession
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()

    def _connect(self) -> None:
        """Установка соединения с базой данных"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.cursor = self.conn.cursor()
            logger.info("Успешное подключение к базе данных")
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    def _create_tables(self) -> None:
        """Создание необходимых таблиц"""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS dialog_sessions (
                    chat_id BIGINT,
                    ai_name TEXT,
                    messages JSONB,
                    PRIMARY KEY (chat_id, ai_name)
                );
            """)
            self.conn.commit()
            logger.info("Таблицы успешно созданы")
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def save_user(self, user: User) -> None:
        """Сохранение информации о пользователе"""
        try:
            self.cursor.execute("""
                INSERT INTO users (chat_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id) 
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity = CURRENT_TIMESTAMP;
            """, (user.chat_id, user.username, user.first_name, user.last_name))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")
            self.conn.rollback()
            raise

    async def save_dialog_message(self, session: DialogSession) -> None:
        """Сохранение сообщения диалога"""
        try:
            self.cursor.execute("""
                INSERT INTO dialog_sessions (chat_id, ai_name, messages)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, ai_name) 
                DO UPDATE SET messages = %s;
            """, (
                session.chat_id,
                session.ai_name,
                Json(session.messages),
                Json(session.messages)
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения диалога: {e}")
            self.conn.rollback()
            raise

    async def get_all_users(self) -> List[int]:
        """Получение списка всех пользователей"""
        try:
            self.cursor.execute("SELECT chat_id FROM users")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            raise

    async def get_dialog_history(self, chat_id: int, ai_name: str) -> Optional[List]:
        """Получение истории диалога"""
        try:
            self.cursor.execute(
                "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
                (chat_id, ai_name)
            )
            result = self.cursor.fetchone()
            return json.loads(result[0]) if result else []
        except Exception as e:
            logger.error(f"Ошибка получения истории диалога: {e}")
            raise

    def close(self):
        """Закрытие соединения с БД"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
