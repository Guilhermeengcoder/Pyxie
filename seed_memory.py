# Envia o memory.json local para o Upstash Redis. Rode UMA vez:
#   python seed_memory.py
import json

from core import memory_json

if not memory_json._remoto():
    raise SystemExit(
        "Defina UPSTASH_REDIS_REST_URL e UPSTASH_REDIS_REST_TOKEN no .env primeiro."
    )

with open("memory.json", encoding="utf-8") as f:
    dados = json.load(f)

if not isinstance(dados, dict):
    raise SystemExit("O memory.json precisa ser um objeto JSON.")

if memory_json._cmd("GET", memory_json.CHAVE) is not None:
    resp = input("Já existe memória no Redis. Sobrescrever? (s/N) ").strip().lower()
    if resp != "s":
        raise SystemExit("Cancelado. Nada foi alterado.")

memory_json._cmd("SET", memory_json.CHAVE, json.dumps(dados, ensure_ascii=False))
print("Memória enviada para o Redis.")
print("Seções:", ", ".join(dados.keys()))