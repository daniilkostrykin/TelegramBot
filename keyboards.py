# keyboards.py

from telebot import types

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    video_button = types.KeyboardButton('Видео')
    computer_button = types.KeyboardButton('Компьютер')
    gemini_button = types.KeyboardButton('Gemini')
    markup.row(video_button, computer_button, gemini_button)
    return markup

def get_video_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    pause_button = types.KeyboardButton('⏯️ Пауза / ⏸️ Воспроизведение')
    fast_forward = types.KeyboardButton('▶️ Перемотать вперед')
    fast_backward = types.KeyboardButton('◀️ Перемотать назад')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.row(pause_button)
    markup.row(fast_backward, fast_forward)
    markup.add(back_button)
    return markup

def get_computer_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    off_button = types.KeyboardButton('❌ Выключить компьютер')
    restart_button = types.KeyboardButton('🔄 Перезагрузить компьютер')
    chrome_button = types.KeyboardButton(
        text='🌐 Управление компьютером',
        web_app=types.WebAppInfo(url='https://remotedesktop.google.com/access/')
    )
    open_site_button = types.KeyboardButton('🌐 Открыть сайт')
    full_screen_button = types.KeyboardButton('📺 На весь экран')
    mouse_button = types.KeyboardButton('🖱️ Мышь')
    volume_button = types.KeyboardButton('🔊 Громкость')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(off_button, restart_button, chrome_button)
    markup.add(open_site_button, full_screen_button, mouse_button, volume_button)
    markup.add(back_button)
    return markup

def get_gemini_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    search_button = types.KeyboardButton('🔍 Запрос')
    dialog_button = types.KeyboardButton('💬 Диалог')
    search_internet_button = types.KeyboardButton('🔍 Поиск в интернете')
    open_button = types.KeyboardButton('📂 Открыть папку')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(search_button, dialog_button, search_internet_button)
    markup.add(open_button, back_button)
    return markup

def get_gemini_dialog_keyboard(): # Клавиатура для режима диалога
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    end_dialog_button = types.KeyboardButton('⏹️ Завершить диалог')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(end_dialog_button, back_button)
    return markup

def get_gemini_model_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    model_1_button = types.KeyboardButton('Gemini 2.0 Experimental')
    model_2_button = types.KeyboardButton('Gemini 1.5 Pro')
    model_3_button = types.KeyboardButton('Gemini 1.5 Flash')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(model_1_button, model_2_button, model_3_button)
    markup.add(back_button)
    return markup

def get_info_size_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    short_button = types.KeyboardButton('📏 Кратко')
    long_button = types.KeyboardButton('📐 Подробно')
    markup.add(short_button, long_button)
    return markup

def get_mouse_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    left_button = types.KeyboardButton('Лево')
    right_button = types.KeyboardButton('Право')
    back_button = types.KeyboardButton('⬅️ Назад')
    markup.add(left_button, right_button)
    markup.add(back_button)
    return markup

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