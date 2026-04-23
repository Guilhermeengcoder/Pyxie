import random

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

        self.sufixos = {
            "ajuda": [
                " Se precisar de mais alguma coisa é só falar.",
                " Posso te ajudar com mais algo se quiser."
            ],
            "normal": [
                ""
            ],
            "comando": [
                ""
            ],
            "saudacao": [
                "",
                " Como posso te ajudar hoje?"
            ]
        }

    def aplicar(self, resposta, tipo="normal"):

        if not resposta:
            return resposta

        if tipo not in self.sufixos:
            tipo = "normal"

        sufixo = random.choice(self.sufixos[tipo])

        return f"{resposta}{sufixo}"