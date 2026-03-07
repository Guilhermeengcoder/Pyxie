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