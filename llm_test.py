from google import genai
import os

# Вставьте ваш ключ напрямую или используйте переменную окружения
client = genai.Client(api_key="AIzaSyBP015NMILauAwurbJR92ZMdM_-Fbez0DQ")

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Тест связи"
    )
    print("✅ Ключ работает!")
    print(f"Ответ модели: {response.text}")
except Exception as e:
    print("❌ Ошибка при проверке ключа:")
    print(e)