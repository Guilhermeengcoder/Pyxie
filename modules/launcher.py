import re
import subprocess
import sys
import os


class Module:
    name = "launcher"

    PROGRAMAS = {
        "chrome": {
            "windows": [],
            "linux": "google-chrome",
            "darwin": "open -a 'Google Chrome'",
            "display": "Chrome",
        },
        "edge": {
            "windows": [],
            "linux": "microsoft-edge",
            "darwin": "open -a 'Microsoft Edge'",
            "display": "Edge",
        },
        "spotify": {
            "windows": [],
            "linux": "spotify",
            "darwin": "open -a 'Spotify'",
            "display": "Spotify",
        },
        "notepad": {
            "windows": [],
            "linux": "gedit",
            "darwin": "open -a 'TextEdit'",
            "display": "Bloco de Notas",
        },
        "calculadora": {
            "windows": [],
            "linux": "gnome-calculator",
            "darwin": "open -a 'Calculator'",
            "display": "Calculadora",
        },
        "vscode": {
            "windows": [],
            "linux": "code",
            "darwin": "open -a 'Visual Studio Code'",
            "display": "VS Code",
        },
    }

    ALIASES = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "edge",
        "microsoft edge": "edge",
        "spotify": "spotify",
        "bloco de notas": "notepad",
        "notepad": "notepad",
        "calculadora": "calculadora",
        "calc": "calculadora",
        "vscode": "vscode",
        "vs code": "vscode",
        "visual studio code": "vscode",
    }

    # So conta como comando se a frase COMEÇAR com um desses verbos.
    # Isso evita abrir programas so porque a palavra "abrir" apareceu
    # em algum lugar de uma pergunta ou comentario (ex.: "voce consegue
    # abrir o chrome?" nao deve, de fato, abrir o chrome).
    PADRAO_COMANDO = re.compile(r"^(abre|abra|abrir|inicia|inicie|lan[cç]a|lance)\b")

    def run(self, msg: str):
        msg_lower = msg.lower().strip()

        if not self.PADRAO_COMANDO.match(msg_lower):
            return None

        for alias, programa in sorted(self.ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in msg_lower:
                return self._abrir(programa)

        return None

    def _abrir(self, programa: str):
        if programa not in self.PROGRAMAS:
            return f"Não conheço o programa '{programa}'."
        info = self.PROGRAMAS[programa]
        display = info["display"]
        try:
            if sys.platform == "win32":
                for caminho in info["windows"]:
                    if caminho and os.path.exists(caminho):
                        subprocess.Popen([caminho])
                        return f"Abrindo {display}!"
                return f"Não encontrei o {display}. Verifique se está instalado."
            elif sys.platform == "darwin":
                os.system(info["darwin"])
                return f"Abrindo {display}!"
            else:
                subprocess.Popen([info["linux"]])
                return f"Abrindo {display}!"
        except Exception as e:
            return f"Erro ao abrir {display}: {str(e)}"
