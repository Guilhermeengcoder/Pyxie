from datetime import datetime


class Module:

    name = "hora"

    def handle(self, msg):

        if "hora" in msg:
            agora = datetime.now().strftime("%H:%M")
            return f"Agora são {agora}"