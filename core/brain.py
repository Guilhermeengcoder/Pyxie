import random
import unicodedata
from core.memory import Memory
from datetime import datetime
from zoneinfo import ZoneInfo
from core.identity import obter_nome, obter_criador, obter_usuario, apresentar
from core.intent import detectar_intencao
from core.personality import responder_saudacao
from core.internet import buscar_web
from core.knowledge import buscar_conhecimento, aprender
from core.reminder import adicionar, listar, verificar


# função para normalizar texto
def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto


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

        message = normalizar(message)

        # módulos externos
        for module in self.modules.values():
            if hasattr(module, "handle"):
                response = module.handle(message)
                if response:
                    return response

        # cálculo
        if message.startswith("calcule") or message.startswith("quanto e"):

            expression = message.replace("calcule", "").replace("quanto e", "").strip()
            expression = expression.replace("?", "").replace("=", "")

            try:
                result = eval(expression)
                return f"O resultado é {result}"
            except:
                return "Não consegui calcular essa conta."

        # hora correta no Brasil
        if "hora" in message or "horas" in message:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            return f"Agora são {agora.strftime('%H:%M')}"

        # saudações
        greetings = [
            "Olá 👋",
            "Oi, Guilherme.",
            "Estou aqui.",
            "Fala comigo.",
            "Sempre pronta."
        ]

        if any(word in message for word in ["oi", "ola", "opa", "eai", "fala ai", "tudo bem", "ei"]):
            return random.choice(greetings)

        # recuperar memória
        if "o que voce sabe" in message or "o que voce lembra" in message:
            data = self.memory.data
            if data:
                return str(data)
            return "Ainda não tenho registros."

        # buscar memória
        if message.startswith("procure"):
            keyword = message.replace("procure", "").strip()
            results = self.memory.search(keyword)

            if results:
                return f"Encontrei: {results}"
            return "Nada encontrado."

        # reconhecer perguntas de identidade
        if any(p in message for p in [
            "quem e voce",
            "quem e vc",
            "como voce se chama"
        ]):
            return f"Eu sou {obter_nome()}."

        # lembretes
        if "listar lembretes" in message:
            return str(listar())

        if message.startswith("lembre-me"):
            try:
                partes = message.replace("lembre-me", "").strip().split(" as ")
                texto = partes[0]
                horario = partes[1]
                adicionar(texto, horario)
                return "Lembrete adicionado 👍"
            except:
                return "Use: lembre-me de X às HH:MM"

        # identidade / apresentação
        if "seu nome" in message:
            return f"Meu nome é {obter_nome()}."

        if "se apresente" in message or "apresente se" in message:
            return apresentar()

        if "quem te criou" in message:
            return f"Fui criada por {obter_criador()}."

        if "quem sou eu" in message:
            return f"Você é {obter_usuario()}, meu criador."

        # pesquisa explícita
        if message.startswith("pesquise") or message.startswith("procure na internet"):

            pergunta = message.replace("pesquise", "").replace("procure na internet", "").strip()

            resposta = buscar_web(pergunta)

            if resposta:
                return resposta

            return "Não encontrei nada relevante."

        # knowledge engine
        resposta = buscar_conhecimento(message)

        if resposta:
            return resposta

        # internet automática
        resposta = buscar_web(message)

        if resposta:
            aprender(message, resposta)
            return resposta
    
        return "Ainda não encontrei uma resposta para isso."

from core.modules.memory_control import MemoryControl
    
brain = Brain()

brain.register_module(

    "memory_control",
    MemoryControl(brain.memory)
)
    
    