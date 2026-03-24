from core.brain import brain
from core.context import Context
from core.nlp import detectar_intencao
from core.module_loader import carregar_modulos
from modules.ollama_ai import perguntar_ollama

context = Context()
modulos = carregar_modulos()

STOPWORDS = ["a", "o", "de", "do", "da", "e", "é", "que", "no", "na"]


def processar_mensagem(msg: str):

    msg = msg.lower()
    context.add_message(msg)

    intent = detectar_intencao(msg)

    # =========================
    # 🔥 MÓDULOS (ANTES DE TUDO)
    # =========================
    for nome, func in modulos.items():
        resposta = func(msg)
        if resposta:
            return resposta

    # =========================
    # PESQUISA DIRETA
    # =========================
    if msg.startswith("pesquise"):

        termo = msg.replace("pesquise", "").strip()

        if termo:
            context.update_topic(termo)

        resposta = brain.process(msg)

        return resposta if resposta else "Não encontrei nada relevante."

    # =========================
    # INTENÇÕES NLP
    # =========================
    if intent == "pesquisa":

        termo = msg

        comandos = [
            "quem é",
            "quem foi",
            "o que é",
            "o que foi",    
            "pesquise",
            "procure",
            "me fale sobre"
        ]

        for c in comandos:
            if termo.startswith(c):
                termo = termo.replace(c, "").strip()

        if termo:
            context.update_topic(termo)

        resposta = brain.process("pesquise " + termo)

        if not resposta:
            return "Não encontrei nada relevante."

        # 🔥 filtro básico
        if termo not in resposta.lower():
            return "Não encontrei algo confiável sobre isso."

        return resposta

    # =========================
    # PRONOMES COM CONTEXTO
    # =========================
    if "ele" in msg or "ela" in msg:

        topic = context.get_topic()

        if topic:
            msg = msg.replace("ele", topic)
            msg = msg.replace("ela", topic)

            return brain.process(msg)

    # =========================
    # PADRÃO
    # =========================
    resposta = brain.process(msg)

    if resposta:
        return resposta

    # 🔥 fallback inteligente (IA)
    memoria = "\n".join(context.get_context())
    return perguntar_ollama(msg, memoria)