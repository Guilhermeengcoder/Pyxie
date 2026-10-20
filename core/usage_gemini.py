# =============================================================
# core/usage_gemini.py — Contagem LOCAL de uso do Gemini
#
# É estimativa: conta as respostas bem-sucedidas que ESTE app
# recebeu, não o saldo oficial do Google. Guarda só números.
# O dia vira à meia-noite do horário do Pacífico (como o RPD).
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

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "gemini_uso.json"
PREFIXO_CHAVE = "pyxie:gemini_uso:"
TTL_S = 3 * 24 * 3600

_lock = threading.RLock()
_mem = {"dia": None, "pedidos": 0, "tokens": 0}  # último recurso


def _limite(nome):
    try:
        v = int((os.getenv(nome) or "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _agora_pacifico():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        # Sem tzdata: aproximação fixa (ignora horário de verão).
        return datetime.now(timezone(timedelta(hours=-8)))


def _dia_e_reset():
    agora = _agora_pacifico()
    proxima = (agora + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return agora.strftime("%Y-%m-%d"), (proxima - agora).total_seconds()


# ---------------- armazenamento ----------------

def _somar_remoto(dia, tokens):
    chave = PREFIXO_CHAVE + dia
    memory_json._cmd("HINCRBY", chave, "pedidos", 1)
    memory_json._cmd("HINCRBY", chave, "tokens", tokens)
    memory_json._cmd("EXPIRE", chave, TTL_S)


def _ler_remoto(dia):
    bruto = memory_json._cmd("HGETALL", PREFIXO_CHAVE + dia)
    if isinstance(bruto, dict):
        dados = bruto
    elif isinstance(bruto, list):
        dados = dict(zip(bruto[::2], bruto[1::2]))
    else:
        dados = {}
    return int(dados.get("pedidos", 0)), int(dados.get("tokens", 0))


def _ler_local(dia):
    try:
        with ARQUIVO.open("r", encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return 0, 0
    if d.get("dia") != dia:
        return 0, 0
    return int(d.get("pedidos", 0)), int(d.get("tokens", 0))


def _somar_local(dia, tokens):
    pedidos, total = _ler_local(dia)
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("w", encoding="utf-8") as f:
        json.dump(
            {"dia": dia, "pedidos": pedidos + 1, "tokens": total + tokens}, f
        )


# ---------------- interface pública ----------------

def tokens_da_interacao(interaction, prompt: str = "") -> int:
    """Tokens reais (usage.total_tokens); sem eles, estima pelo tamanho."""
    usage = getattr(interaction, "usage", None)

    total = getattr(usage, "total_tokens", None)
    if isinstance(total, int) and total > 0:
        return total

    soma = sum(
        (getattr(usage, campo, 0) or 0)
        for campo in (
            "total_input_tokens",
            "total_output_tokens",
            "total_thought_tokens",
        )
    )
    if soma > 0:
        return soma

    saida = getattr(interaction, "output_text", "") or ""
    return (len(prompt) + len(saida)) // 3  # estimativa grosseira


def registrar(tokens: int):
    dia, _ = _dia_e_reset()
    tokens = max(0, int(tokens or 0))

    with _lock:
        if _mem["dia"] != dia:
            _mem.update(dia=dia, pedidos=0, tokens=0)
        _mem["pedidos"] += 1
        _mem["tokens"] += tokens

        try:
            if memory_json._remoto():
                _somar_remoto(dia, tokens)
            else:
                _somar_local(dia, tokens)
        except (requests.RequestException, OSError, ValueError) as e:
            print(f"[usage_gemini] não consegui gravar: {e}")


def obter(modelo: str = "") -> dict:
    dia, reset_s = _dia_e_reset()

    try:
        if memory_json._remoto():
            pedidos, tokens = _ler_remoto(dia)
        else:
            pedidos, tokens = _ler_local(dia)
    except (requests.RequestException, OSError, ValueError) as e:
        print(f"[usage_gemini] não consegui ler: {e}")
        pedidos, tokens = (
            (_mem["pedidos"], _mem["tokens"]) if _mem["dia"] == dia else (0, 0)
        )

    limite_p = _limite("GEMINI_LIMITE_PEDIDOS_DIA")
    limite_t = _limite("GEMINI_LIMITE_TOKENS_DIA")

    return {
        "provedor": "gemini",
        "modelo": modelo or os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "pedidos_usados": pedidos,
        "pedidos_limite": limite_p,
        "pedidos_restantes": (
            max(0, limite_p - pedidos) if limite_p else None
        ),
        "tokens_usados": tokens,
        "tokens_limite": limite_t,
        "tokens_restantes": (
            max(0, limite_t - tokens) if limite_t else None
        ),
        "reset_s": reset_s,
        "estimativa": True,
    }