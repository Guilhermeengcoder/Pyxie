import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Modelos Flash disponíveis para a sua chave:")
for m in client.models.list():
    if "flash" in m.name:
        print(" ", m.name)

CANDIDATOS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
for nome in CANDIDATOS:
    try:
        r = client.models.generate_content(model=nome, contents="Responda só: ok")
        print(f"OK     {nome}: {r.text.strip()[:30]}")
    except Exception as e:
        print(f"FALHA  {nome}: {str(e)[:120]}")