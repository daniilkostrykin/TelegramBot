def get_ai_selection_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру выбора AI"""
    kb = [
        [KeyboardButton(text='🧠 Gemini')],
        [KeyboardButton(text='🦊 G4F')],
        [KeyboardButton(text='🌟 Mistral')],
        [KeyboardButton(text='🎨 Midjourney')],
        [KeyboardButton(text='🐉 Qwen')],
        [KeyboardButton(text='⬅️ Назад')]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
