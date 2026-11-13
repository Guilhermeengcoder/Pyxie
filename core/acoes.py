# =============================================================
# core/acoes.py — Fila de ações para o agente local (PC)
#
# O servidor só ENFILEIRA. Quem executa é o agente_local.py,
# rodando no PC, e só programas desta lista.
# =============================================================

import json
import time
import unicodedata
import uuid

from core import memory_json

FILA = "pyxie:acoes"
CHAVE_AGENTE = "pyxie:agente:visto"
PREFIXO_RESULTADO = "pyxie:acao:res:"

MAX_NA_FILA = 10
VALIDADE_S = 60          # o agente ignora pedidos mais velhos que isso

# Mesmos nomes de PROGRAMAS em modules/launcher.py.
PROGRAMAS = {
    "chrome": "Chrome",
    "spotify": "Spotify",
    "vscode": "VS Code",
    "edge": "Edge",
    "notepad": "Bloco de Notas",
    "calculadora": "Calculadora",
}

ALIASES = {
    "chrome": "chrome", "google chrome": "chrome",
    "spotify": "spotify",
    "vscode": "vscode", "vs code": "vscode", "visual studio code": "vscode",
    "edge": "edge", "microsoft edge": "edge",
    "bloco de notas": "notepad", "notepad": "notepad",
    "calculadora": "calculadora",
}


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return t.encode("ascii", "ignore").decode().strip()


def resolver(nome):
    """Nome falado -> id da lista permitida, ou None."""
    return ALIASES.get(_norm(nome))


def lista_falada() -> str:
    return ", ".join(PROGRAMAS.values())


def agente_ativo() -> bool:
    return memory_json._cmd("GET", CHAVE_AGENTE) is not None


def enfileirar(programa: str) -> str:
    """Enfileira 'abrir programa'. Levanta ValueError se não puder."""
    if not memory_json._remoto():
        raise ValueError("a fila precisa do Redis configurado")
    if programa not in PROGRAMAS:
        raise ValueError("programa fora da lista permitida")
    if int(memory_json._cmd("LLEN", FILA) or 0) >= MAX_NA_FILA:
        raise ValueError("há pedidos demais na fila")

    item = {
        "id": uuid.uuid4().hex[:8],
        "acao": "abrir",
        "alvo": programa,
        "criado": time.time(),
    }
    memory_json._cmd("LPUSH", FILA, json.dumps(item))
    return item["id"]


def esperar_resultado(acao_id: str, timeout_s: float = 10.0):
    """Texto que o agente deixou, ou None se não confirmou a tempo."""
    limite = time.time() + timeout_s
    while time.time() < limite:
        valor = memory_json._cmd("GET", PREFIXO_RESULTADO + acao_id)
        if valor is not None:
            return str(valor)
        time.sleep(1)
    return None