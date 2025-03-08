import psycopg2
import logging

logger = logging.getLogger(__name__)


def test_db_connection():
    """
    Тестирует соединение с базой данных и выводит подробную информацию об ошибках.
    """
    try:
        # Пробуем подключиться к базе данных
        conn = psycopg2.connect(
            dbname="tgbot",
            user="postgres",
            password="postgres",
            host="localhost",
            port="5432",
     
        )
        print(f"Сообщение: {e.pgerror.encode('utf-8', 'ignore').decode('utf-8')}")

        # Если соединение успешно, создаем курсор
        cursor = conn.cursor()

        # Пробуем выполнить простой запрос
        cursor.execute("SELECT version();")
        version = cursor.fetchone()

        print("✅ Успешное подключение к базе данных!")
        print(f"📊 Версия PostgreSQL: {version[0]}")

        # Закрываем соединение
        cursor.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        print("❌ Ошибка при подключении к базе данных:")
        print(f"Код ошибки: {e.pgcode}")
        print(f"Сообщение: {e.pgerror}")
        print(f"Диагностика: {e.diag}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        return False


if __name__ == "__main__":
    # Если файл запущен напрямую, выполняем тест
    test_db_connection()
