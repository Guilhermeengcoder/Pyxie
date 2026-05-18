import time

from core.brain import brain
from core.context import Context
from core.nlp import detectar_intencao
from core.module_loader import carregar_modulos
from modules.ollama_ai import perguntar_ollama

# =============================================================
# CONTEXTO E MÓDULOS GLOBAIS
# carregar_modulos() usa cache — só executa trabalho pesado
# uma vez. Nas chamadas seguintes retorna instantâneo.
# =============================================================
context = Context()
modulos = carregar_modulos()

STOPWORDS = ["a", "o", "de", "do", "da", "e", "é", "que", "no", "na"]


# =============================================================
# ROTEAMENTO POR KEYWORDS
# Cada módulo pode declarar keywords = ["hora", "horas", "dia"]
# com palavras simples (não frases) para ser pré-selecionado.
# Módulos sem keywords são ignorados nessa etapa — eles ainda
# podem ser acionados pelo brain.py via decidir().
# =============================================================
def detectar_modulos_compativeis(msg: str) -> list:
    palavras = set(msg.split())
    compativeis = []

    for nome, instancia in modulos.items():
        keywords = getattr(instancia, "keywords", [])
        if not keywords:
            continue

        if palavras.intersection(k.lower() for k in keywords):
            compativeis.append(nome)

    return compativeis


# =============================================================
# PROCESSAMENTO PRINCIPAL
# =============================================================
def processar_mensagem(msg: str):
    inicio_total = time.perf_counter()

    msg = msg.lower().strip()
    if not msg:
        return "Mensagem vazia."

    context.add_message(msg)
    intent = detectar_intencao(msg)

    # =========================================================
    # MÓDULOS COM KEYWORDS
    # Acessa instâncias direto do dict — sem instanciar de novo
    # =========================================================
    for nome in detectar_modulos_compativeis(msg):
        instancia = modulos.get(nome)
        if not instancia:
            continue

        try:
            inicio = time.perf_counter()
            resposta = instancia.run(msg)
            print(f"[engine] '{nome}' em {(time.perf_counter() - inicio):.3f}s")

            if resposta:
                print(f"[engine] total: {(time.perf_counter() - inicio_total):.3f}s")
                return resposta

        except Exception as e:
            print(f"[engine] erro no módulo '{nome}': {e}")

    # =========================================================
    # PESQUISA DIRETA
    # =========================================================
    if msg.startswith("pesquise"):
        termo = msg.replace("pesquise", "").strip()
        if termo:
            context.update_topic(termo)

        resposta = brain.process(msg)
        return resposta if resposta else "Não encontrei nada relevante."

    # =========================================================
    # INTENÇÕES NLP
    # =========================================================
    if intent == "pesquisa":
        termo = msg
        for comando in ["quem é", "quem foi", "o que é", "o que foi",
                        "pesquise", "procure", "me fale sobre"]:
            if termo.startswith(comando):
                termo = termo.replace(comando, "").strip()

        if termo:
            context.update_topic(termo)

        resposta = brain.process(f"pesquise {termo}")

        if not resposta:
            return "Não encontrei nada relevante."
        if termo not in resposta.lower():
            return "Não encontrei algo confiável sobre isso."
        return resposta

    # =========================================================
    # PRONOMES + CONTEXTO
    # =========================================================
    if "ele" in msg or "ela" in msg:
        topic = context.get_topic()
        if topic:
            msg = msg.replace("ele", topic).replace("ela", topic)
            resposta = brain.process(msg)
            if resposta:
                return resposta

    # =========================================================
    # PROCESSAMENTO PADRÃO
    # =========================================================
    resposta = brain.process(msg)
    if resposta:
        return resposta

    # =========================================================
    # FALLBACK IA — contexto limitado para não sobrecarregar
    # =========================================================
    memoria = "\n".join(context.get_context()[-5:])
    resposta = perguntar_ollama(msg, memoria)

    print(f"[engine] fallback IA em {(time.perf_counter() - inicio_total):.3f}s")
    return resposta