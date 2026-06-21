import subprocess
import sys
import os


class Module:

    name = "launcher"

    # Cada programa tem uma lista de caminhos possíveis (Windows)
    # e o comando para Linux/Mac. Tenta cada caminho até achar.
    PROGRAMAS = {
        "chrome": {
            "windows": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "linux": "google-chrome",
            "darwin": "open -a 'Google Chrome'",
            "display": "Chrome"
        },
        "edge": {
            "windows": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "linux": "microsoft-edge",
            "darwin": "open -a 'Microsoft Edge'",
            "display": "Edge"
        },
        "spotify": {
            "windows": [
                # Instalação via Store (AppData\Roaming)
                os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
                # Instalação via Store (LocalAppData\Microsoft\WindowsApps)
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "Spotify.exe"),
                # Instalação clássica
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "Spotify.exe"),
                r"C:\Program Files\Spotify\Spotify.exe",
                r"C:\Program Files (x86)\Spotify\Spotify.exe",
            ],
            "linux": "spotify",
            "darwin": "open -a 'Spotify'",
            "display": "Spotify"
        },
        "notepad": {
            "windows": [r"C:\Windows\System32\notepad.exe"],
            "linux": "gedit",
            "darwin": "open -a 'TextEdit'",
            "display": "Bloco de Notas"
        },
        "calculadora": {
            "windows": [r"C:\Windows\System32\calc.exe"],
            "linux": "gnome-calculator",
            "darwin": "open -a 'Calculator'",
            "display": "Calculadora"
        },
        "vscode": {
            "windows": [
                r"C:\Program Files\Microsoft VS Code\Code.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
            ],
            "linux": "code",
            "darwin": "open -a 'Visual Studio Code'",
            "display": "VS Code"
        },
    }

    # Mapeamento de palavras → chave do programa
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

    TRIGGERS = ["abre", "abra", "abrir", "inicia", "inicie", "lança", "lance", "abrir o", "abre o"]

    def run(self, msg: str):
        msg_lower = msg.lower().strip()

        # Verifica se tem trigger de abertura
        tem_trigger = any(t in msg_lower for t in self.TRIGGERS)
        if not tem_trigger:
            return None

        # Tenta encontrar qual programa foi pedido
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
                caminhos = info["windows"]

                for caminho in caminhos:
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