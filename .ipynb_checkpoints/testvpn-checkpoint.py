import requests
import google.generativeai as genai

def test_connection():
    try:
        # Проверяем IP
        ip = requests.get('https://api.ipify.org?format=json').json()['ip']
        print(f"Current IP: {ip}")
        
        # Проверяем доступность Gemini
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content("Test message")
        print("Gemini доступен!")
        return True
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return False

# Используйте при запуске
if __name__ == "__main__":
    if test_connection():
        print("Соединение установлено успешно")
    else:
        print("Проблема с соединением")