from core.memory import Memory  # ajusta o caminho se necessário

memoria = Memory()

def executar(entrada):
    entrada = entrada.lower()

    # 🔹 SALVAR MEMÓRIA
    if "lembre" in entrada or "memorize" in entrada:
        conteudo = entrada.replace("lembre", "").replace("memorize", "").strip()

        if not conteudo:
            return "O que você quer que eu lembre?"

        memoria.remember("geral", conteudo)
        return "Informação salva."

    # 🔹 LISTAR MEMÓRIAS
    if "memoria" in entrada or "memórias" in entrada:
        if not memoria.data:
            return "Ainda não lembro de nada."

        resposta = "Eu lembro de:\n"
        for categoria, info in memoria.data.items():
            resposta += f"- {info['current']}\n"

        return resposta

    # 🔹 CONSULTA DIRETA
    if "o que voce lembra" in entrada:
        if not memoria.data:
            return "Ainda não lembro de nada."

        resposta = "Eu lembro de:\n"
        for categoria, info in memoria.data.items():
            resposta += f"- {info['current']}\n"

        return resposta

    # ⚠️ ESSENCIAL: se não for com memória, não responde
    return None