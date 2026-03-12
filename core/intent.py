def detectar_intencao(pergunta):

    pergunta = pergunta.lower()

    # saudações
    if any(s in pergunta for s in ["bom dia", "boa tarde", "boa noite", "oi", "olá"]):
        return "saudacao"

    # identidade
    if any(s in pergunta for s in ["seu nome", "quem é você", "quem é voce", "como você se chama"]):
        return "identidade"

    # tempo
    if "hora" in pergunta:
        return "tempo"

    return "desconhecido"


# NOVA FUNÇÃO ADICIONADA (sem alterar a existente)

def detectar_intencao_avancada(pergunta):

    pergunta = pergunta.lower()

    # variações mais amplas
    if "voce" in pergunta and "quem" in pergunta:
        return "identidade"

    if "hora" in pergunta or "horas" in pergunta:
        return "tempo"

    if any(s in pergunta for s in ["oi", "ola", "opa", "eai", "fala"]):
        return "saudacao"

    return "desconhecido"