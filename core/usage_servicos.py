# =============================================================
# core/usage_servicos.py — Contagem LOCAL de uso de serviços externos
#
# Tavily, Firecrawl e Cloudflare. É estimativa: conta o que ESTE
# app registrou, não o saldo oficial do serviço. Guarda só números.
# Mesmo padrão do usage_gemini.py (Redis, ou arquivo local).
# =============================================================

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from dotenv import load_dotenv

load_dotenv()

from core import memory_json

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "servicos_uso.json"
PREFIXO_CHAVE = "pyxie:servico_uso:"
TTL_S = 62 * 24 * 3600

# periodo: "mes" e "dia" resetam em UTC; "total" nunca reseta.
# Confira o seu plano e ajuste o limite pelas variáveis do .env.
SERVICOS = {
    "tavily": {
        "periodo": "mes", "unidade": "créditos", "limite_env": "TAVILY_LIMITE_MES",
    },
    "firecrawl": {
        "periodo": (os.getenv("FIRECRAWL_PERIODO", "total") or "total").strip().lower(),
        "unidade": "créditos", "limite_env": "FIRECRAWL_LIMITE",
    },
    "cloudflare": {
        "periodo": "dia", "unidade": "neurônios", "limite_env": "CLOUDFLARE_LIMITE_DIA",
    },
}

_lock = threading.RLock()
_mem = {}  # último recurso: {servico: {"chave", "pedidos", "unidades"}}


def _limite(nome_env):
    try:
        v = int((os.getenv(nome_env) or "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _dia_ciclo() -> int:
    try:
        return min(28, max(1, int(os.getenv("FIRECRAWL_DIA_CICLO", "1"))))
    except ValueError:
        return 1


def _periodo(servico):
    """Devolve (chave do período, segundos até o reset ou None)."""
    agora = datetime.now(timezone.utc)
    tipo = SERVICOS[servico]["periodo"]

    if tipo == "mes":
        proximo = (
            agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            + timedelta(days=32)
        ).replace(day=1)
        return agora.strftime("%Y-%m"), (proximo - agora).total_seconds()

    if tipo == "ciclo":
        # Ciclo de cobrança que renova num dia fixo do mês (ex.: dia 22).
        dia = _dia_ciclo()
        inicio = agora.replace(
            day=dia, hour=0, minute=0, second=0, microsecond=0
        )
        if agora < inicio:
            # Ainda não chegou o dia deste mês: o ciclo começou no mês anterior.
            inicio = (inicio - timedelta(days=1)).replace(day=dia)
        proximo = (inicio + timedelta(days=32)).replace(day=dia)
        return inicio.strftime("%Y-%m-%d"), (proximo - agora).total_seconds()

    if tipo == "dia":
        proximo = (agora + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return agora.strftime("%Y-%m-%d"), (proximo - agora).total_seconds()

    return "total", None


# ---------------- armazenamento ----------------

def _chave_redis(servico, chave):
    return f"{PREFIXO_CHAVE}{servico}:{chave}"


def _somar_remoto(servico, chave, unidades):
    k = _chave_redis(servico, chave)
    memory_json._cmd("HINCRBY", k, "pedidos", 1)
    memory_json._cmd("HINCRBY", k, "unidades", unidades)
    if SERVICOS[servico]["periodo"] != "total":
        memory_json._cmd("EXPIRE", k, TTL_S)


def _ler_remoto(servico, chave):
    bruto = memory_json._cmd("HGETALL", _chave_redis(servico, chave))
    if isinstance(bruto, dict):
        dados = bruto
    elif isinstance(bruto, list):
        dados = dict(zip(bruto[::2], bruto[1::2]))
    else:
        dados = {}
    return int(dados.get("pedidos", 0)), int(dados.get("unidades", 0))


def _ler_arquivo():
    try:
        with ARQUIVO.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _ler_local(servico, chave):
    item = _ler_arquivo().get(servico) or {}
    if item.get("chave") != chave:
        return 0, 0
    return int(item.get("pedidos", 0)), int(item.get("unidades", 0))


def _somar_local(servico, chave, unidades):
    pedidos, total = _ler_local(servico, chave)
    todos = _ler_arquivo()
    todos[servico] = {
        "chave": chave,
        "pedidos": pedidos + 1,
        "unidades": total + unidades,
    }
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("w", encoding="utf-8") as f:
        json.dump(todos, f)


# ---------------- interface pública ----------------

def registrar(servico: str, unidades=1):
    """Soma 1 pedido e `unidades` (créditos/neurônios) ao período atual."""
    if servico not in SERVICOS:
        return

    chave, _ = _periodo(servico)

    try:
        unidades = max(0, int(round(float(unidades or 0))))
    except (TypeError, ValueError):
        unidades = 0

    with _lock:
        atual = _mem.get(servico)
        if not atual or atual["chave"] != chave:
            atual = {"chave": chave, "pedidos": 0, "unidades": 0}
            _mem[servico] = atual
        atual["pedidos"] += 1
        atual["unidades"] += unidades

        try:
            if memory_json._remoto():
                _somar_remoto(servico, chave, unidades)
            else:
                _somar_local(servico, chave, unidades)
        except (requests.RequestException, OSError, ValueError) as e:
            print(f"[usage_servicos] não consegui gravar ({servico}): {e}")


def obter(servico: str) -> dict:
    chave, reset_s = _periodo(servico)
    cfg = SERVICOS[servico]

    try:
        if memory_json._remoto():
            pedidos, usadas = _ler_remoto(servico, chave)
        else:
            pedidos, usadas = _ler_local(servico, chave)
    except (requests.RequestException, OSError, ValueError) as e:
        print(f"[usage_servicos] não consegui ler ({servico}): {e}")
        m = _mem.get(servico)
        pedidos, usadas = (
            (m["pedidos"], m["unidades"]) if m and m["chave"] == chave else (0, 0)
        )

    limite = _limite(cfg["limite_env"])

    return {
        "provedor": servico,
        "unidade": cfg["unidade"],
        "periodo": cfg["periodo"],
        "pedidos": pedidos,
        "usadas": usadas,
        "limite": limite,
        "restantes": max(0, limite - usadas) if limite else None,
        "reset_s": reset_s,
        "estimativa": True,
    }


def obter_todos() -> dict:
    return {nome: obter(nome) for nome in SERVICOS}