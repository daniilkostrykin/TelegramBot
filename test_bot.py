import asyncio
from aiogram import types
# bot_handlers.py
import re
import threading
import time
import requests
import logging
import os
from z.config import ADMIN_ID, POPULAR_SITES, GEMINI_API_KEY, BOT_TOKEN, MISTRAL_API_KEY
import google.generativeai as genai
from g4f.client import Client
from deep_translator import GoogleTranslator
from aiogram.types import Message
from z.keyboards import *
import psycopg2
import json
import traceback
from aiogram.fsm.state import State, StatesGroup
from aiogram import Dispatcher, Bot, types, F
from aiogram.utils import markdown
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
import asyncio
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import BaseFilter
from mistralai import Mistral
import aiohttp
import PIL.Image
bot = Bot(token=BOT_TOKEN)


def process_code_block(text: str) -> list:
    """
    Разделяет текст на обычный текст и блоки кода.
    Возвращает список кортежей (текст, is_code).
    """
    parts = []
    pattern = r'```(?:python)?\n([\s\S]*?)```'
    last_end = 0

    for match in re.finditer(pattern, text):
        if match.start() > last_end:
            parts.append((text[last_end:match.start()], False))

        parts.append((match.group(1), True))
        last_end = match.end()

    if last_end < len(text):
        parts.append((text[last_end:], False))

    return parts if parts else [(text, False)]


def to_markdown(text: str) -> str:
    """
    Преобразует текст в формат Markdown для Telegram.
    Обрабатывает жирный текст, код и другие элементы.
    """
    bold_texts = []

    def save_bold(match):
        inner_text = match.group(1)
        inner_text = re.sub(r'\*([^*]+)\*', r'*\1*', inner_text)
        bold_texts.append(inner_text)
        return f"§BOLD{len(bold_texts)-1}§"

    math_exprs = []

    def save_math(match):
        math_exprs.append(match.group(0))
        return f"§MATH{len(math_exprs)-1}§"

    # Обрабатываем строки с кодом внутри жирного текста, чтобы они не стали жирными
    def save_code_in_bold(match):
        code = match.group(1)
        return f"§CODE{len(bold_texts)}§"

    # Сначала находим строки с кодом в жирном тексте и меняем их на метки
    text = re.sub(r'\*\*`(.*?)`\*\*', save_code_in_bold, text)

    # Обрабатываем жирный текст
    text = re.sub(r'\*\*(.*?)\*\*', save_bold, text, flags=re.DOTALL)

    # Заменяем математические выражения
    text = re.sub(r'\d+\s*\*\s*\d+', save_math, text)

    # Заменяем HTML-теги
    text = re.sub(r'<sup>([^<]+)</sup>', r'^1', text)
    text = re.sub(r'<sub>([^<]+)</sub>', r'_1', text)

    # Заменяем маркеры списка
    text = re.sub(r'^\s*\*\s+', '• ', text, flags=re.MULTILINE)

    # Экранируем специальные символы Markdown
    special_chars = '_*[]()~>#+-=|{}.!\\'
    escaped_text = ''.join(
        f'\\{char}' if char in special_chars else char for char in text)
    text = escaped_text

    # Вставляем назад кодовые элементы, чтобы они не были жирными
    for i, bold_text in enumerate(bold_texts):
        escaped_bold = ''.join(
            f'\\{char}' if char in special_chars and char != '*' else char for char in bold_text)
        text = text.replace(f"§BOLD{i}§", f"*{escaped_bold}*")

    # Вставляем назад математические выражения
    for i, math_expr in enumerate(math_exprs):
        escaped_expr = ''.join(
            f'\\{char}' if char in special_chars else char for char in math_expr)
        text = text.replace(f"§MATH{i}§", escaped_expr)

    # Вставляем метки для кода обратно
    for i, _ in enumerate(bold_texts):
        text = text.replace(f"§CODE{i}§", f"`{bold_texts[i]}`")

    return text


async def safe_send_message(message: types.Message, text: str):
    MAX_LENGTH = 4000
    try:
        parts = process_code_block(text)
        current_message = ""

        for content, is_code in parts:
            if not content.strip():
                continue

            if is_code:
                if current_message:
                    await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                    current_message = ""

                await message.answer(f"```\n{content}\n```", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                formatted_text = to_markdown(content)

                if len(current_message) + len(formatted_text) > MAX_LENGTH:
                    await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                    current_message = formatted_text
                else:
                    current_message += formatted_text

        if current_message:
            await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        print(f"Ошибка форматирования: {e}")
        await message.answer(text)


async def test_safe_send_message():
    # Создаем мок-объект для сообщения
    class MockMessage:
        async def answer(self, text, parse_mode=None):
            print(f"\nОтформатированное сообщение (parse_mode={parse_mode}):")
            print("=" * 50)
            print(text)
            print("=" * 50)
            # Отправляем сообщение в реальный бот
            await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=parse_mode)
            return None

    mock_message = MockMessage()

    # Тестовые сообщения
    test_messages = [
        "Простой текст без форматирования",

        "Текст с **жирным** форматированием",

        "Текст с кодом:\n```python\ndef hello():\n    print('Hello')\n```",

        "Смешанный текст с **жирным** и `кодом`\n```\nprint('test')\n```",

        "Математические выражения: 2 * 2 = 4",

        "Список:\n* Пункт 1\n* Пункт 2",

        "Текст с <sup>верхним</sup> и <sub>нижним</sub> индексом"
    ]

    # Тестируем каждое сообщение
    for msg in test_messages:
        print("\nТестирование сообщения:")
        print(f"Исходный текст:\n{msg}")
        await safe_send_message(mock_message, msg)
        print("\nНажмите Enter для следующего теста...")
        input()

    # Закрываем сессию бота
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_safe_send_message())
