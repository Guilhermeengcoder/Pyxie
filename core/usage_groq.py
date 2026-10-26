# =============================================================
# core/usage_groq.py — Contagem LOCAL de tokens por dia do Groq
#
# O Groq não envia o limite diário de tokens (TPD) nos cabeçalhos,
# então este módulo soma os tokens das respostas que ESTE app recebeu.
# É estimativa: não inclui usos feitos fora do app (testes, outros
# scripts) e o reset real pode diferir do dia UTC.
# Defina GROQ_LIMITE_TOKENS_DIA no .env para ver a barra.
# =============================================================

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from core import memory_json

load_dotenv()

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "groq_uso.json"
PREFIXO_CHAVE = "pyxie:groq_uso:"
TTL_S = 3 * 24 * 3600

_lock = threading.RLock()
_mem = {}  # {modelo: {"dia", "pedidos", "tokens"}}


def _limite():
    try:
        v = int((os.getenv("GROQ_LIMITE_TOKENS_DIA") or "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _dia_e_reset():
    agora = datetime.now(timezone.utc)
    proxima = (agora + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return agora.strftime("%Y-%m-%d"), (proxima - agora).total_seconds()


def _chave(modelo, dia):
    return f"{PREFIXO_CHAVE}{modelo}:{dia}"


def _ler_arquivo():
    try:
        with ARQUIVO.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def registrar(modelo: str, tokens: int):
    dia, _ = _dia_e_reset()
    tokens = max(0, int(tokens or 0))

    with _lock:
        atual = _mem.get(modelo)
        if not atual or atual["dia"] != dia:
            atual = {"dia": dia, "pedidos": 0, "tokens": 0}
            _mem[modelo] = atual
        atual["pedidos"] += 1
        atual["tokens"] += tokens

        try:
            if memory_json._remoto():
                k = _chave(modelo, dia)
                memory_json._cmd("HINCRBY", k, "pedidos", 1)
                memory_json._cmd("HINCRBY", k, "tokens", tokens)
                memory_json._cmd("EXPIRE", k, TTL_S)
            else:
                todos = _ler_arquivo()
                item = todos.get(modelo) or {}
                if item.get("dia") != dia:
                    item = {"dia": dia, "pedidos": 0, "tokens": 0}
                item["pedidos"] += 1
                item["tokens"] += tokens
                todos[modelo] = item
                ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
                with ARQUIVO.open("w", encoding="utf-8") as f:
                    json.dump(todos, f)
        except (requests.RequestException, OSError, ValueError) as e:
            print(f"[usage_groq] não consegui gravar: {e}")


def obter(modelo: str) -> dict:
    dia, reset_s = _dia_e_reset()

    try:
        if memory_json._remoto():
            bruto = memory_json._cmd("HGETALL", _chave(modelo, dia))
            if isinstance(bruto, dict):
                dados = bruto
            elif isinstance(bruto, list):
                dados = dict(zip(bruto[::2], bruto[1::2]))
            else:
                dados = {}
            pedidos = int(dados.get("pedidos", 0))
            tokens = int(dados.get("tokens", 0))
        else:
            item = _ler_arquivo().get(modelo) or {}
            if item.get("dia") == dia:
                pedidos, tokens = int(item.get("pedidos", 0)), int(item.get("tokens", 0))
            else:
                pedidos, tokens = 0, 0
    except (requests.RequestException, OSError, ValueError) as e:
        print(f"[usage_groq] não consegui ler: {e}")
        m = _mem.get(modelo)
        pedidos, tokens = (
            (m["pedidos"], m["tokens"]) if m and m["dia"] == dia else (0, 0)
        )

    limite = _limite()

    return {
        "tokens_dia_usados": tokens,
        "tokens_dia_limite": limite,
        "tokens_dia_restantes": max(0, limite - tokens) if limite else None,
        "pedidos_dia_contados": pedidos,
        "reset_dia_s": reset_s,
    }