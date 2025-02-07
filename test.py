import logging
import requests
import telebot
from bs4 import BeautifulSoup
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import time

# Настроим логирование
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "7768700329:AAGDdhc3SOssFG-71E0zSsynlAH-6Y2mQwk"
bot = telebot.TeleBot(BOT_TOKEN)

# Адрес веб-страницы с textarea
WEB_PAGE_URL = "https://duckduckgo.com/?q=DuckDuckGo+AI+Chat&ia=chat&duckai=1&atb=v468-3"  # Замените на нужный URL страницы с textarea

# Инициализация драйвера для Selenium (например, для Chrome)
service = Service(r'C:\Users\Daniil\Downloads\chromedriver-win64 (2)\chromedriver-win64\chromedriver.exe')
driver = webdriver.Chrome(service=service)

# Функция для имитации нажатия кнопок через Selenium
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Функция для имитации нажатия кнопок через Selenium с использованием WebDriverWait
def simulate_button_clicks():
    try:
        logger.info("Открытие страницы через Selenium...")
        driver.get(WEB_PAGE_URL)

        # 1. Нажать на кнопку "Приступим!"
        logger.info("Ожидаем появления кнопки 'Приступим!'...")
        start_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Приступим!']"))
        )
        start_button.click()
        logger.info("Кнопка 'Приступим!' нажата.")

        # 2. Нажать на кнопку "Далее"
        logger.info("Ожидаем появления кнопки 'Далее'...")
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Далее']"))
        )
        next_button.click()
        logger.info("Кнопка 'Далее' нажата.")

        # 3. Нажать на кнопку "Принимаю условия"
        logger.info("Ожидаем появления кнопки 'Принимаю условия'...")
        accept_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Принимаю условия']"))
        )
        accept_button.click()
        logger.info("Кнопка 'Принимаю условия' нажата.")

    except Exception as e:
        logger.error(f"Ошибка при нажатии кнопок: {e}")

# Функция для отправки текста в textarea на веб-странице и получения ответа
def send_to_textarea_and_get_response(query):
    logger.info("Отправка запроса в форму на веб-странице...")

    # Выполним предварительные действия через Selenium
    simulate_button_clicks()

    # После выполнения всех действий, найдём textarea и отправим запрос
    try:
        logger.info("Поиск поля для ввода текста...")
        textarea = driver.find_element(By.NAME, "user-prompt")
        textarea.send_keys(query)  # Вводим текст в textarea
        textarea.send_keys("\n")  # Имитируем нажатие Enter для отправки запроса
        logger.info("Запрос отправлен в форму.")

        # Подождем, пока появится ответ (например, 3 секунды)
        time.sleep(10)

        # Найдем ответ на странице
        logger.info("Ищем ответ на странице...")
        response_div = driver.find_element(By.CLASS_NAME, "VrBPSncUavA1d7C9kAc5")
        # Извлекаем все параграфы <p>
        paragraphs = response_div.find_elements(By.TAG_NAME, "p")
        # Извлекаем все элементы <li>
        list_items = response_div.find_elements(By.TAG_NAME, "li")

        # Объединяем все параграфы и элементы списка в один ответ
        response_parts = []

        for p in paragraphs:
            response_parts.append(p.text)
        
        for li in list_items:
            response_parts.append(f"• {li.text}")  # Добавляем маркер для элементов списка

        # Объединяем все части в одну строку, разделяя их новой строкой
        full_response = "\n".join(response_parts)
        logger.info("Ответ получен.")
        return full_response.strip()

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {e}")
        return "Ошибка при получении ответа."

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_query = message.text
    bot.send_message(message.chat.id, "🔎 Ищу ответ...")

    ai_response = send_to_textarea_and_get_response(user_query)

    if not ai_response.strip():
        ai_response = "Ответ не найден. Попробуйте другой запрос."

    bot.send_message(message.chat.id, ai_response)

# Запуск бота
if __name__ == "__main__":
    logger.info("Запуск Telegram-бота...")
    bot.polling(none_stop=True)

    # Не забываем закрыть драйвер после завершения работы бота
    driver.quit()
