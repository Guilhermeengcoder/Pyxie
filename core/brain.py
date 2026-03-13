import random
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from core.memory import Memory
from core.identity import obter_nome, obter_criador, obter_usuario, apresentar
from core.personality import Personality
from core.internet import buscar_web
from core.knowledge import buscar_conhecimento, aprender
from core.reminder import adicionar, listar
from core.nlp_intent import NLPIntent
from core.context import Context


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto


class Brain:

    def __init__(self):

        self.memory = Memory()
        self.modules = {}
        self.nlp = NLPIntent()
        self.personality = Personality()
        self.context = Context()

    def register_module(self, name, module):
        self.modules[name] = module

    def process(self, message):

        message = normalizar(message)

        # salva histórico
        self.context.add_message(message)

        # ==============================
        # CONTEXTO
        # ==============================

        topic = self.context.get_topic()

        if topic:

            pronomes = ["ele", "ela", "dele", "dela", "isso"]

            palavras = message.split()

            palavras = [topic if p in pronomes else p for p in palavras]

            message = " ".join(palavras)

            perguntas_contexto = ["quando", "onde", "como", "por que", "quem", "qual"]

            if palavras and palavras[0] in perguntas_contexto and topic not in message:

                message = f"{message} {topic}"

        # ==============================
        # NLP INTENT
        # ==============================

        intent = self.nlp.detectar(message)

        if intent:

            module = self.modules.get(intent)

            if module and hasattr(module, "handle"):

                response = module.handle(message)

                if response:
                    return self.personality.aplicar(response)

        # ==============================
        # CÁLCULOS
        # ==============================

        if message.startswith("calcule") or message.startswith("quanto e"):

            expression = message.replace("calcule", "").replace("quanto e", "").strip()
            expression = expression.replace("?", "").replace("=", "")

            allowed = "0123456789+-*/(). "

            if all(c in allowed for c in expression):

                try:
                    result = eval(expression)
                    return self.personality.aplicar(f"O resultado é {result}")

                except:
                    return self.personality.aplicar("Não consegui calcular essa conta.")

            else:
                return self.personality.aplicar("Expressão inválida.")

        # ==============================
        # HORÁRIO
        # ==============================

        if "hora" in message or "horas" in message:

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

            return self.personality.aplicar(
                f"Agora são {agora.strftime('%H:%M')}"
            )

        # ==============================
        # SAUDAÇÕES (corrigido)
        # ==============================

        greetings = [
            "Olá 👋",
            f"Oi, {obter_usuario()}.",
            "Estou aqui.",
            "PYXIE presente.",
            "Sempre pronta."
        ]

        palavras = message.split()

        saudacoes = ["oi", "ola", "opa", "eai", "fala"]

        if palavras and palavras[0] in saudacoes:
            return self.personality.aplicar(random.choice(greetings))

        # ==============================
        # IDENTIDADE
        # ==============================

        if any(p in message for p in [
            "quem e voce",
            "quem e vc",
            "como voce se chama"
        ]):

            return self.personality.aplicar(f"Eu sou {obter_nome()}.")

        if "seu nome" in message:
            return self.personality.aplicar(f"Meu nome é {obter_nome()}.")

        if "se apresente" in message or "apresente se" in message:
            return self.personality.aplicar(apresentar())

        if "quem te criou" in message:
            return self.personality.aplicar(f"Fui criada por {obter_criador()}.")

        if "quem sou eu" in message:
            return self.personality.aplicar(f"Você é {obter_usuario()}, meu criador.")

        # ==============================
        # MEMÓRIA
        # ==============================

        if "o que voce lembra" in message or "o que voce sabe" in message:

            data = self.memory.data

            if data:
                return self.personality.aplicar(str(data))

            return self.personality.aplicar("Ainda não tenho registros.")

        if message.startswith("memoria"):

            keyword = message.replace("memoria", "").strip()

            results = self.memory.search(keyword)

            if results:
                return self.personality.aplicar(f"Encontrei: {results}")

            return self.personality.aplicar("Nada encontrado.")

        # ==============================
        # LEMBRETES
        # ==============================

        if "listar lembretes" in message:
            return self.personality.aplicar(str(listar()))

        if message.startswith("lembre-me"):

            try:

                partes = message.replace("lembre-me", "").strip().split(" as ")

                texto = partes[0]
                horario = partes[1]

                adicionar(texto, horario)

                return self.personality.aplicar("Lembrete adicionado 👍")

            except:

                return self.personality.aplicar("Use: lembre-me de X às HH:MM")

        # ==============================
        # PESQUISA EXPLÍCITA
        # ==============================

        if message.startswith("pesquise") or message.startswith("procure na internet"):

            pergunta = message.replace("pesquise", "").replace("procure na internet", "").strip()

            self.context.update_topic(pergunta)

            response = buscar_web(pergunta)

            if response:
                return self.personality.aplicar(response)

            return self.personality.aplicar("Não encontrei nada relevante.")

        # ==============================
        # KNOWLEDGE ENGINE
        # ==============================

        response = buscar_conhecimento(message)

        if response:
            return self.personality.aplicar(response)

        # ==============================
        # INTERNET AUTOMÁTICA INTELIGENTE
        # ==============================

        perguntas_web = [
            "quem",
            "quando",
            "onde",
            "como",
            "por que",
            "o que",
            "qual"
        ]

        palavras = message.split()

        if palavras and palavras[0] in perguntas_web:

            response = buscar_web(message)

            if response:

                aprender(message, response)

                return self.personality.aplicar(response)

        # ==============================

        return self.personality.aplicar(
            "Ainda não encontrei uma resposta para isso."
        )


from core.modules.memory_control import MemoryControl

brain = Brain()

brain.register_module(
    "memory_control",
    MemoryControl(brain.memory)
)