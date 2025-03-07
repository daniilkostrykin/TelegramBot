"""
Модуль dialog_state содержит классы состояний для диалогов с различными AI моделями.
"""

from aiogram.fsm.state import State, StatesGroup


class DialogStates(StatesGroup):
    """Класс состояний для диалогов с AI моделями."""

    waiting_for_dialog = State()
    waiting_for_g4f_dialog = State()
    waiting_for_model_selection = State()
    waiting_for_g4f_model = State()
    waiting_for_mistral_dialog = State()
    waiting_for_mistral_model = State()
    waiting_for_text_image = State()
    waiting_for_text_voice = State()
    waiting_for_nocode = State()
    waiting_for_appearance = State()
    waiting_for_photo = State()
    waiting_for_midjourney = State()
    waiting_for_qwen_dialog = State()
