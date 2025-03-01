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
        bold_texts.append(inner_text)
        return f"§BOLD{len(bold_texts)-1}§"

    math_exprs = []

    def save_math(match):
        math_exprs.append(match.group(0))
        return f"§MATH{len(math_exprs)-1}§"

    # Сначала сохраняем математические выражения
    # Сохраняем сложные математические выражения с последовательными умножениями
    text = re.sub(
        r'(?:\d+(?:/\d+)?|\(\d+(?:/\d+)?\))(?:\s*\*\s*(?:\d+(?:/\d+)?|\(\d+(?:/\d+)?\)))+', save_math, text)
    # Сохраняем простые умножения вида 2 * 3
    text = re.sub(r'\d+\s*\*\s*\d+', save_math, text)
    # Сохраняем степени вида ^6
    text = re.sub(r'\^[0-9]+', save_math, text)

    # Сохраняем маркеры списка, заменяя их временно
    text = re.sub(r'^(\s*)\*(\s+)', r'\1§LIST§\2', text, flags=re.MULTILINE)

    # Обрабатываем двойные звездочки (обычный жирный текст)
    text = re.sub(r'\*\*(.*?)\*\*', save_bold, text, flags=re.DOTALL)

    # Обрабатываем одиночные звездочки (если это не маркер списка)
    text = re.sub(r'\*([^*\n]+)\*', save_bold, text)

    # Возвращаем маркеры списка
    text = text.replace('§LIST§', '*')

    # Заменяем HTML-теги
    text = re.sub(r'<sup>([^<]+)</sup>', r'^\1', text)
    text = re.sub(r'<sub>([^<]+)</sub>', r'_\1', text)

    # Заменяем маркеры списка на буллеты
    text = re.sub(r'^\s*\*\s+', '• ', text, flags=re.MULTILINE)

    # Экранируем специальные символы Markdown
    special_chars = '_*[]()~>#+-=|{}.!\\'
    escaped_text = ''.join(
        f'\\{char}' if char in special_chars else char for char in text)
    text = escaped_text

    # Вставляем назад жирный текст
    for i, bold_text in enumerate(bold_texts):
        escaped_bold = ''.join(
            f'\\{char}' if char in special_chars and char != '*' else char for char in bold_text)
        text = text.replace(f"§BOLD{i}§", f"*{escaped_bold}*")

    # Вставляем назад математические выражения
    for i, math_expr in enumerate(math_exprs):
        escaped_expr = ''.join(
            f'\\{char}' if char in special_chars else char for char in math_expr)
        text = text.replace(f"§MATH{i}§", escaped_expr)

    return text


async def safe_send_message(message: types.Message, text: str):
    MAX_LENGTH = 3500
    try:
        parts = process_code_block(text)
        current_message = ""

        for content, is_code in parts:
            if not content.strip():
                continue

            if is_code:
                if current_message:
                    try:
                        await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception as e:
                        if "can't parse entities: Can't find end of Bold" in str(e):
                            # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                            fixed_text = current_message
                            # Если нечетное количество звездочек
                            if fixed_text.count('*') % 2 != 0:
                                fixed_text += '*'
                            await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await message.answer(current_message)
                    current_message = ""

                # Разбиваем длинный код на части
                code_parts = [content[i:i + MAX_LENGTH]
                              for i in range(0, len(content), MAX_LENGTH)]
                for code_part in code_parts:
                    try:
                        await message.answer(f"```\n{code_part}\n```", parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception as e:
                        if "can't parse entities: Can't find end of PreCode entity" in str(e):
                            # Если ошибка связана с незакрытым блоком кода, добавляем закрывающие символы
                            fixed_code = code_part
                            if not fixed_code.endswith('\n'):
                                fixed_code += '\n'
                            await message.answer(f"```\n{fixed_code}\n```", parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await message.answer(code_part)
            else:
                formatted_text = to_markdown(content)

                if len(current_message) + len(formatted_text) > MAX_LENGTH:
                    try:
                        await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception as e:
                        if "can't parse entities: Can't find end of Bold" in str(e):
                            # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                            fixed_text = current_message
                            # Если нечетное количество звездочек
                            if fixed_text.count('*') % 2 != 0:
                                fixed_text += '*'
                            await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await message.answer(current_message)
                    current_message = formatted_text
                else:
                    current_message += formatted_text

        if current_message:
            try:
                await message.answer(current_message, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception as e:
                if "can't parse entities: Can't find end of Bold" in str(e):
                    # Если ошибка связана с незакрытым жирным текстом, добавляем закрывающую звездочку
                    fixed_text = current_message
                    # Если нечетное количество звездочек
                    if fixed_text.count('*') % 2 != 0:
                        fixed_text += '*'
                    await message.answer(fixed_text, parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    await message.answer(current_message)

    except Exception as e:
        print(f"Ошибка форматирования: {e}")
        # Если произошла ошибка форматирования, разбиваем текст на части и отправляем без форматирования
        text_parts = [text[i:i + MAX_LENGTH]
                      for i in range(0, len(text), MAX_LENGTH)]
        for part in text_parts:
            await message.answer(part)


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
        "Математические выражения:(1/6) * (1/6) * (1/6) * (1/6) * (1/6) * (1/6) = (1/6)^6 = 1/46656",

        "Разные варианты умножения:\n2 * 3 = 6\n(1/2) * 4 = 2\n(3/4) * (2/3) = 1/2",

        "Комплексный тест:\n* Маркер списка\n* Маркер с *выделением*\nОбычный текст с *выделением*\n2 * 3 = 6\n* Еще маркер",

        "Простой текст без форматирования",

        "Текст с **жирным** форматированием",

        "Текст с *одиночными* звездочками",

        "Текст с формулой: 2 * 3 = 6",

        "Текст с *жирным* и *2-м числом*",

        "Список с маркерами:\n* Первый пункт\n* Второй пункт с *выделением*\n* Третий пункт",

        "Смешанный текст:\n* Маркер списка\nОбычный *выделенный* текст\n* Еще маркер",

        "Текст с кодом:\n```python\ndef hello():\n    print('Hello')\n```",

        "Смешанный текст с **жирным** и `кодом`\n```\nprint('test')\n```",

        "Математические выражения: 2 * 2 = 4",

        "Список:\n* Пункт 1\n* Пункт 2",

        "Текст с <sup>верхним</sup> и <sub>нижним</sub> индексом",
        """

**Объяснение:**

 

*   `import copy`: Импортирует модуль `copy`, который позволяет создавать копии объектов.

*   `new_list = copy.copy(my_list)`:  Создает *поверхностную* копию списка `my_list`.  Это важно, чтобы `random.shuffle` не изменял исходный список.  Если в списке находятся изменяемые объекты (например, другие списки или словари), то нужно использовать `copy.deepcopy` для создания *глубокой* копии.

*   `random.shuffle(new_list)`: Перемешивает *копию* списка.

*   Возвращается новая, перемешанная копия списка.  Исходный список остается неизменным.

 

**Какой рандомайзер выбрать?**

 

*   Если вам нужно просто сгенерировать случайное число, используйте вариант 1.

*   Если вам нужно выбрать случайный элемент из списка, используйте вариант 2.  **Обязательно проверяйте список на пустоту!**

*   Если вам нужно перемешать список и *не важно*, что исходный список будет изменен, используйте вариант 3.

*   Если вам нужно перемешать список, но *важно сохранить исходный список без изменений*, используйте вариант 4.

 

**Более продвинутые варианты (кратко):**

 

*   **Генерация случайных паролей:** Используйте `random.choice` для выбора символов из заданного набора и объедините их в строку.

*   **Моделирование бросков костей/монет:** Используйте `random.randint` для моделирования бросков костей (например, `random.randint(1, 6)` для шестигранного кубика) или монеты (`random.choice(["орел", "решка"])`).

*   **Случайная выборка из набора данных:** Используйте `random.sample` для выбора `k` уникальных элементов из списка.

 

Надеюсь, эти примеры помогут вам создать нужный рандомайзер! Если у вас есть более конкретная задача, опишите ее, и я постараюсь помочь.

 """
    ]
    text = ["""Вот несколько примеров рандомайзеров на разных языках программирования:

 

**Python:**

 

```python

import random

 

def random_number(min_value, max_value):



  Возвращает случайное целое число в диапазоне [min_value, max_value] включительно.



  return random.randint(min_value, max_value)

 

def random_choice(options):


  Возвращает случайный элемент из списка.


  return random.choice(options)

 

def shuffle_list(my_list):



  Перемешивает список случайным образом на месте.


  random.shuffle(my_list)

  return my_list # Возвращает перемешанный список для удобства, но он уже изменен

 

# Пример использования:

print("Случайное число между 1 и 10:", random_number(1, 10))

 

colors = ["красный", "синий", "зеленый"]

print("Случайный цвет:", random_choice(colors))

 

numbers = [1, 2, 3, 4, 5]

print("Перемешанный список:", shuffle_list(numbers))

```

 

**JavaScript:**

 

```javascript

function randomNumber(minValue, maxValue) {

  /**

   * Возвращает случайное целое число в диапазоне [minValue, maxValue] включительно.

   */

  return Math.floor(Math.random() * (maxValue - minValue + 1)) + minValue;

}

 

function randomChoice(options) {

  /**

   * Возвращает случайный элемент из массива.

   */

  const randomIndex = Math.floor(Math.random() * options.length);

  return options[randomIndex];

}

 

function shuffleArray(array) {

  /** ```
""", "Математические выражения: (1/6) * (1/6) * (1/6) * (1/6) * (1/6) * (1/6) = (1/6)^6 = 1/46656",

            "Разные варианты умножения:\n2 * 3 = 6\n(1/2) * 4 = 2\n(3/4) * (2/3) = 1/2", """Вероятность того, что 6 выпадет 6 раз подряд при броске игральной кости, равна:
(1/6) * (1/6) * (1/6) * (1/6) * (1/6) * (1/6) = (1/6)<sup>6</sup> = 1/46656

То есть, вероятность составляет примерно 0.00002143347. Или примерно 0.0021%.""",
            """Вы имеете в виду язык программирования C++? Если да, то вот некоторые его плюсы:

 

**Преимущества C++:**

 

*   **Высокая производительность:** C++ позволяет очень эффективно управлять памятью и ресурсами, что делает его идеальным для задач, требующих высокой производительности, таких как разработка игр, операционных систем, драйверов устройств и высоконагруженных серверов.  Он компилируется непосредственно в машинный код, минуя интерпретацию, что дает огромный прирост скорости по сравнению с языками, использующими виртуальную машину (например, Java или C#).

 

*   **Контроль над памятью:** C++ предоставляет разработчику полный контроль над управлением памятью.  Это означает, что можно оптимизировать использование памяти для конкретной задачи, но и требует большей ответственности (например, ручное выделение и освобождение памяти для предотвращения утечек).

 

*   **Объектно-ориентированное программирование (ООП):** C++ полностью поддерживает принципы ООП (инкапсуляция, наследование, полиморфизм), что позволяет создавать сложные и модульные приложения.

 

*   **Широкое распространение и большое сообщество:** C++ - один из самых популярных и старых языков программирования. Это означает, что существует огромное количество библиотек, фреймворков, документации и примеров кода, а также большое и активное сообщество разработчиков, готовых помочь.

 

*   **Переносимость:** Код на C++ можно компилировать для различных платформ (Windows, Linux, macOS и другие).  Хотя, конечно, иногда требуется внесение изменений для адаптации к конкретной операционной системе или архитектуре.

 

*   **Близость к аппаратному обеспечению:** C++ позволяет работать с аппаратным обеспечением на низком уровне, что особенно важно при разработке драйверов устройств и системного программного обеспечения.

 

*   **Использование в других языках и технологиях:** Многие другие языки программирования (например, Python, Java) используют C++ в качестве основы или для расширения функциональности, особенно в тех случаях, когда требуется высокая производительность.

 

*   **Возможность создавать высокопроизводительные игры:** Многие современные игры написаны на C++ из-за его способности эффективно обрабатывать графику, физику и другие сложные расчеты.

 

*   **Обратная совместимость с C:** C++ обратно совместим с языком C, что позволяет использовать код, написанный на C, в C++ проектах.

 

**В заключение:** C++ - мощный и гибкий язык программирования, идеально подходящий для задач, где требуется высокая производительность, контроль над ресурсами и возможность работы с аппаратным обеспечением. Однако, его сложность может представлять собой проблему для начинающих программистов.""", """Вероятность выпадения определенного числа на игральной кости (например, 6) равна 1/6, если кость честная. 

 

Если мы хотим узнать вероятность того, что 6 выпадет **подряд** несколько раз, то нужно перемножить вероятности каждого отдельного броска.

 

Например, вероятность того, что 6 выпадет два раза подряд, будет:

 

(1/6) * (1/6) = 1/36

 

В вашем вопросе вы спрашиваете о вероятности, что 6 выпадет **подряд** несколько раз. Но не указано сколько раз.  Поэтому давайте рассмотрим несколько примеров:

 

*   **Вероятность выпадения шести 2 раза подряд:** 1/36

*   **Вероятность выпадения шести 3 раза подряд:** (1/6) * (1/6) * (1/6) = 1/216

*   **Вероятность выпадения шести *n* раз подряд:** (1/6)<sup>n</sup>

 

**Пожалуйста, уточните, сколько раз подряд должна выпасть шестерка, чтобы я мог дать вам точный ответ.**"""
            ]
    # Тестируем каждое сообщение
    for msg in text:
        print("\nТестирование сообщения:")
        print(f"Исходный текст:\n{msg}")
        await safe_send_message(mock_message, msg)
        print("\nНажмите Enter для следующего теста...")
        input()

    # Закрываем сессию бота
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_safe_send_message())
