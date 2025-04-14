# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton


# --- Клавиатуры (keyboard.py) ---
def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text='Нейросети'),
         KeyboardButton(text='🦆 Нейросети в интернете', web_app=WebAppInfo(
             url='https://duckduckgo.com/?q=DuckDuckGo+AI+Chat&ia=chat&duckai=1'))]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_computer_keyboard():
    keyboard = [
        [KeyboardButton(text='🌐 Открыть сайт'),
         KeyboardButton(text='📂 Открыть папку')],
        [KeyboardButton(text='⬅️ Назад')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_dialog_keyboard():  # Клавиатура для режима диалога
    keyboard = [
        [KeyboardButton(text='⏹️ Завершить диалог'),
         KeyboardButton(text='⬅️ Назад')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_ai_selection_keyboard():
    keyboard = [
        [KeyboardButton(text="Текст-Текст"),
         KeyboardButton(text="Текст-Изображение")],
        [KeyboardButton(text="Текст-Голос"), KeyboardButton(text="NoCode")],
        [KeyboardButton(text="Внешность"), KeyboardButton(text="Фото")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_text_text_button():
    keyboard = [
        [KeyboardButton(text="Gemini")],
        [KeyboardButton(text="G4F (Аналог ChatGPT)"),
         KeyboardButton(text="Mistral AI"), KeyboardButton(text="Qwen")],
        [KeyboardButton(text="AI.IO.NET")],
        [KeyboardButton(text="DeepSeek")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_text_image_button():
    keyboard = [
        [KeyboardButton(text="Midjourney")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_text_voice_keyboard():
    keyboard = [
        [KeyboardButton(text="Озвучка текста"), KeyboardButton(text="Озвучка книги", web_app=WebAppInfo(
            url="https://huggingface.co/spaces/drewThomasson/ebook2audiobook"))],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_nocode_keyboard():
    keyboard = [
        [KeyboardButton(text="Glide", web_app=WebAppInfo(
            url="https://www.glideapps.com/"))],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_appearance_keyboard():
    keyboard = [
        [KeyboardButton(text="Tough Tongue AI", web_app=WebAppInfo(
            url="https://app.toughtongueai.com/"))],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_photo_keyboard():
    keyboard = [
        [KeyboardButton(text="Memenome", web_app=WebAppInfo(
            url="https://www.memenome.gg/"))],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_g4f_model_keyboard():
    keyboard = [
        [KeyboardButton(text='GPT 4o mini')],
        [KeyboardButton(text='⬅️ Назад')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_gemini_model_keyboard():
    from src.handlers.gemini import model_mapping

    # Создаем список кнопок из model_mapping
    buttons = []

    # Первая кнопка на всю строку
    first_model = list(model_mapping.keys())[0]
    buttons.append([KeyboardButton(text=first_model)])

    # Остальные модели по три в ряд
    remaining_models = list(model_mapping.keys())[1:]
    for i in range(0, len(remaining_models), 3):
        row = []
        for model in remaining_models[i:i+3]:
            row.append(KeyboardButton(text=model))
        buttons.append(row)

    # Добавляем кнопку "Назад"
    buttons.append([KeyboardButton(text='⬅️ Назад')])

    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return markup


def get_mistral_model_keyboard():
    keyboard = [
        [KeyboardButton(text='Ministral 8b'), KeyboardButton(
            text='Mistral Medium'), KeyboardButton(text='Pixtral Large')],
        [KeyboardButton(text='Codestral'), KeyboardButton(
            text='Codestral Mamba'), KeyboardButton(text='Pixtral 12b')],
        [KeyboardButton(text='Mistral Small'), KeyboardButton(
            text='Mistral Saba'), KeyboardButton(text='Mistral Moderation')],
        [KeyboardButton(text='⬅️ Назад')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_ai_io_net_keyboard():
    keyboard = [
        [KeyboardButton(text='DeepSeek модели'),
         KeyboardButton(text='Qwen модели')],
        [KeyboardButton(text='Mistral модели'),
         KeyboardButton(text='LLaMA модели')],
        [KeyboardButton(text='Другие модели')],
        [KeyboardButton(text='⬅️ Назад')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup


def get_ai_io_net_model_keyboard(models: list):
    buttons = []
    for i in range(0, len(models), 2):
        row = [KeyboardButton(text=models[i])]
        if i + 1 < len(models):
            row.append(KeyboardButton(text=models[i + 1]))
        buttons.append(row)

    buttons.append([KeyboardButton(text='⬅️ Назад')])
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return markup
