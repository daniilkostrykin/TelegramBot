# keyboards.py

from telebot import types

# --- Клавиатуры (keyboard.py) ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    #video_button = types.KeyboardButton('Видео')
    #computer_button = types.KeyboardButton('Компьютер')
    ai_button = types.KeyboardButton('Нейросети')
    duck_button = types.KeyboardButton('🦆 Нейросети в интернете', web_app=types.WebAppInfo('https://duckduckgo.com/?q=DuckDuckGo+AI+Chat&ia=chat&duckai=1'))
    #markup.row(video_button, computer_button, ai_button)
    markup.row(ai_button, duck_button)
    return markup

def get_computer_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    #off_button = types.KeyboardButton('❌ Выключить компьютер')
    #restart_button = types.KeyboardButton('🔄 Перезагрузить компьютер')
    #chrome_button = types.KeyboardButton(
    #    text='🌐 Управление компьютером',
    #    web_app=types.WebAppInfo(url='https://remotedesktop.google.com/access/')
    #)
    open_site_button = types.KeyboardButton('🌐 Открыть сайт')
    #volume_button = types.KeyboardButton('🔊 Громкость')
    open_button = types.KeyboardButton('📂 Открыть папку')
    back_button = types.KeyboardButton('⬅️ Назад')
    #markup.add(off_button, restart_button, chrome_button)
    markup.add(open_site_button, open_button)
    markup.add(back_button)
    return markup

def get_dialog_keyboard(): # Клавиатура для режима диалога
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    end_dialog_button = types.KeyboardButton('⏹️ Завершить диалог')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(end_dialog_button, back_button)
    return markup

def get_ai_selection_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    text_text_button = types.KeyboardButton("Текст-Текст")
    text_image_button =  types.KeyboardButton("Текст-Изображение")
    text_voice_button = types.KeyboardButton("Текст-Голос")
    nocode_button = types.KeyboardButton("NoCode")
    back_button = types.KeyboardButton("⬅️ Назад")
    keyboard.add(text_text_button, text_image_button)
    keyboard.add(text_voice_button, nocode_button)
    keyboard.add(back_button)
    return keyboard


def get_text_text_button():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    chatgpt_button = types.KeyboardButton("ChatGPT")
    gemini_button = types.KeyboardButton("Gemini")
    g4f_button = types.KeyboardButton("G4F (Аналог ChatGPT)")
    back_button = types.KeyboardButton("⬅️ Назад")
    keyboard.add(chatgpt_button, gemini_button, g4f_button)
    keyboard.add(back_button)  
    return keyboard  

def get_text_image_button():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    midjourney_button = types.KeyboardButton("Midjourney")
    back_button = types.KeyboardButton("⬅️ Назад")
    keyboard.add(midjourney_button)
    keyboard.add(back_button)  
    return keyboard  

def get_text_voice_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    hailuo_button = types.KeyboardButton("Озвучка текста", web_app=types.WebAppInfo("https://www.hailuo.ai/audio"))
    audiobook_button = types.KeyboardButton("Озвучка книги", web_app=types.WebAppInfo("https://huggingface.co/spaces/drewThomasson/ebook2audiobook"))
    keyboard.add(hailuo_button, audiobook_button)

    back_button = types.KeyboardButton("⬅️ Назад")
    keyboard.add(back_button)

    return keyboard

def get_nocode_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    glide_button = types.KeyboardButton("Glide", web_app=types.WebAppInfo("https://www.glideapps.com/"))


    back_button = types.KeyboardButton("⬅️ Назад")
    keyboard.add(glide_button)
    keyboard.add(back_button)

    return keyboard
def get_g4f_model_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    model_1_button = types.KeyboardButton('GPT 4o mini')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(model_1_button)
    markup.add(back_button)
    return markup

def get_gemini_model_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    model_1_button = types.KeyboardButton('Gemini 2.0 Experimental')
    model_2_button = types.KeyboardButton('Gemini 1.5 Pro')
    model_3_button = types.KeyboardButton('Gemini 1.5 Flash')
    model_4_button = types.KeyboardButton('Gemini 2.0 Pro Experimental 02-05') 
    model_5_button = types.KeyboardButton('Gemini 2.0 Flash Thinking Experimental 01-21') 
    model_6_button = types.KeyboardButton('Gemini 2.0 Flash-Lite Preview 02-05') 
    model_7_button = types.KeyboardButton('Gemini 2.0 Flash') 
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(model_1_button, model_2_button, model_3_button)
    markup.add(model_4_button, model_5_button, model_6_button)
    markup.add(model_7_button)
    markup.add(back_button)
    return markup
"""
def get_volume_keyboard(is_muted):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    mute_button = types.KeyboardButton('🔊 Включить звук' if is_muted else '🔇 Выключить звук')
    up_button = types.KeyboardButton('🔊 Повысить громкость')
    down_button = types.KeyboardButton('🔉 Понизить громкость')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(mute_button)
    markup.add(up_button, down_button)
    markup.add(back_button)
    return markup
"""