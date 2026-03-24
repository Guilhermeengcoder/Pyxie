from datetime import datetime


class Module:

    name = "hora"

    def handle(self, msg):

        msg = msg.lower()

        if "hora" in msg:
            agora = datetime.now().strftime("%H:%M")
            return f"Agora são {agora}"

        if "dia" in msg or "data" in msg:
            hoje = datetime.now().strftime("%d/%m/%Y")
            return f"Hoje é {hoje}"

        return None