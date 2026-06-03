import subprocess
import sys
import os


class Module:

    name = "launcher"

    PROGRAMAS = {
        "chrome": {
            "windows": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "linux": "google-chrome",
            "darwin": "open -a 'Google Chrome'"
        },
        "edge": {
            "windows": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "linux": "microsoft-edge",
            "darwin": "open -a 'Microsoft Edge'"
        },
        "spotify": {
            "windows": os.path.join(
                os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"
            ),
            "linux": "spotify",
            "darwin": "open -a 'Spotify'"
        },
    }

    TRIGGERS = {
        "chrome": [
            "abra o chrome",
            "abre o chrome",
            "abrir chrome",
            "abrir o chrome",
            "abra o google chrome",
            "abre o google chrome",
            "abrir o google chrome",
            "inicia o chrome",
            "inicie o chrome",
            "lança o chrome",
            "lance o chrome",
        ],
        "edge": [
            "abra o edge",
            "abre o edge",
            "abrir edge",
            "abrir o edge",
            "abra o microsoft edge",
            "abre o microsoft edge",
            "abrir o microsoft edge",
            "inicia o edge",
            "inicie o edge",
        ],
        "spotify": [
            "abra o spotify",
            "abre o spotify",
            "abrir spotify",
            "abrir o spotify",
            "inicia o spotify",
            "inicie o spotify",
            "abre a musica",
            "abra a musica",
            "coloca uma musica",
            "coloque uma musica",
            "quero ouvir musica",
        ],
    }

    def run(self, msg: str):
        msg = msg.lower().strip()

        for programa, triggers in self.TRIGGERS.items():
            for trigger in triggers:
                if trigger in msg:
                    return self._abrir(programa)

        return None

    def _abrir(self, programa: str):
        info = self.PROGRAMAS.get(programa)

        if not info:
            return f"Programa '{programa}' não encontrado na lista."

        try:
            if sys.platform == "win32":
                caminho = info["windows"]

                if not os.path.exists(caminho):
                    return f"Não encontrei o {programa.capitalize()} no caminho esperado. Verifique se está instalado."

                subprocess.Popen(caminho)

            elif sys.platform == "darwin":
                os.system(info["darwin"])

            else:
                subprocess.Popen([info["linux"]])

            return f"Abrindo {programa.capitalize()}!"

        except Exception as e:
            return f"Erro ao abrir {programa}: {str(e)}"