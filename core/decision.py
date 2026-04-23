# =============================================================
# core/decision.py — Roteador Central da PYXIE v2.1
# Melhorias:
# - Redução de falsos positivos (web)
# - Suporte a contexto
# - Base para sistema de confiança
# =============================================================

import re
import unicodedata


# =============================================================
# NORMALIZAÇÃO
# =============================================================

def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    for c in ["?", "!", ".", ","]:
        texto = texto.replace(c, "")
    return texto


# =============================================================
# CHECAGENS
# =============================================================

def _checar_hora(msg: str):
    padroes_hora = [
        r"^que horas (sao|são|e|é)$",
        r"^qual (a hora|o horario|o dia|a data)( atual)?$",
        r"^(que dia|que data) (e|é) hoje$",
        r"^hoje e (segunda|terca|quarta|quinta|sexta|sabado|domingo)",
        r"^(me diz|me diga|fala) (a hora|as horas|que horas|que dia)$",
        r"^qual e a data de hoje$",
    ]

    for padrao in padroes_hora:
        if re.search(padrao, msg):
            return 1.0

    palavras = msg.split()
    if len(palavras) <= 3:
        if "hora" in palavras or "horas" in palavras:
            return 0.8
        if "dia" in palavras and "hoje" in palavras:
            return 0.8

    return 0.0


def _checar_saudacao(msg: str):
    saudacoes_exatas = {
        "oi", "ola", "opa", "eai", "e ai",
        "fala", "salve", "oi tudo bem", "ola tudo bem"
    }

    cumprimentos_inicio = ["bom dia", "boa tarde", "boa noite"]

    if msg in saudacoes_exatas:
        return 1.0

    for c in cumprimentos_inicio:
        if msg.startswith(c):
            return 0.9

    palavras = msg.split()
    if palavras:
        if palavras[0] in {"salve", "oi", "ola", "eai", "fala"} and len(palavras) <= 6:
            return 0.7

    return 0.0


def _checar_identidade(msg: str):
    padroes = [
        "quem e voce", "qual seu nome",
        "se apresente", "quem te criou",
        "voce e uma ia", "voce e um robo"
    ]

    for p in padroes:
        if p in msg:
            return 1.0

    return 0.0


def _checar_calculo(msg: str):
    padroes = [
        r"calcul[ae]",
        r"quanto e \d",
        r"resultado de",
        r"\d+\s*[\+\-\*\/]\s*\d+",
    ]

    for p in padroes:
        if re.search(p, msg):
            return 1.0

    return 0.0


def _checar_memoria(msg: str):
    triggers = [
        "lembre que", "guarde que", "memorize que",
        "anota que", "liste memorias",
        "o que voce lembra", "esqueca"
    ]

    for t in triggers:
        if t in msg:
            return 1.0

    return 0.0


def _checar_pesquisa_explicita(msg: str):
    inicios = [
        "pesquise", "procure", "busque",
        "pesquise sobre", "procure sobre"
    ]

    if any(msg.startswith(i) for i in inicios):
        return 1.0

    return 0.0


def _checar_pergunta_web(msg: str):
    """
    Agora só ativa se COMEÇAR com padrão — evita falso positivo
    """

    inicios = [
        "quem foi", "quem e",
        "o que e", "o que foi",
        "quando foi", "onde fica",
        "como funciona", "explique",
        "me explique", "qual foi",
        "quanto tempo durou",
        "em que ano"
    ]

    if any(msg.startswith(i) for i in inicios):
        return 0.9

    return 0.0


def _checar_lembrete(msg: str):
    if re.search(r"(lembra|lembre|avisa).*(as|às)\s*\d{1,2}", msg):
        return 1.0
    if "lembrete" in msg:
        return 0.8
    return 0.0


# =============================================================
# MAPA DE REGRAS
# =============================================================

REGRAS = {
    "internet_explicita": _checar_pesquisa_explicita,
    "memoria": _checar_memoria,
    "lembrete": _checar_lembrete,
    "calculo": _checar_calculo,
    "identidade": _checar_identidade,
    "saudacao": _checar_saudacao,
    "hora": _checar_hora,
    "internet": _checar_pergunta_web,
}


# =============================================================
# DECISÃO COM CONTEXTO
# =============================================================

def decidir(mensagem: str, contexto: dict = None) -> dict:
    msg_norm = normalizar(mensagem)
    contexto = contexto or {}

    pontuacoes = {}

    for nome, regra in REGRAS.items():
        score = regra(msg_norm)
        if score > 0:
            pontuacoes[nome] = score

    # 🔥 CONTEXTO: continuidade de conversa
    if contexto.get("ultimo_destino") == "internet":
        if msg_norm.startswith(("e ", "e onde", "e quando", "e como")):
            pontuacoes["internet"] = max(pontuacoes.get("internet", 0), 0.85)

    if not pontuacoes:
        return {
            "destino": "ollama",
            "confianca": 0.0,
            "regra": "fallback",
            "msg_norm": msg_norm,
        }

    destino = max(pontuacoes, key=pontuacoes.get)

    return {
        "destino": destino,
        "confianca": pontuacoes[destino],
        "regra": destino,
        "msg_norm": msg_norm,
    }