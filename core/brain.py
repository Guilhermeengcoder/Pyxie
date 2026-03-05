import random
from core.memory import Memory
from datetime import datetime
from core.identity import obter_nome, obter_criador, obter_usuario



class Brain:

    def __init__(self):
        self.memory = Memory()
        self.modules = {}

    # NOVO: registrar módulos
    def register_module(self, name, module):
        self.modules[name] = module

    def process(self, message):
        message = message.lower()

        # Primeiro deixa os módulos tentarem responder
        for module in self.modules.values():
            if hasattr(module, "handle"):
                response = module.handle(message)
                if response:
                    return response

        # Sistema de cálculo
        if message.startswith("calcule") or message.startswith("quanto é"):

            expression = message.replace("calcule", "").replace("quanto é", "").strip()

            expression = expression.replace("?", "").replace("=", "")

            try:
                result = eval(expression)
                return f"O resultado é {result}"
            except:
                return "Não consegui calcular essa conta."

        # Hora atual
        if "hora" in message:
            agora = datetime.now()
            return f"Agora são {agora.hour}:{agora.minute}"

        # Saudações
        greetings = [
            "Olá 👋",
            "Oi, Guilherme.",
            "Estou aqui.",
            "Fala comigo.",
            "Sempre pronta."
        ]

        if any(word in message for word in ["oi", "olá", "opa", "eai", "fala ai", "tudo bem", "ei"]):
            return random.choice(greetings)

        # Recuperar memória
        if "o que você sabe" in message:
            data = self.memory.data
            if data:
                return str(data)
            return "Ainda não tenho registros."

        if "o que você lembra" in message:
            data = self.memory.data
            if data:
                return str(data)
            return "Sobre isso não lembro de nada."

        # Buscar palavra-chave
        if message.startswith("procure"):
            keyword = message.replace("procure", "").strip()
            results = self.memory.search(keyword)

            if results:
                return f"Encontrei: {results}"
            return "Nada encontrado."

        if "seu nome" in message:
            return f"Meu nome é {obter_nome()}."

        if "quem te criou" in message:
            return f"Fui criada por {obter_criador()}."

        if "quem sou eu" in message:
            return f"Você é {obter_usuario()}, meu criador."    

        return "Processado."