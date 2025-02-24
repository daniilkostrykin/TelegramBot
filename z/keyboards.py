# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# --- Клавиатуры (keyboard.py) ---
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    # video_button = KeyboardButton('Видео')
    # computer_button = KeyboardButton('Компьютер')
    ai_button = KeyboardButton('Нейросети')
    duck_button = KeyboardButton('🦆 Нейросети в интернете', web_app=WebAppInfo(
        'https://duckduckgo.com/?q=DuckDuckGo+AI+Chat&ia=chat&duckai=1'))
    # markup.row(video_button, computer_button, ai_button)
    markup.row(ai_button, duck_button)
    return markup


def get_computer_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    # off_button = KeyboardButton('❌ Выключить компьютер')
    # restart_button = KeyboardButton('🔄 Перезагрузить компьютер')
    # chrome_button = KeyboardButton(
    #    text='🌐 Управление компьютером',
    #    web_app=WebAppInfo(url='https://remotedesktop.google.com/access/')
    # )
    open_site_button = KeyboardButton('🌐 Открыть сайт')
    # volume_button = KeyboardButton('🔊 Громкость')
    open_button = KeyboardButton('📂 Открыть папку')
    back_button = KeyboardButton('⬅️ Назад')
    # markup.add(off_button, restart_button, chrome_button)
    markup.add(open_site_button, open_button)
    markup.add(back_button)
    return markup


def get_dialog_keyboard():  # Клавиатура для режима диалога
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    end_dialog_button = KeyboardButton('⏹️ Завершить диалог')
    back_button = KeyboardButton('⬅️ Назад')
    markup.add(end_dialog_button, back_button)
    return markup


def get_ai_selection_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    text_text_button = KeyboardButton("Текст-Текст")
    text_image_button = KeyboardButton("Текст-Изображение")
    text_voice_button = KeyboardButton("Текст-Голос")
    nocode_button = KeyboardButton("NoCode")
    appearance_button = KeyboardButton("Внешность")
    photo_button = KeyboardButton("Фото")
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(text_text_button, text_image_button)
    keyboard.add(text_voice_button, nocode_button)
    keyboard.add(appearance_button, photo_button)
    keyboard.add(back_button)
    return keyboard


def get_text_text_button():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    chatgpt_button = KeyboardButton(
        "ChatGPT🌐", web_app=WebAppInfo("https://chatgpt.com/"))
    gemini_button = KeyboardButton("Gemini")
    g4f_button = KeyboardButton("G4F (Аналог ChatGPT)")
    mistral_button = KeyboardButton("Mistral AI")
    microsoft_copilot_button = KeyboardButton(
        "Microsoft Copilot🌐", web_app=WebAppInfo("https://copilot.microsoft.com/"))
    github_copilot_button = KeyboardButton(
        "Github Copilot🌐", web_app=WebAppInfo("https://github.com/copilot"))
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(chatgpt_button, gemini_button)
    keyboard.add(g4f_button, mistral_button)
    keyboard.add(microsoft_copilot_button)
    keyboard.add(github_copilot_button)
    keyboard.add(back_button)
    return keyboard


def get_text_image_button():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    midjourney_button = KeyboardButton("Midjourney")
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(midjourney_button)
    keyboard.add(back_button)
    return keyboard


def get_text_voice_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    hailuo_button = KeyboardButton("Озвучка текста")
    audiobook_button = KeyboardButton("Озвучка книги", web_app=WebAppInfo(
        "https://huggingface.co/spaces/drewThomasson/ebook2audiobook"))
    keyboard.add(hailuo_button, audiobook_button)
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(back_button)
    return keyboard


def get_nocode_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    glide_button = KeyboardButton(
        "Glide", web_app=WebAppInfo("https://www.glideapps.com/"))
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(glide_button)
    keyboard.add(back_button)
    return keyboard


def get_appearance_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    tough_tongue_ai_button = KeyboardButton(
        "Tough Tongue AI", web_app=WebAppInfo("https://app.toughtongueai.com/"))
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(tough_tongue_ai_button)
    keyboard.add(back_button)
    return keyboard


def get_photo_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    memenome_button = KeyboardButton(
        "Memenome", web_app=WebAppInfo("https://www.memenome.gg/"))
    back_button = KeyboardButton("⬅️ Назад")
    keyboard.add(memenome_button)
    keyboard.add(back_button)
    return keyboard


def get_g4f_model_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    model_1_button = KeyboardButton('GPT 4o mini')
    back_button = KeyboardButton('⬅️ Назад')
    markup.add(model_1_button)
    markup.add(back_button)
    return markup


def get_gemini_model_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    model_1_button = KeyboardButton('Gemini 2.0 Experimental')
    model_2_button = KeyboardButton('Gemini 1.5 Pro')
    model_3_button = KeyboardButton('Gemini 1.5 Flash')
    model_4_button = KeyboardButton('Gemini 2.0 Pro Experimental 02-05')
    model_5_button = KeyboardButton(
        'Gemini 2.0 Flash Thinking Experimental 01-21')
    model_6_button = KeyboardButton('Gemini 2.0 Flash-Lite Preview 02-05')
    model_7_button = KeyboardButton('Gemini 2.0 Flash')
    back_button = KeyboardButton('⬅️ Назад')
    markup.add(model_1_button, model_2_button, model_3_button)
    markup.add(model_4_button, model_5_button, model_6_button)
    markup.add(model_7_button)
    markup.add(back_button)
    return markup


"""
def get_volume_keyboard(is_muted):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    mute_button = KeyboardButton('🔊 Включить звук' if is_muted else '🔇 Выключить звук')
    up_button = KeyboardButton('🔊 Повысить громкость')
    down_button = KeyboardButton('🔉 Понизить громкость')
    back_button = KeyboardButton('⬅️ Назад')
    markup.add(mute_button)
    markup.add(up_button, down_button)
    markup.add(back_button)
    return markup
"""
