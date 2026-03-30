from datetime import datetime
from zoneinfo import ZoneInfo


class Module:

    name = "hora"

    def run(self, msg):
        msg = msg.lower()

        try:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        except:
            agora = datetime.now()

        dias = {
            "monday": "segunda-feira",
            "tuesday": "terça-feira",
            "wednesday": "quarta-feira",
            "thursday": "quinta-feira",
            "friday": "sexta-feira",
            "saturday": "sábado",
            "sunday": "domingo"
        }

        # 🔥 DATA (FORÇADO)
        if "dia" in msg:
            dia_semana = dias.get(agora.strftime("%A").lower(), "")
            return f"Hoje é {dia_semana}, {agora.strftime('%d/%m/%Y')}"

        # 🔥 HORA
        if "hora" in msg:
            return f"Agora são {agora.strftime('%H:%M')}"

        return None