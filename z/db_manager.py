import os
import psycopg2
import logging
from typing import List, Tuple, Optional, Any
import json
import traceback

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        """Устанавливает соединение с базой данных"""
        DATABASE_URL = os.environ.get("DB_URL")
        RAILWAY_DB_URL = "postgresql://postgres:tocutLkkpvyyDLmYnEPZrrovLcTbjFvA@postgres.railway.internal:5432/railway"
        LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:5433/postgres"

        try:
            if DATABASE_URL:
                print(f"Попытка подключения к удаленной базе: {DATABASE_URL}")
                self.conn = psycopg2.connect(DATABASE_URL)
            else:
                raise psycopg2.OperationalError(
                    "Переменная окружения DB_URL не задана, пробуем Railway...")

        except psycopg2.Error as e:
            print(
                f"Ошибка при подключении к {DATABASE_URL}: {e}. Пробуем Railway...")

            try:
                self.conn = psycopg2.connect(RAILWAY_DB_URL)
                print("Успешно подключено к Railway!")
            except psycopg2.Error as e:
                print(
                    f"Ошибка при подключении к Railway: {e}. Пробуем локальную базу...")

                try:
                    self.conn = psycopg2.connect(LOCAL_DB_URL)
                    print("Переключено на локальную базу данных!")
                except psycopg2.Error as e:
                    print(
                        f"Ошибка при подключении к локальной базе данных: {e}. Программа завершена.")
                    raise

        self.cursor = self.conn.cursor()
        print("Подключение успешно!")

    async def save_user(self, chat_id: int, username: str, first_name: str, last_name: str) -> None:
        """Сохраняет или обновляет информацию о пользователе"""
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
            """, (chat_id, username, first_name, last_name))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя: {e}")
            raise

    async def get_all_users(self) -> List[int]:
        """Получает список всех chat_id пользователей"""
        try:
            # Сначала пробуем получить пользователей из таблицы users
            self.cursor.execute("SELECT chat_id FROM users")
            users = self.cursor.fetchall()

            if not users:
                # Если таблица users пуста, получаем пользователей из dialog_sessions
                self.cursor.execute(
                    "SELECT DISTINCT chat_id FROM dialog_sessions")
                users = self.cursor.fetchall()

            return [user[0] for user in users]
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []

    async def save_dialog_message(self, chat_id: int, ai_name: str, role: str, content: str) -> None:
        """
        Сохраняет сообщение в диалог пользователя в БД.

        Args:
            chat_id: ID чата пользователя
            ai_name: Название AI модели
            role: Роль отправителя (user/model)
            content: Содержание сообщения
        """
        try:
            # Получаем текущую историю
            self.cursor.execute(
                "SELECT messages FROM dialog_sessions WHERE chat_id = %s AND ai_name = %s",
                (chat_id, ai_name)
            )
            result = self.cursor.fetchone()

            # Загружаем существующие сообщения
            old_messages = []
            if result and result[0]:
                if isinstance(result[0], list):
                    old_messages = result[0]
                elif isinstance(result[0], str):
                    try:
                        old_messages = json.loads(result[0])
                    except json.JSONDecodeError:
                        print("[ERROR] JSONDecodeError! Используем пустой список.")
                        old_messages = []

            # Объединяем старые и новые сообщения
            new_messages = old_messages + [{"role": role, "parts": [content]}]

            # Сохраняем обновленную историю
            self.cursor.execute("""
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
            self.conn.commit()
            print("[LOG] Сообщение успешно сохранено в БД.")

        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения диалога: {e}")
            print(traceback.format_exc())
            raise

    async def get_dialog_history(self, chat_id: int, ai_name: str) -> List[dict]:
        """Получает историю диалога для конкретного пользователя и AI"""
        try:
            self.cursor.execute("""
                SELECT role, content
                FROM dialog_sessions
                WHERE chat_id = %s AND ai_name = %s
                ORDER BY timestamp ASC
            """, (chat_id, ai_name))

            messages = []
            for role, content in self.cursor.fetchall():
                if role == "user":
                    messages.append({"role": role, "parts": [content]})
                else:
                    messages.append({"role": role, "parts": [content]})

            return messages
        except Exception as e:
            logger.error(f"Ошибка при получении истории диалога: {e}")
            return []

    def close(self):
        """Закрывает соединение с базой данных"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


# Создаем глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager()
