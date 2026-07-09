from datetime import datetime
from zoneinfo import ZoneInfo

PREFIXO = "pyxie,"


class Module:

    name = "hora"

    def run(self, msg):
        msg = msg.lower().strip()

        if not msg.startswith(PREFIXO):
            return None

        msg = msg[len(PREFIXO):].strip()

        try:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        except Exception:
            agora = datetime.now()

        dias = {
            "monday":    "segunda-feira",
            "tuesday":   "terça-feira",
            "wednesday": "quarta-feira",
            "thursday":  "quinta-feira",
            "friday":    "sexta-feira",
            "saturday":  "sábado",
            "sunday":    "domingo"
        }

        if "dia" in msg or "data" in msg:
            dia_semana = dias.get(agora.strftime("%A").lower(), "")
            return f"Hoje é {dia_semana}, {agora.strftime('%d/%m/%Y')}"

        if "hora" in msg:
            return f"Agora são {agora.strftime('%H:%M')}"

        return None