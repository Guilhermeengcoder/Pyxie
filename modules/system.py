from datetime import datetime


class SystemModule:

    GREETINGS = ["oi", "olá", "ola", "eai", "e aí", "bom dia", "boa tarde", "boa noite", "fala ai", "qual foi", "ei"]

    def handle(self, message):

        for greet in self.GREETINGS:
            if greet in message:
                return "Olá Guilherme. PYXIE online."

        if "status" in message:
            return "Todos os sistemas funcionando."

        # NOVO: comando de horas
        if "hora" in message:
            agora = datetime.now()
            return f"Agora são {agora.strftime('%H:%M')}."

        return None