class SystemModule:

    GREETINGS = ["oi", "olá", "ola", "eai", "e aí", "bom dia", "boa tarde", "boa noite", "fala ai", "qual foi", "ei"]

    def handle(self, message):

        for greet in self.GREETINGS:
            if greet in message:
                return "Olá Guilherme. PYXIE online."

        if "status" in message:
            return "Todos os sistemas funcionando."

        return None