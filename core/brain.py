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
from core.language_pipeline import LanguagePipeline


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
        self.language = LanguagePipeline()

    def register_module(self, name, module):
        self.modules[name] = module

    def process(self, message):

        # ==============================
        # INPUT ORIGINAL
        # ==============================

        original_message = normalizar(message)

        # ==============================
        # PIPELINE
        # ==============================

        tokens = self.language.processar(original_message)

        processed_message = " ".join(tokens)

        # salva histórico
        self.context.add_message(processed_message)

        # ==============================
        # CONTEXTO
        # ==============================

        topic = self.context.get_topic()

        if topic:

            pronomes = ["ele", "ela", "dele", "dela", "isso"]

            palavras = processed_message.split()

            palavras = [topic if p in pronomes else p for p in palavras]

            processed_message = " ".join(palavras)

        # ==============================
        # NLP INTENT
        # ==============================

        intent = self.nlp.detectar(processed_message)

        if intent:

            module = self.modules.get(intent)

            if module and hasattr(module, "handle"):

                response = module.handle(processed_message)

                if response:
                    return self.personality.aplicar(response)

        # ==============================
        # CÁLCULOS
        # ==============================

        if original_message.startswith("calcule") or original_message.startswith("quanto e"):

            expression = original_message.replace("calcule", "").replace("quanto e", "").strip()

            allowed = "0123456789+-*/(). "

            if all(c in allowed for c in expression):

                try:
                    result = eval(expression)
                    return self.personality.aplicar(f"O resultado é {result}")

                except:
                    return self.personality.aplicar("Não consegui calcular essa conta.")

        # ==============================
        # HORÁRIO
        # ==============================

        if "hora" in original_message:

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

            return self.personality.aplicar(
                f"Agora são {agora.strftime('%H:%M')}"
            )

        # ==============================
        # DATA
        # ==============================

        if "dia" in original_message or "data" in original_message:

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

            return self.personality.aplicar(
                f"Hoje é {agora.strftime('%d/%m/%Y')}"
            )

        # ==============================
        # SAUDAÇÕES
        # ==============================

        if original_message.startswith("bom dia"):
            return self.personality.aplicar(f"Bom dia, {obter_usuario()}.")

        if original_message.startswith("boa tarde"):
            return self.personality.aplicar(f"Boa tarde, {obter_usuario()}.")

        if original_message.startswith("boa noite"):
            return self.personality.aplicar(f"Boa noite, {obter_usuario()}.")

        if original_message in ["oi", "ola", "opa", "eai", "fala"]:
            return self.personality.aplicar(f"Oi, {obter_usuario()}.")

        # ==============================
        # IDENTIDADE
        # ==============================

        if "quem e voce" in original_message:
            return self.personality.aplicar(f"Eu sou {obter_nome()}.")

        if "seu nome" in original_message:
            return self.personality.aplicar(f"Meu nome é {obter_nome()}.")

        if "quem te criou" in original_message:
            return self.personality.aplicar(f"Fui criada por {obter_criador()}.")

        if "quem sou eu" in original_message:
            return self.personality.aplicar(f"Você é {obter_usuario()}, meu criador.")

        if "se apresente" in original_message:
            return self.personality.aplicar(apresentar())

        # ==============================
        # MEMÓRIA (APENAS COM COMANDO)
        # ==============================

        if original_message.startswith("memoria"):

            keyword = original_message.replace("memoria", "").strip()

            results = self.memory.search(keyword)

            if results:
                return self.personality.aplicar(f"Encontrei: {results}")

            return self.personality.aplicar("Nada encontrado.")

        if "o que voce lembra" in original_message:

            data = self.memory.data

            if data:
                return self.personality.aplicar(str(data))

            return self.personality.aplicar("Ainda não tenho registros.")

        # ==============================
        # LEMBRETES
        # ==============================

        if "listar lembretes" in original_message:
            return self.personality.aplicar(str(listar()))

        # ==============================
        # PESQUISA EXPLÍCITA
        # ==============================

        if original_message.startswith("pesquise"):

            pergunta = original_message.replace("pesquise", "").strip()

            self.context.update_topic(pergunta)

            response = buscar_web(pergunta)

            if response:
                return self.personality.aplicar(response)

        # ==============================
        # KNOWLEDGE
        # ==============================

        response = buscar_conhecimento(processed_message)

        if response:
            return self.personality.aplicar(response)

        # ==============================
        # INTERNET AUTOMÁTICA
        # ==============================

        perguntas_web = [
            "quem",
            "quando",
            "onde",
            "como",
            "por que",
            "o que",
            "qual",
            "quantos",
            "quantas"
        ]

        palavras = original_message.split()

        if palavras and palavras[0] in perguntas_web:

            response = buscar_web(original_message)

            if response:

                aprender(processed_message, response)

                return self.personality.aplicar(response)

        return self.personality.aplicar(
            "Ainda não encontrei uma resposta para isso."
        )


from core.modules.memory_control import MemoryControl

brain = Brain()

brain.register_module(
    "memory_control",
    MemoryControl(brain.memory)
)