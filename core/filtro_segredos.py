# =============================================================
# core/filtro_segredos.py — Detecta chaves e senhas em texto
#
# Roda antes de enviar qualquer coisa a um provedor sem confiança.
# Devolve só o TIPO do que achou, nunca o valor.
# Prefere errar para o lado de bloquear: um falso positivo só
# pede para o usuário remover o trecho.
# =============================================================

import re

_PADROES = [
    ("chave gsk_", r"\bgsk_[A-Za-z0-9]{20,}"),
    ("chave sk-", r"\bsk-[A-Za-z0-9_-]{20,}"),
    ("chave do Google (AIza)", r"\bAIza[0-9A-Za-z_-]{30,}"),
    ("token do GitHub", r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    ("chave da AWS", r"\bAKIA[0-9A-Z]{16}\b"),
    ("chave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    (
        "atribuição com valor literal",
        r"(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|senha)\w*[\"']?\s*[=:]\s*[\"'][^\"'\s]{8,}[\"']",
    ),
    (
        "linha de .env com valor",
        r"(?m)^\s*(?:export\s+)?[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|SENHA)[A-Z0-9_]*\s*=\s*[^\s\"'(]{8,}\s*$",
    ),
]

_COMPILADOS = [(nome, re.compile(p)) for nome, p in _PADROES]


def detectar_segredos(texto: str) -> list:
    """Lista os tipos de segredo encontrados (vazia se não achar nada)."""
    texto = str(texto or "")
    return [nome for nome, padrao in _COMPILADOS if padrao.search(texto)]