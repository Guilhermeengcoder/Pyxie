import keyboard
import screen_brightness_control as sbc


class Module:

    name = "system_control"

    ALIASES = {
        "aumentar volume": "volume_up",
        "aumente o volume": "volume_up",
        "volume mais alto": "volume_up",

        "diminuir volume": "volume_down",
        "abaixar volume": "volume_down",
        "volume mais baixo": "volume_down",

        "silenciar": "mute",
        "mutar": "mute",

        "aumentar brilho": "brightness_up",
        "aumente o brilho": "brightness_up",

        "diminuir brilho": "brightness_down",
        "abaixar brilho": "brightness_down",

        "qual o brilho": "brightness_status",
        "mostrar brilho": "brightness_status",
    }

    def run(self, msg: str):
        msg_lower = msg.lower().strip()

        for alias, comando in sorted(
            self.ALIASES.items(),
            key=lambda x: -len(x[0])
        ):
            if alias in msg_lower:
                return self._executar(comando)

        return None

    def _executar(self, comando):

        try:

            if comando == "volume_up":
                keyboard.send("volume up")
                return "Aumentando o volume."

            elif comando == "volume_down":
                keyboard.send("volume down")
                return "Diminuindo o volume."

            elif comando == "mute":
                keyboard.send("volume mute")
                return "Volume silenciado."

            elif comando == "brightness_up":
                atual = sbc.get_brightness()[0]
                novo = min(atual + 10, 100)

                sbc.set_brightness(novo)

                return f"Brilho aumentado para {novo}%."

            elif comando == "brightness_down":
                atual = sbc.get_brightness()[0]
                novo = max(atual - 10, 0)

                sbc.set_brightness(novo)

                return f"Brilho reduzido para {novo}%."

            elif comando == "brightness_status":
                atual = sbc.get_brightness()[0]

                return f"O brilho atual está em {atual}%."

        except Exception as e:
            return f"Erro ao executar comando: {str(e)}"

        return None