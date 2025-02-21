from openai import OpenAI
from config import DEEPSEEK_TOKEN

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=DEEPSEEK_TOKEN,
)
completion = client.chat.completions.create(
    model="deepseek/deepseek-chat",
    messages=[
        {
            "role": "user",
            "content": "В чем смысл жизни?"
        }])
print(completion. choices[0].message.content)
