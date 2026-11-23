import os
import time

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from core.prompt import montar_prompt

KEY = os.getenv("GEMINI_API_KEY")
codigo = open("api/voz.py", encoding="utf-8").read()
GRANDE = montar_prompt("analise esse código\n\n```\n" + codigo + "\n```", "")


def rodar(rotulo, modelo, prompt, timeout_ms):
    client = genai.Client(
        api_key=KEY, http_options=types.HttpOptions(timeout=timeout_ms)
    )
    t = time.perf_counter()
    try:
        i = client.interactions.create(model=modelo, input=prompt)
        dt = time.perf_counter() - t
        print(f"\n[{rotulo}] {modelo} OK em {dt:.1f}s")
        print("  saída (chars):", len(i.output_text or ""))
        print("  usage:", getattr(i, "usage", None))
    except Exception as e:
        dt = time.perf_counter() - t
        print(f"\n[{rotulo}] {modelo} FALHOU em {dt:.1f}s: "
              f"{type(e).__name__}: {str(e)[:150]}")


# 1) unidade do timeout: se for ms, estoura em ~0,5 s; se for s, não estoura
rodar("timeout 500", "gemini-3.5-flash-lite", "diga ok", 500)

# 2) mesmo arquivo grande no Lite
rodar("grande lite", "gemini-3.5-flash-lite", GRANDE, 300_000)

# 3) mesmo arquivo grande no 3.6 (gasta 1 dos 20 pedidos/dia)
rodar("grande 3.6", "gemini-3.6-flash", GRANDE, 300_000)