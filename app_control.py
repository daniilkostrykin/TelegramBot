# app_control.py

import os
import subprocess
import webbrowser
from fuzzywuzzy import process
from config import POPULAR_SITES, TRANSLATIONS

def get_closest_app(query):
    closest_match, score = process.extractOne(query, TRANSLATIONS.keys())
    if score > 60:
        return TRANSLATIONS[closest_match]
    return None

def open_file(path):
    try:
        os.startfile(path)
        return True
    except Exception as e:
        print(f"Ошибка при открытии файла или папки: {e}")
        return False
def open_link(command, task_name=None):
    """Открывает ссылку по указанной команде и запускает задачу, если указано."""
    command = command.lower().strip()
    for key, url in POPULAR_SITES.items():
        if key in command:
            # Если указано задание в планировщике задач
            if task_name:
                if not run_task(task_name):
                    return False
                print(f"Запускаю задачу: {task_name}")
            # Открытие ссылки
            try:
                webbrowser.open(url)
                print(f"Открываю ссылку: {url}")
                return True
            except Exception as e:
                print(f"Ошибка при открытии ссылки {key}: {e}")
                return False
    print(f"Ссылка для команды '{command}' не найдена.")
    return False
def run_task(task_name):
    """Запускает задачу из Планировщика задач."""
    try:
        result = subprocess.run(
            ["schtasks", "/run", "/tn", task_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            print(f"Задача '{task_name}' успешно запущена.")
            return True
        else:
            print(f"Ошибка при запуске задачи '{task_name}': {result.stderr}")
            return False
    except Exception as e:
        print(f"Ошибка выполнения: {e}")
        return False

def open_application(query):
    query = query.lower().strip()
    closest_app = get_closest_app(query)
    if closest_app:
        if os.path.exists(closest_app):
            if closest_app.endswith(".exe"):
                try:
                    subprocess.Popen([closest_app])
                    return True
                except Exception as e:
                    print(f"Ошибка при открытии {query}: {e}")
                    return False
            elif closest_app.endswith(".lnk"):
                return open_file(closest_app)
            else:
                return open_file(closest_app)
        else:
            print(f"Путь для {query} не существует: {closest_app}")
    else:
        print(f"Не найдено подходящего приложения для команды '{query}'")
    return False