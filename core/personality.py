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

class Personality:

    def __init__(self):

        self.estilo = "amigavel"

        self.prefixos = [
            "",
            "Claro. ",
            "Entendi. ",
            "Certo. ",
            "Deixa eu ver. "
        ]

        self.sufixos = [
            "",
            "",
            "",
            " Se precisar de mais alguma coisa é só falar.",
            " Estou aqui se precisar."
        ]

    def aplicar(self, resposta):

        if not resposta:
            return resposta

        prefixo = random.choice(self.prefixos)
        sufixo = random.choice(self.sufixos)

        return f"{prefixo}{resposta}{sufixo}"