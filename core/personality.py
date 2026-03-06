import random
from core.identity import carregar_identidade

def responder_saudacao(usuario):

    respostas = [
        f"Olá {usuario}! Como posso ajudar hoje?",
        f"Oi {usuario}! É bom falar com você novamente.",
        f"Olá! Estou pronta para ajudar.",
        f"Oi {usuario}, o que vamos construir hoje?"
    ]

    return random.choice(respostas)