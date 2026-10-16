import threading

_lock = threading.Lock()

_ultimo = {
    "modelo": None,
    "tokens_limite": None,
    "tokens_restantes": None,
    "tokens_reset": None,
    "requests_limite": None,
    "requests_restantes": None,
    "requests_reset": None,
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
        })


def ultimo():
    with _lock:
        return dict(_ultimo)