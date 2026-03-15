from core.brain import brain
from core.memory import Memory
from core.context import Context
from core.nlp import detectar_intencao

memory = Memory()
context = Context()

STOPWORDS = ["a", "o", "de", "do", "da", "e", "é", "que", "no", "na"]


def processar_mensagem(msg: str):

    msg = msg.lower()
    context.add_message(msg)

    intent = detectar_intencao(msg)

    # =========================
    # LISTAR MEMÓRIAS
    # =========================

    if "o que voce lembra" in msg or "oque voce lembra" in msg:
        if memory.data:
            resposta = "Eu lembro de:\n"
            for cat in memory.data:
                resposta += "- " + memory.data[cat]["current"] + "\n"
            return resposta
        else:
            return "Ainda não lembro de nada."

    # =========================
    # SALVAR MEMÓRIA
    # =========================

    if "lembre que" in msg or "lembrar que" in msg:

        content = msg.replace("lembre que", "").replace("lembrar que", "").strip()

        words = content.split()
        category = words[0] if words else "nota"

        memory.remember(category, content)

        context.update_topic(category)

        return "Informação salva."

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
    # BUSCA NA MEMÓRIA
    # =========================

    words = [w for w in msg.split() if w not in STOPWORDS and len(w) > 2]

    for word in words:

        results = memory.search(word)

        if results:

            context.update_topic(word)

            resposta = "Encontrei isso na memória:\n"

            for r in results:
                resposta += "- " + r + "\n"

            return resposta

    # =========================
    # CONTEXTO CURTO
    # =========================

    if len(words) <= 2 and context.get_topic():

        results = memory.search(context.get_topic())

        if results:

            resposta = f"Considerando que estamos falando sobre {context.get_topic()}\n"

            for r in results:
                resposta += "- " + r + "\n"

            return resposta

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

    return resposta if resposta else "Não encontrei nada relevante."

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

    return brain.process(msg)