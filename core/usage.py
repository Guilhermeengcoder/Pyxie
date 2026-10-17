import threading
import time

_lock = threading.Lock()

_ultimo = {
    "modelo": None,
    "tokens_limite": None,
    "tokens_restantes": None,
    "tokens_reset": None,
    "requests_limite": None,
    "requests_restantes": None,
    "requests_reset": None,
    "atualizado_em": None,
}


def _int(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def registrar_headers(headers, modelo):
    """Guarda o último estado de limites informado pela Groq nos headers."""
    if headers is None:
        return

    def g(nome):
        return headers.get(nome)

    with _lock:
        _ultimo.update({
            "modelo": modelo,
            "tokens_limite": _int(g("x-ratelimit-limit-tokens")),
            "tokens_restantes": _int(g("x-ratelimit-remaining-tokens")),
            "tokens_reset": g("x-ratelimit-reset-tokens"),
            "requests_limite": _int(g("x-ratelimit-limit-requests")),
            "requests_restantes": _int(g("x-ratelimit-remaining-requests")),
            "requests_reset": g("x-ratelimit-reset-requests"),
            "atualizado_em": time.time(),
        })


def ultimo():
    with _lock:
        dados = dict(_ultimo)

    # Quantos segundos se passaram desde que esse dado foi registrado
    # (o front desconta isso do tempo de reset).
    if dados["atualizado_em"] is not None:
        dados["idade_s"] = max(0.0, time.time() - dados["atualizado_em"])
    else:
        dados["idade_s"] = 0.0

    return dados