import requests
from pprint import pprint
from dotenv import load_dotenv
import os
from typing import Dict, List

load_dotenv()

AI_IO_API_KEY = os.getenv("AI_IO_API_KEY")


url = "https://api.intelligence.io.solutions/api/v1/models"

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {AI_IO_API_KEY}",
}

response = requests.get(url, headers=headers)
data = response.json()
#pprint(data)

for i in range(len(data['data'])):
    name = data['data'][i]['id']
    print(name)
