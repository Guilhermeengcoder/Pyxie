# =============================================================
# core/llm_config.py — Modo do LLM (Groq / Gemini / Auto) e pausas
#
# Guarda no Redis (chave pyxie:llm_config); sem Redis, em
# data/llm_config.json; em último caso, na memória do processo.
# Não contém dados pessoais: só o modo e horários de pausa.
# =============================================================

import json
import threading
import time
from pathlib import Path

import requests

from core import memory_json
from core.llm_erros import ErroCota, ErroIndisponivel

CHAVE = "pyxie:llm_config"
ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "llm_config.json"

MODOS = ("groq", "gemini", "auto")

CACHE_S = 5                    # quanto tempo o estado lido fica em cache
PAUSA_INDISPONIVEL_S = 60      # padrão quando o provedor não informa espera
PAUSA_COTA_S = 3600
PAUSA_MAXIMA_S = 24 * 3600     # teto, por segurança

_lock = threading.RLock()
_cache = None
_cache_ate = 0.0
_ultimo_conhecido = None       # último recurso se Redis e arquivo falharem


def _normalizar(dados) -> dict:
    if not isinstance(dados, dict):
        dados = {}

    modo = dados.get("modo")
    if modo not in MODOS:
        modo = "groq"

    pausas = {}
    brutas = dados.get("pausas")
    if isinstance(brutas, dict):
        for nome, ate in brutas.items():
            try:
                pausas[str(nome)] = float(ate)
            except (TypeError, ValueError):
                pass

    return {"modo": modo, "pausas": pausas}


def _ler() -> dict:
    """Lê direto do armazenamento (sem cache)."""
    global _ultimo_conhecido

    try:
        if memory_json._remoto():
            bruto = memory_json._cmd("GET", CHAVE)
            dados = _normalizar(json.loads(bruto) if bruto else {})
        else:
            try:
                with ARQUIVO.open("r", encoding="utf-8") as f:
                    dados = _normalizar(json.load(f))
            except FileNotFoundError:
                dados = _normalizar({})

        _ultimo_conhecido = dados
        return dados

    except (requests.RequestException, OSError, ValueError) as e:
        print(f"[llm_config] não consegui ler o estado: {e}")
        return _normalizar(_ultimo_conhecido)


def _gravar(dados: dict):
    global _ultimo_conhecido

    _ultimo_conhecido = dados

    try:
        if memory_json._remoto():
            memory_json._cmd("SET", CHAVE, json.dumps(dados))
        else:
            ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
            with ARQUIVO.open("w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2)
    except (requests.RequestException, OSError, ValueError) as e:
        # O estado continua valendo na memória do processo.
        print(f"[llm_config] não consegui gravar o estado: {e}")


def invalidar_cache():
    global _cache, _cache_ate
    _cache = None
    _cache_ate = 0.0


def carregar() -> dict:
    """Estado atual, com cache curto."""
    global _cache, _cache_ate

    with _lock:
        agora = time.time()
        if _cache is not None and agora < _cache_ate:
            return _cache

        _cache = _ler()
        _cache_ate = agora + CACHE_S
        return _cache


def obter_modo() -> str:
    return carregar()["modo"]


def definir_modo(modo: str) -> str:
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo!r}")

    with _lock:
        dados = _ler()
        dados["modo"] = modo
        _gravar(dados)
        invalidar_cache()

    return modo


def pausar(provedor: str, erro) -> float:
    """
    Põe o provedor em pausa depois de ErroCota ou ErroIndisponivel.
    Usa erro.espera_s quando existir; senão, o padrão do tipo.
    Devolve os segundos de pausa (0 se o erro não justifica pausa).
    """
    if isinstance(erro, ErroCota):
        padrao = PAUSA_COTA_S
    elif isinstance(erro, ErroIndisponivel):
        padrao = PAUSA_INDISPONIVEL_S
    else:
        return 0.0

    segundos = getattr(erro, "espera_s", None) or padrao
    segundos = max(1.0, min(float(segundos), PAUSA_MAXIMA_S))

    with _lock:
        dados = _ler()
        dados["pausas"][provedor] = time.time() + segundos
        _gravar(dados)
        invalidar_cache()

    return segundos


def segundos_de_pausa(provedor: str) -> float:
    ate = carregar()["pausas"].get(provedor, 0.0)
    return max(0.0, ate - time.time())


def em_pausa(provedor: str) -> bool:
    return segundos_de_pausa(provedor) > 0


def limpar_pausa(provedor: str):
    with _lock:
        dados = _ler()
        dados["pausas"].pop(provedor, None)
        _gravar(dados)
        invalidar_cache()