# =============================================================
# core/reminder.py — Lembretes persistentes
#
# Redis (ZSET "pyxie:lembretes", score = momento em epoch UTC);
# sem Redis, arquivo data/lembretes.json.
# Cada lembrete: {"id", "texto", "quando"}.
# =============================================================

import json
import threading
import time
import unicodedata
import uuid
from pathlib import Path

from core import memory_json

CHAVE = "pyxie:lembretes"
ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "lembretes.json"

MAX_PENDENTES = 50
MAX_TEXTO = 200

_lock = threading.RLock()


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return t.encode("ascii", "ignore").decode().strip()


# ---------------- arquivo local ----------------

def _ler_local() -> list:
    try:
        with ARQUIVO.open("r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def _gravar_local(itens: list):
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False, indent=2)


# ---------------- interface pública ----------------

def adicionar(texto: str, quando: float) -> str:
    """Agenda um lembrete para `quando` (epoch). Devolve o id.
    Levanta ValueError (limites) ou requests.RequestException (Redis)."""
    texto = str(texto or "").strip()[:MAX_TEXTO]
    if not texto:
        raise ValueError("lembrete vazio")

    item = {"id": uuid.uuid4().hex[:6], "texto": texto, "quando": float(quando)}

    with _lock:
        if len(listar()) >= MAX_PENDENTES:
            raise ValueError("lembretes demais pendentes")

        if memory_json._remoto():
            memory_json._cmd(
                "ZADD", CHAVE, item["quando"],
                json.dumps(item, ensure_ascii=False),
            )
        else:
            itens = _ler_local()
            itens.append(item)
            _gravar_local(itens)

    return item["id"]


def listar() -> list:
    """Pendentes, do mais próximo ao mais distante."""
    if memory_json._remoto():
        brutos = memory_json._cmd("ZRANGE", CHAVE, 0, -1) or []
        itens = []
        for b in brutos:
            try:
                itens.append(json.loads(b))
            except ValueError:
                pass
    else:
        itens = _ler_local()
    return sorted(itens, key=lambda i: i.get("quando", 0))


def cancelar(trecho: str) -> list:
    """Cancela os lembretes cujo id é igual ou cujo texto contém `trecho`.
    Devolve os textos cancelados."""
    alvo = _norm(trecho)
    if not alvo:
        return []

    with _lock:
        escolhidos = [
            i for i in listar()
            if i.get("id") == alvo or alvo in _norm(i.get("texto"))
        ]
        if not escolhidos:
            return []

        if memory_json._remoto():
            for i in escolhidos:
                memory_json._cmd("ZREM", CHAVE, json.dumps(i, ensure_ascii=False))
        else:
            ids = {i["id"] for i in escolhidos}
            _gravar_local([i for i in _ler_local() if i.get("id") not in ids])

    return [i["texto"] for i in escolhidos]


def pegar_vencidos() -> list:
    """Remove e devolve os lembretes já vencidos (cada um sai uma só vez)."""
    agora = time.time()

    if memory_json._remoto():
        brutos = memory_json._cmd("ZRANGEBYSCORE", CHAVE, "-inf", agora) or []
        vencidos = []
        for b in brutos:
            # ZREM devolve 1 só para quem removeu: evita entrega dupla.
            if memory_json._cmd("ZREM", CHAVE, b) == 1:
                try:
                    vencidos.append(json.loads(b))
                except ValueError:
                    pass
        return vencidos

    with _lock:
        itens = _ler_local()
        vencidos = [i for i in itens if i.get("quando", 0) <= agora]
        if vencidos:
            _gravar_local([i for i in itens if i.get("quando", 0) > agora])
        return vencidos