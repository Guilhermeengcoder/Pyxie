def detectar_intencao(pergunta):

    pergunta = pergunta.lower()

    if "bom dia" in pergunta:
        return "saudacao"

    if "boa tarde" in pergunta:
        return "saudacao"

    if "boa noite" in pergunta:
        return "saudacao"

    if "seu nome" in pergunta:
        return "identidade"

    if "horas" in pergunta:
        return "tempo"

    return "desconhecido"