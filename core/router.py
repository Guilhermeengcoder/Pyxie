from core.nlp_intent import NLPIntent
from core.context import Context

nlp = NLPIntent()


# =========================
# REGRAS DE PRIORIDADE
# Cada regra retorna (modulo, confianca) ou None
# =========================

def _regra_keyword(msg: str):
    """Palavras-chave explícitas têm prioridade máxima."""
    kw_map = {
        "pesquise":    ("internet",  1.0),
        "procure":     ("internet",  1.0),
        "lembre que":  ("memoria",   1.0),
        "lembrar que": ("memoria",   1.0),
        "liste memorias": ("memoria_control", 1.0),
        "mostrar memorias": ("memoria_control", 1.0),
        "esqueca":     ("memoria_control", 1.0),
        "esqueça":     ("memoria_control", 1.0),
        "calcule":     ("calculo",   1.0),
        "quanto é":    ("calculo",   1.0),
        "hora":        ("hora",      1.0),
        "horas":       ("hora",      1.0),
        "que horas":   ("hora",      1.0),
        "bom dia":     ("saudacao",  1.0),
        "boa tarde":   ("saudacao",  1.0),
        "boa noite":   ("saudacao",  1.0),
        "quem é você": ("identidade", 1.0),
        "quem e voce": ("identidade", 1.0),
        "seu nome":    ("identidade", 1.0),
        "se apresente":("identidade", 1.0),
        "quem te criou":("identidade", 1.0),
    }
    for kw, resultado in kw_map.items():
        if kw in msg:
            return resultado
    return None


def _regra_saudacao(msg: str):
    """Mensagens curtas de saudação."""
    saudacoes = {"oi", "olá", "ola", "opa", "eai", "fala", "e aí"}
    if msg.strip() in saudacoes:
        return ("saudacao", 1.0)
    return None


def _regra_pergunta_web(msg: str):
    """Perguntas abertas que devem ir para a internet."""
    inicios = ["quem é", "quem foi", "o que é", "o que foi",
               "quando foi", "onde fica", "como funciona",
               "me fale sobre", "fale sobre", "quero saber sobre"]
    for inicio in inicios:
        if msg.startswith(inicio):
            return ("internet", 0.9)
    return None


def _regra_nlp(msg: str):
    """NLP semântico como segunda camada."""
    intent = nlp.detectar(msg)
    if intent:
        confianca = 0.75
        return (intent, confianca)
    return None


# =========================
# PIPELINE DE DECISÃO
# =========================

PIPELINE = [
    _regra_keyword,
    _regra_saudacao,
    _regra_pergunta_web,
    _regra_nlp,
]


def decidir(msg: str, context: Context = None) -> dict:
    """
    Analisa a mensagem e retorna uma decisão de roteamento.

    Retorna:
        {
            "modulo": str,       # nome do módulo destino
            "confianca": float,  # 0.0 a 1.0
            "regra": str,        # qual regra tomou a decisão
            "msg_limpa": str     # mensagem normalizada
        }
    """
    msg_norm = msg.lower().strip()

    # Resolve pronomes usando contexto
    if context:
        entity = context.get_entity() or context.get_topic()
        if entity:
            for pronome in ["ele", "ela", "isso", "esse", "essa", "dele", "dela"]:
                if pronome in msg_norm.split():
                    msg_norm = msg_norm.replace(pronome, entity)

    for regra in PIPELINE:
        resultado = regra(msg_norm)
        if resultado:
            modulo, confianca = resultado
            return {
                "modulo": modulo,
                "confianca": confianca,
                "regra": regra.__name__,
                "msg_limpa": msg_norm,
            }

    # Nenhuma regra bateu → fallback para IA
    return {
        "modulo": "ollama",
        "confianca": 0.0,
        "regra": "fallback",
        "msg_limpa": msg_norm,
    }