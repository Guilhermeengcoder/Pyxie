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
        }
    }

    TRIGGERS = [
        "abra o chrome",
        "abre o chrome",
        "abrir chrome",
        "abra o google chrome",
        "abre o google chrome",
        "abrir o chrome",
        "abrir o google chrome",
        "inicia o chrome",
        "inicie o chrome",
        "lança o chrome",
        "lance o chrome",
    ]

    def run(self, msg: str):
        msg = msg.lower().strip()

        for trigger in self.TRIGGERS:
            if trigger in msg:
                return self._abrir("chrome")

        return None

    def _abrir(self, programa: str):
        try:
            if sys.platform == "win32":
                caminho = self.PROGRAMAS[programa]["windows"]
                subprocess.Popen(caminho)

            elif sys.platform == "darwin":
                os.system(self.PROGRAMAS[programa]["darwin"])

            else:
                subprocess.Popen([self.PROGRAMAS[programa]["linux"]])

            return f"Abrindo {programa.capitalize()}!"

        except Exception as e:
            return f"Erro ao abrir {programa}: {str(e)}"