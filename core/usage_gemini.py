# =============================================================
# core/usage_gemini.py — Contagem LOCAL de uso do Gemini
#
# É estimativa: conta as respostas bem-sucedidas que ESTE app
# recebeu, não o saldo oficial do Google. Guarda só números.
# O dia vira à meia-noite do horário do Pacífico (como o RPD).
# Contagem separada por modelo (os limites do Google são por modelo).
# =============================================================

import json
import os
import re
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
_mem = {}  # último recurso: {modelo: {"dia", "pedidos", "tokens"}}
_ultimo_modelo = None


def _limite(nome):
    try:
        v = int((os.getenv(nome) or "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _sufixo(modelo):
    # Lite usa GEMINI_LIMITE_PEDIDOS_DIA_LITE; os demais, o nome sem sufixo.
    return "_LITE" if "lite" in (modelo or "").lower() else ""


def _arquivo(modelo):
    seguro = re.sub(r"[^A-Za-z0-9_.-]", "_", modelo or "padrao")
    return ARQUIVO.with_name(f"gemini_uso_{seguro}.json")


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

def _somar_remoto(modelo, dia, tokens):
    chave = f"{PREFIXO_CHAVE}{modelo}:{dia}"
    memory_json._cmd("HINCRBY", chave, "pedidos", 1)
    memory_json._cmd("HINCRBY", chave, "tokens", tokens)
    memory_json._cmd("EXPIRE", chave, TTL_S)


def _ler_remoto(modelo, dia):
    bruto = memory_json._cmd("HGETALL", f"{PREFIXO_CHAVE}{modelo}:{dia}")
    if isinstance(bruto, dict):
        dados = bruto
    elif isinstance(bruto, list):
        dados = dict(zip(bruto[::2], bruto[1::2]))
    else:
        dados = {}
    return int(dados.get("pedidos", 0)), int(dados.get("tokens", 0))


def _ler_local(modelo, dia):
    try:
        with _arquivo(modelo).open("r", encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return 0, 0
    if d.get("dia") != dia:
        return 0, 0
    return int(d.get("pedidos", 0)), int(d.get("tokens", 0))


def _somar_local(modelo, dia, tokens):
    pedidos, total = _ler_local(modelo, dia)
    arq = _arquivo(modelo)
    arq.parent.mkdir(parents=True, exist_ok=True)
    with arq.open("w", encoding="utf-8") as f:
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


def registrar(tokens: int, modelo: str = ""):
    global _ultimo_modelo
    modelo = modelo or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    dia, _ = _dia_e_reset()
    tokens = max(0, int(tokens or 0))

    with _lock:
        _ultimo_modelo = modelo
        atual = _mem.get(modelo)
        if not atual or atual["dia"] != dia:
            atual = {"dia": dia, "pedidos": 0, "tokens": 0}
            _mem[modelo] = atual
        atual["pedidos"] += 1
        atual["tokens"] += tokens

        try:
            if memory_json._remoto():
                _somar_remoto(modelo, dia, tokens)
            else:
                _somar_local(modelo, dia, tokens)
        except (requests.RequestException, OSError, ValueError) as e:
            print(f"[usage_gemini] não consegui gravar: {e}")


def obter(modelo: str = "") -> dict:
    modelo = (
        modelo
        or _ultimo_modelo
        or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    )
    dia, reset_s = _dia_e_reset()

    try:
        if memory_json._remoto():
            pedidos, tokens = _ler_remoto(modelo, dia)
        else:
            pedidos, tokens = _ler_local(modelo, dia)
    except (requests.RequestException, OSError, ValueError) as e:
        print(f"[usage_gemini] não consegui ler: {e}")
        m = _mem.get(modelo)
        pedidos, tokens = (
            (m["pedidos"], m["tokens"]) if m and m["dia"] == dia else (0, 0)
        )

    suf = _sufixo(modelo)
    limite_p = _limite("GEMINI_LIMITE_PEDIDOS_DIA" + suf)
    limite_t = _limite("GEMINI_LIMITE_TOKENS_DIA" + suf)

    return {
        "provedor": "gemini",
        "modelo": modelo,
        "pedidos_usados": pedidos,
        "pedidos_limite": limite_p,
        "pedidos_restantes": max(0, limite_p - pedidos) if limite_p else None,
        "tokens_usados": tokens,
        "tokens_limite": limite_t,
        "tokens_restantes": max(0, limite_t - tokens) if limite_t else None,
        "reset_s": reset_s,
        "estimativa": True,
    }