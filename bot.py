from flask import Flask, request
from telegram import Bot
import asyncio
import threading
import requests  # Import the requests library

app = Flask(__name__)
BOT_TOKEN = "7616648953:AAEbzkEo7zmVe1QALD3flEe_mtru7xfNtns"
bot = Bot(token=BOT_TOKEN)

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data['message']['chat']['id']
        message_text = data['message'].get('text', 'Нет текста')
        attachments = data['message'].get('document', None)

        await handle_message(chat_id, message_text, attachments)

    return "OK", 200


async def handle_message(chat_id, message_text, attachments):
    try:
        print(f"Отправляю сообщение: {message_text}")
        await bot.send_message(chat_id=chat_id, text=f"Я получил твое сообщение: {message_text}")

        if attachments:
            file_id = attachments['file_id']
            await bot.send_document(chat_id=chat_id, document=file_id)
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")


async def remove_webhook():
   try:
       webhook_url = await bot.get_webhook_info()
       if webhook_url.url:
           await bot.delete_webhook()
           print("Вебхук успешно удален.")
       else:
           print("Нет активного вебхука.")
   except Exception as e:
       print(f"Ошибка при удалении вебхука: {e}")


if __name__ == '__main__':
    import uvicorn
    import asyncio
    asyncio.run(remove_webhook())  # Вызываем удаление вебхука перед запуском приложения
    uvicorn.run(app, host='0.0.0.0', port=5000, loop="asyncio")