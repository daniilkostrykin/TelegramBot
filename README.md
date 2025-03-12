---

# 🚀 Telegram AI Bot  

Этот проект — Telegram-бот, интегрирующий различные нейросети, такие как Gemini, Mistral, G4F и другие, с возможностью обработки текстов, изображений и голосовых сообщений.

## 📌 Функции бота  
✅ Генерация текста с помощью нейросетей (Gemini, G4F, Mistral, Qwen)  
✅ Генерация изображений (Midjourney)  
✅ Озвучивание текста  
✅ Интерактивное управление через Telegram-клавиатуру  
✅ Интеграция с базой данных PostgreSQL  

---

## 🔧 Установка и настройка  

### 1️⃣ **Клонирование репозитория**  
```sh
git clone https://github.com/daniilkostrykin/TelegramBot.git
cd telegram-ai-bot
```

### 2️⃣ **Создание и активация виртуального окружения**  
```sh
python3 -m venv venv
source venv/bin/activate  # Для Linux/macOS
venv\Scripts\activate     # Для Windows
```

### 3️⃣ **Установка зависимостей**  
```sh
pip install -r requirements.txt
```

### 4️⃣ **Настройка переменных окружения**  
Создайте файл `.env` и добавьте в него:  
```ini
BOT_TOKEN=your-telegram-bot-token
DB_URL=your-database-url
GEMINI_API_KEY=your-gemini-api-key
MISTRAL_API_KEY=your-mistral-api-key
TOGETHER_API_KEY=your-together-api-key
ADMIN_ID=your-telegram-id
```

---

## ⚙️ **Запуск бота**  

### **1. Обычный запуск**
```sh
python main.py
```
Бот автоматически зарегистрирует обработчики и начнет получать обновления.

### **2. Запуск в Docker (если используется)**
Создайте `Dockerfile`:  
```dockerfile
FROM python:3.11
WORKDIR /bot
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```
Затем:  
```sh
docker build -t telegram-ai-bot .
docker run -d --env-file .env telegram-ai-bot
```

---

## 🏗 **Структура проекта**
```
/telegram-ai-bot
│── main.py                     # Главный файл для запуска бота
│── bot_handlers.py              # Основные обработчики команд
│── g4f.py                       # Обработчики G4F
│── requirements.txt             # Зависимости проекта
│── .env                         # Переменные окружения (не добавлять в Git)
│── /src
│   ├── handlers/
│   │   ├── gemini.py            # Обработчики Gemini
│   │   ├── mistral.py           # Обработчики Mistral
│   │   ├── midjourney.py        # Обработчики Midjourney
│   ├── database/
│   │   ├── db_manager.py        # Управление базой данных
│   ├── models/
│   │   ├── dialog_state.py      # Состояния диалогов FSM
│   │   ├── user_state.py        # Состояния пользователей FSM
│   ├── keyboards.py             # Телеграм-клавиатуры
```

---

## 🎯 **Основные файлы**
### **`main.py` (точка входа)**
- Загружает токен бота из `.env`
- Настраивает логирование
- Запускает `setup_handlers(bot)`  
- Удаляет вебхук и запускает **polling**  

### **`bot_handlers.py` (обработчики команд)**
- Регистрирует команды `/start`, `/help`
- Инициализирует FSM (Finite State Machine)
- Управляет состояниями и клавиатурами  

### **`g4f.py` (обработчики G4F)**
- Подключает G4F API  
- Обрабатывает выбор моделей  
- Управляет диалогами  

---

## 📡 **Использование бота**
После запуска в Telegram используйте команды:
```
/start    - Запуск бота
/g4f      - Включение G4F
/gemini   - Включение Gemini
/mistral  - Включение Mistral
/qwen     - Включение Qwen
```
Выберите AI и отправьте запрос. Бот обработает его и ответит.

---

---

👨‍💻 Автор: **Daniil**  
📅 Дата: **2025**  
🚀 Готово к использованию!  

---
