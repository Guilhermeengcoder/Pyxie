import random
from core.memory import Memory
from datetime import datetime
from zoneinfo import ZoneInfo
from core.identity import obter_nome, obter_criador, obter_usuario
from core.intent import detectar_intencao
from core.personality import responder_saudacao
from core.internet import buscar_web
from core.knowledge import buscar_conhecimento, aprender


def pensar(pergunta):

    intencao = detectar_intencao(pergunta)

    if intencao == "saudacao":
        return responder_saudacao(obter_usuario())

    if intencao == "identidade":
        return "Eu sou a PYXIE."

    return "Ainda estou aprendendo, mas posso aprender isso."


class Brain:

    def __init__(self):
        self.memory = Memory()
        self.modules = {}

    def register_module(self, name, module):
        self.modules[name] = module

    def process(self, message):

        message = message.lower()

        # Módulos externos
        for module in self.modules.values():
            if hasattr(module, "handle"):
                response = module.handle(message)
                if response:
                    return response

        # Cálculo
        if message.startswith("calcule") or message.startswith("quanto é"):

            expression = message.replace("calcule", "").replace("quanto é", "").strip()
            expression = expression.replace("?", "").replace("=", "")

            try:
                result = eval(expression)
                return f"O resultado é {result}"
            except:
                return "Não consegui calcular essa conta."

        # Hora correta no Brasil
        if "hora" in message:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            return f"Agora são {agora.strftime('%H:%M')}"

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
        if "o que você sabe" in message or "o que você lembra" in message:
            data = self.memory.data
            if data:
                return str(data)
            return "Ainda não tenho registros."

        # Buscar memória
        if message.startswith("procure"):
            keyword = message.replace("procure", "").strip()
            results = self.memory.search(keyword)

            if results:
                return f"Encontrei: {results}"
            return "Nada encontrado."

        # Identidade
        if "seu nome" in message:
            return f"Meu nome é {obter_nome()}."

        if "quem te criou" in message:
            return f"Fui criada por {obter_criador()}."

        if "quem sou eu" in message:
            return f"Você é {obter_usuario()}, meu criador."

        # PESQUISA EXPLÍCITA
        if message.startswith("pesquise") or message.startswith("procure na internet"):

            pergunta = message.replace("pesquise", "").replace("procure na internet", "").strip()

            resposta = buscar_web(pergunta)

            if resposta:
                return resposta

            return "Não encontrei nada relevante."

        # KNOWLEDGE ENGINE

        resposta = buscar_conhecimento(message)

        if resposta:
            return resposta

        # INTERNET AUTOMÁTICA

        resposta = buscar_web(message)
        if resposta:
            aprender(message, resposta)
            return resposta

        return "Ainda não encontrei uma resposta para isso."
        