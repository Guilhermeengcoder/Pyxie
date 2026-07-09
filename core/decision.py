import re
import unicodedata

PREFIXO = "pyxie,"


def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    for c in ["?", "!", ".", ","]:
        texto = texto.replace(c, "")
    return texto


def _tem_prefixo(msg: str) -> tuple[bool, str]:
    """Retorna (tem_prefixo, msg_sem_prefixo)."""
    normalizado = msg.lower().strip()
    if normalizado.startswith(PREFIXO):
        return True, normalizado[len(PREFIXO):].strip()
    return False, normalizado


def _checar_hora(msg: str):
    tem, conteudo = _tem_prefixo(msg)
    if not tem:
        return 0.0

    padroes_hora = [
        r"que horas (sao|são|e|é)",
        r"qual (a hora|o horario|o dia|a data)( atual)?",
        r"que (dia|data) (e|é) hoje",
        r"qual e a data de hoje",
        r"(me diz|me diga|fala) (a hora|as horas|que horas|que dia)",
    ]

    for padrao in padroes_hora:
        if re.search(padrao, conteudo):
            return 1.0

    palavras = conteudo.split()
    if len(palavras) <= 3:
        if any(p in palavras for p in ["hora", "horas", "dia", "data"]):
            return 0.8

    return 0.0


def _checar_saudacao(msg: str):
    # saudações continuam sem precisar de prefixo
    saudacoes_exatas = {
        "oi", "ola", "opa", "eai", "e ai",
        "fala", "salve", "oi tudo bem", "ola tudo bem"
    }
    cumprimentos_inicio = ["bom dia", "boa tarde", "boa noite"]

    msg_norm = normalizar(msg)

    if msg_norm in saudacoes_exatas:
        return 1.0

    for c in cumprimentos_inicio:
        if msg_norm.startswith(c):
            return 0.9

    palavras = msg_norm.split()
    if palavras and palavras[0] in {"salve", "oi", "ola", "eai", "fala"} and len(palavras) <= 6:
        return 0.7

    return 0.0


def _checar_identidade(msg: str):
    padroes = [
        "quem e voce", "qual seu nome",
        "se apresente", "quem te criou",
        "voce e uma ia", "voce e um robo"
    ]
    msg_norm = normalizar(msg)
    for p in padroes:
        if p in msg_norm:
            return 1.0
    return 0.0


def _checar_calculo(msg: str):
    msg_norm = normalizar(msg)
    padroes = [
        r"calcul[ae]",
        r"quanto e \d",
        r"resultado de",
        r"\d+\s*[\+\-\*\/]\s*\d+",
    ]
    for p in padroes:
        if re.search(p, msg_norm):
            return 1.0
    return 0.0


def _checar_memoria(msg: str):
    msg_norm = normalizar(msg)
    triggers = [
        "lembre que", "guarde que", "memorize que",
        "anota que", "liste memorias",
        "o que voce lembra", "esqueca"
    ]
    for t in triggers:
        if t in msg_norm:
            return 1.0
    return 0.0


def _checar_pesquisa_explicita(msg: str):
    msg_norm = normalizar(msg)
    inicios = [
        "pesquise", "procure", "busque",
        "pesquise sobre", "procure sobre"
    ]
    if any(msg_norm.startswith(i) for i in inicios):
        return 1.0
    return 0.0


def _checar_pergunta_web(msg: str):
    msg_norm = normalizar(msg)
    inicios = [
        "quem foi", "quem e",
        "o que e", "o que foi",
        "quando foi", "onde fica",
        "como funciona", "explique",
        "me explique", "qual foi",
        "quanto tempo durou",
        "em que ano"
    ]
    if any(msg_norm.startswith(i) for i in inicios):
        return 0.9
    return 0.0


def _checar_lembrete(msg: str):
    msg_norm = normalizar(msg)
    if re.search(r"(lembra|lembre|avisa).*(as|às)\s*\d{1,2}", msg_norm):
        return 1.0
    if "lembrete" in msg_norm:
        return 0.8
    return 0.0


def _checar_launcher(msg: str):
    msg_norm = normalizar(msg)
    triggers = [
        "abre", "abra", "abrir",
        "inicia", "inicie",
        "abre o chrome", "abra o chrome",
        "abrir o chrome"
    ]
    if any(t in msg_norm for t in triggers):
        return 0.9
    return 0.0


REGRAS = {
    "launcher":           _checar_launcher,
    "internet_explicita": _checar_pesquisa_explicita,
    "memoria":            _checar_memoria,
    "lembrete":           _checar_lembrete,
    "calculo":            _checar_calculo,
    "identidade":         _checar_identidade,
    "saudacao":           _checar_saudacao,
    "hora":               _checar_hora,
    "internet":           _checar_pergunta_web,
}


def decidir(mensagem: str, contexto: dict = None) -> dict:
    contexto = contexto or {}
    msg_norm = normalizar(mensagem)

    pontuacoes = {}

    for nome, regra in REGRAS.items():
        # hora recebe a mensagem original para checar o prefixo com vírgula
        entrada = mensagem if nome == "hora" else msg_norm
        score = regra(entrada)
        if score > 0:
            pontuacoes[nome] = score

    # contexto: continuidade de conversa
    if contexto.get("ultimo_destino") == "internet":
        if msg_norm.startswith(("e ", "e onde", "e quando", "e como")):
            pontuacoes["internet"] = max(pontuacoes.get("internet", 0), 0.85)

    if not pontuacoes:
        return {
            "destino":   "ollama",
            "confianca": 0.0,
            "regra":     "fallback",
            "msg_norm":  msg_norm,
        }

    destino = max(pontuacoes, key=pontuacoes.get)

    return {
        "destino":   destino,
        "confianca": pontuacoes[destino],
        "regra":     destino,
        "msg_norm":  msg_norm,
    }