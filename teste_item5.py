from dotenv import load_dotenv
load_dotenv(override=True)

from modules.groq_ai import client, GROQ_MODEL

print("Modelo:", GROQ_MODEL)

try:
    raw = client.chat.completions.with_raw_response.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": "oi"}],
    )
    for k, v in raw.headers.items():
        if "ratelimit" in k.lower() or "retry" in k.lower():
            print(k, "=", v)
    print("RESPOSTA:", raw.parse().choices[0].message.content)
except Exception as e:
    print("ERRO COMPLETO:")
    print(e)