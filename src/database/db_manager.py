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
        self.dialog_sessions = {}  # Локальный кэш для диалогов
        self.is_connected = False  # Флаг подключения к БД
        try:
            self._connect()
            self.is_connected = True
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS dialog_sessions (
                    chat_id BIGINT,
                    ai_name TEXT,
                    messages JSONB,
                    PRIMARY KEY (chat_id, ai_name)
                );
            """)
            # Создаем таблицу для хранения всех пользователей
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
            # Создаем таблицу для хранения всех пользователей
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Создаем таблицу только если есть подключение
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_messages (
                    chat_id BIGINT PRIMARY KEY,
                    message_id BIGINT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при инициализации БД: {e}")
            self.is_connected = False
            # Продолжаем работу без БД, используя только кэш

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
        if not self.is_connected:
            return

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
        Сохраняет сообщение в диалог пользователя (в БД и в память).

        Args:
            chat_id: ID чата пользователя
            ai_name: Название AI модели
            role: Роль отправителя (user/model)
            content: Содержание сообщения
        """
        print(
            f"[LOG] save_dialog_message вызван с: chat_id={chat_id}, ai_name={ai_name}, role={role}, content={content}"
        )

        # Сохраняем в локальный кэш всегда
        dialog_key = (chat_id, ai_name)
        if dialog_key not in self.dialog_sessions:
            self.dialog_sessions[dialog_key] = []

        self.dialog_sessions[dialog_key].append(
            {"role": role, "parts": [content]})

        # Сохраняем в БД только если есть подключение
        if not self.is_connected:
            return

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

    async def get_dialog_history(self, chat_id: int, ai_name: str) -> List[dict]:
        """
        Получает историю диалога для конкретного пользователя и AI.
        Сначала проверяет локальный кэш, затем БД.
        """
        dialog_key = (chat_id, ai_name)

        # Проверяем локальный кэш
        if dialog_key in self.dialog_sessions:
            return self.dialog_sessions[dialog_key]

        # Если в кэше нет, получаем из БД
        try:
            self.cursor.execute("""
                SELECT messages
                FROM dialog_sessions
                WHERE chat_id = %s AND ai_name = %s
            """, (chat_id, ai_name))

            result = self.cursor.fetchone()
            if result and result[0]:
                try:
                    messages = json.loads(result[0]) if isinstance(
                        result[0], str) else result[0]
                    # Сохраняем в кэш
                    self.dialog_sessions[dialog_key] = messages
                    return messages
                except json.JSONDecodeError:
                    logger.error("Ошибка при декодировании JSON из БД")
                    return []
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении истории диалога: {e}")
            return []

    def clear_dialog_history(self, chat_id: int, ai_name: str = None) -> None:
        """
        Очищает историю диалога для конкретного пользователя.
        Если ai_name не указан, очищает все диалоги пользователя.
        """
        try:
            # Очищаем локальный кэш
            if ai_name:
                dialog_key = (chat_id, ai_name)
                if dialog_key in self.dialog_sessions:
                    del self.dialog_sessions[dialog_key]
                # Очищаем в БД

            else:
                # Очищаем все диалоги пользователя
                keys_to_delete = [
                    k for k in self.dialog_sessions.keys() if k[0] == chat_id]
                for key in keys_to_delete:
                    del self.dialog_sessions[key]
                # Очищаем в БД

            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при очистке истории диалога: {e}")
            raise

    def close(self):
        """Закрывает соединение с базой данных"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    async def update_last_message(self, chat_id: int, message_id: int):
        """Сохраняет ID последнего сообщения бота"""
        if not self.is_connected:
            return

        try:
            self.cursor.execute("""
                INSERT INTO last_messages (chat_id, message_id) 
                VALUES (%s, %s)
                ON CONFLICT (chat_id) 
                DO UPDATE SET message_id = EXCLUDED.message_id, 
                             updated_at = CURRENT_TIMESTAMP
            """, (chat_id, message_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при сохранении ID сообщения: {e}")

    async def get_last_message(self, chat_id: int) -> int | None:
        """Получает ID последнего сообщения бота"""
        if not self.is_connected:
            return None

        try:
            self.cursor.execute(
                "SELECT message_id FROM last_messages WHERE chat_id = %s",
                (chat_id,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при получении ID сообщения: {e}")
            return None


# Создаем глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager()
