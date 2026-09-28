# =============================================================
# modules/groq_uso.py — Uso e limites da conta Groq
#
# A Groq devolve, em TODA resposta (sem custo ou chamada extra),
# cabecalhos x-ratelimit-* dizendo quanto ainda da pra usar:
#
#   x-ratelimit-limit-tokens        -> limite de tokens POR MINUTO
#   x-ratelimit-remaining-tokens    -> tokens restantes nesse minuto
#   x-ratelimit-reset-tokens        -> quando o minuto reseta (ex.: "7.6s")
#   x-ratelimit-limit-requests      -> limite de pedidos POR DIA
#   x-ratelimit-remaining-requests  -> pedidos restantes hoje
#   x-ratelimit-reset-requests      -> quando o dia reseta
#
# IMPORTANTE: cada MODELO tem seu proprio limite. Como a PYXIE usa um
# modelo para texto e outro para imagem, este modulo guarda sempre o
# resultado da ULTIMA chamada feita (texto ou imagem), marcado com o
# nome do modelo usado - nao existe um "total combinado" real.
# =============================================================

import threading
import time

_trava = threading.Lock()

_estado = {
    "modelo": None,
    "tokens_limite": None,
    "tokens_restantes": None,
    "tokens_reset": None,
    "requests_limite": None,
    "requests_restantes": None,
    "requests_reset": None,
    "atualizado_em": None,
}


def _para_int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def registrar_headers(headers, modelo: str):
    """
    Le os cabecalhos x-ratelimit-* de uma resposta da Groq e atualiza
    o estado global. Chamado logo apos toda chamada bem-sucedida
    (texto ou imagem).
    """
    with _trava:
        _estado["modelo"] = modelo
        _estado["tokens_limite"] = _para_int(headers.get("x-ratelimit-limit-tokens"))
        _estado["tokens_restantes"] = _para_int(
            headers.get("x-ratelimit-remaining-tokens")
        )
        _estado["tokens_reset"] = headers.get("x-ratelimit-reset-tokens")
        _estado["requests_limite"] = _para_int(
            headers.get("x-ratelimit-limit-requests")
        )
        _estado["requests_restantes"] = _para_int(
            headers.get("x-ratelimit-remaining-requests")
        )
        _estado["requests_reset"] = headers.get("x-ratelimit-reset-requests")
        _estado["atualizado_em"] = time.time()


def obter_uso() -> dict:
    """Retorna uma copia do ultimo estado de uso conhecido (pode ter campos None se ainda nao houve nenhuma chamada)."""
    with _trava:
        return dict(_estado)
