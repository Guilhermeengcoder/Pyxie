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

# 🔥 NOVO IMPORT (única adição real)
from modules.ollama_ai import perguntar_ollama


def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    for c in [",", ".", "?", "!", ":"]:
        texto = texto.replace(c, "")

    texto = texto.replace("oque", "o que")

    return texto


def limpar_pergunta(pergunta):
    remover = [
        "me fale sobre",
        "fale sobre",
        "me diga sobre",
        "diga sobre",
        "quero saber sobre",
        "procure por",
        "procure",
        "pesquise",
        "sobre"
    ]

    for r in remover:
        pergunta = pergunta.replace(r, "")

    return pergunta.strip()


def melhorar_query(pergunta, context):

    entity = context.get_entity()

    if "idade" in pergunta or "quantos anos" in pergunta:
        if entity:
            return f"{entity} idade"

    if "quando nasceu" in pergunta:
        if entity:
            return f"{entity} data de nascimento"

    if "onde nasceu" in pergunta:
        if entity:
            return f"{entity} local de nascimento"

    if "quando foi criado" in pergunta:
        if entity:
            return f"{entity} historia criacao"

    if entity and len(pergunta.split()) <= 3:
        return f"{entity} {pergunta}"

    return pergunta


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

        original_message = normalizar(message)

        if original_message.startswith("pyxie"):
            original_message = original_message.replace("pyxie", "", 1).strip()

        tokens = self.language.processar(original_message)
        processed_message = " ".join(tokens)

        self.context.add_message(processed_message)

        entity = self.context.get_entity() or self.context.get_topic()

        if entity:
            pronomes = ["ele", "ela", "dele", "dela", "isso", "esse", "essa"]
            palavras = processed_message.split()
            palavras = [entity if p in pronomes else p for p in palavras]
            processed_message = " ".join(palavras)

        intent = self.nlp.detectar(processed_message)

        if intent:
            self.context.set_intent(intent)

            if intent == "saudacao":
                respostas = [
                    f"Oi, {obter_usuario()}.",
                    f"Olá, {obter_usuario()}.",
                    f"E aí, {obter_usuario()}."
                ]
                return self.personality.aplicar(random.choice(respostas))

            if intent == "hora":
                try:
                    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
                except:
                    agora = datetime.now()

                return self.personality.aplicar(
                    f"Agora são {agora.strftime('%H:%M')}"
                )

            if intent == "identidade":
                return self.personality.aplicar(
                    f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
                )

            if intent == "calculo":
                expression = processed_message.replace("calcule", "").replace("quanto e", "").strip()
                allowed = "0123456789+-*/(). "

                if all(c in allowed for c in expression):
                    try:
                        result = eval(expression)
                        return self.personality.aplicar(f"O resultado é {result}")
                    except:
                        return self.personality.aplicar("Não consegui calcular essa conta.")

            if intent == "pesquisa":
                pergunta = limpar_pergunta(original_message)

                if len(pergunta.split()) >= 2:
                    self.context.set_entity(pergunta)

                self.context.update_topic(pergunta)

                query = melhorar_query(pergunta, self.context)
                response = buscar_web(query)

                if response is not None and response != "":
                    return self.personality.aplicar(response)

                return self.personality.aplicar(
                    "Tive dificuldade para acessar a internet agora."
                )

            if intent == "memoria":
                response = adicionar(processed_message)

                if response is not None and response != "":
                    return self.personality.aplicar(response)

            module = self.modules.get(intent)

            if module and hasattr(module, "handle"):
                response = module.handle(processed_message)

                if response is not None and response != "":
                    return self.personality.aplicar(response)

        if original_message.startswith("bom dia"):
            try:
                agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            except:
                agora = datetime.now()

            return self.personality.aplicar(
                f"Bom dia, {obter_usuario()}. Hoje é {agora.strftime('%d/%m/%Y')}."
            )

        if original_message.startswith("boa tarde"):
            return self.personality.aplicar(f"Boa tarde, {obter_usuario()}.")

        if original_message.startswith("boa noite"):
            return self.personality.aplicar(f"Boa noite, {obter_usuario()}.")

        if original_message in ["oi", "ola", "opa", "eai", "fala"]:
            return self.personality.aplicar(f"Oi, {obter_usuario()}.")

        if "quem sou eu" in original_message:
            return self.personality.aplicar(
                f"Você é {obter_usuario()}, meu usuário."
            )

        if "quem e voce" in original_message or "quem e vc" in original_message:
            return self.personality.aplicar(
                f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
            )

        if "quem te criou" in original_message:
            return self.personality.aplicar(
                f"Eu fui criada por {obter_criador()}."
            )

        if "se apresente" in original_message or "apresente-se" in original_message:
            return self.personality.aplicar(apresentar())

        if original_message.startswith("calcule") or original_message.startswith("quanto e"):
            expression = original_message.replace("calcule", "").replace("quanto e", "").strip()
            allowed = "0123456789+-*/(). "

            if all(c in allowed for c in expression):
                try:
                    result = eval(expression)
                    return self.personality.aplicar(f"O resultado é {result}")
                except:
                    return self.personality.aplicar("Não consegui calcular essa conta.")

        if "hora" in original_message:
            try:
                agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            except:
                agora = datetime.now()

            return self.personality.aplicar(
                f"Agora são {agora.strftime('%H:%M')}"
            )

        if "data" in original_message:
            try:
                agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            except:
                agora = datetime.now()

            return self.personality.aplicar(
                f"Hoje é {agora.strftime('%d/%m/%Y')}"
            )

        if "pesquise" in original_message or "procure" in original_message:
            pergunta = limpar_pergunta(original_message)

            if len(pergunta.split()) <= 2:
                entity = self.context.get_entity()
                if entity:
                    pergunta = entity

            self.context.update_topic(pergunta)

            query = melhorar_query(pergunta, self.context)
            response = buscar_web(query)

            if response is not None and response != "":
                return self.personality.aplicar(response)

            return self.personality.aplicar(
                "Tive dificuldade para acessar a internet agora."
            )

        response = buscar_conhecimento(processed_message)

        if response is not None and response != "":
            return self.personality.aplicar(response)

        perguntas_web = [
            "quem", "quando", "onde", "como",
            "por que", "o que", "qual",
            "quantos", "quantas"
        ]

        palavras = original_message.split()

        if palavras and palavras[0] in perguntas_web:

            pergunta = limpar_pergunta(original_message)

            if len(pergunta.split()) <= 2:
                entity = self.context.get_entity()
                if entity:
                    pergunta = entity

            query = melhorar_query(pergunta, self.context)
            response = buscar_web(query)

            if response is not None and response != "":
                aprender(processed_message, response)
                return self.personality.aplicar(response)

            return self.personality.aplicar(
                "Não consegui buscar isso na internet agora."
            )

        # 🔥 AQUI ESTÁ O OLLAMA (fallback final)
        contexto = self.context.get_entity() or ""
        response = perguntar_ollama(original_message, contexto)
        
        if response is not None and response != "":
            return self.personality.aplicar(response)

        return self.personality.aplicar(
            "Ainda não encontrei uma resposta para isso."
        )


from core.memory_control import MemoryControl

brain = Brain()

brain.register_module(
    "memory_control",
    MemoryControl(brain.memory)
)