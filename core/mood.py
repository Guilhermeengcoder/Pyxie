import random


class Mood:

    def __init__(self):

        self.estados = [
            "neutra",
            "curiosa",
            "animada",
            "pensativa"
        ]

        self.estado_atual = "neutra"

    def atualizar(self):

        # pequena chance de mudar humor
        if random.random() < 0.2:
            self.estado_atual = random.choice(self.estados)

    def get(self):
        return self.estado_atual