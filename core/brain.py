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
from core.context import Context
from core.language_pipeline import LanguagePipeline
from core.conversation_memory import ConversationMemory
from core.router import decidir

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
        "me fale sobre", "fale sobre", "me diga sobre", "diga sobre",
        "quero saber sobre", "procure por", "procure", "pesquise", "sobre"
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


def extrair_pergunta(texto):
    partes = texto.split(",")
    if len(partes) > 1:
        return partes[1].strip()
    return None


class Brain:

    def __init__(self):
        self.memory = Memory()
        self.modules = {}
        self.personality = Personality()
        self.context = Context()
        self.language = LanguagePipeline()
        self.conv_memory = ConversationMemory(limite=5)

    def register_module(self, name, module):
        self.modules[name] = module

    # --------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------

    def process(self, message):

        original_message = normalizar(message)

        if original_message.startswith("pyxie"):
            original_message = original_message.replace("pyxie", "", 1).strip()

        tokens = self.language.processar(original_message)
        processed_message = " ".join(tokens)

        self.context.add_message(processed_message)

        # Resolução de pronomes via contexto
        entity = self.context.get_entity() or self.context.get_topic()

        if entity:
            pronomes = ["ele", "ela", "dele", "dela", "isso", "esse", "essa"]
            palavras = processed_message.split()
            palavras = [entity if p in pronomes else p for p in palavras]
            processed_message = " ".join(palavras)

        # --------------------------------------------------
        # CUMPRIMENTOS
        # --------------------------------------------------

        if original_message.startswith("bom dia"):
            try:
                agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            except Exception:
                agora = datetime.now()

            resposta = f"Bom dia, {obter_usuario()}. Hoje é {agora.strftime('%d/%m/%Y')}."
            pergunta = extrair_pergunta(original_message)

            if pergunta:
                resposta_ia = perguntar_ollama(pergunta, "")
                if resposta_ia:
                    resposta += " " + resposta_ia

            return self.personality.aplicar(resposta)

        if original_message.startswith("boa tarde"):
            resposta = f"Boa tarde, {obter_usuario()}."
            pergunta = extrair_pergunta(original_message)

            if pergunta:
                resposta_ia = perguntar_ollama(pergunta, "")
                if resposta_ia:
                    resposta += " " + resposta_ia

            return self.personality.aplicar(resposta)

        if original_message.startswith("boa noite"):
            resposta = f"Boa noite, {obter_usuario()}."
            pergunta = extrair_pergunta(original_message)

            if pergunta:
                resposta_ia = perguntar_ollama(pergunta, "")
                if resposta_ia:
                    resposta += " " + resposta_ia

            return self.personality.aplicar(resposta)

        # --------------------------------------------------
        # 🔥 DECISÃO CENTRALIZADA VIA ROUTER
        # --------------------------------------------------

        decisao = decidir(original_message, self.context)
        modulo = decisao["modulo"]

        # --------------------------------------------------
        # MÓDULOS EXTERNOS REGISTRADOS
        # ✅ CORRIGIDO: só executa o módulo escolhido
        # --------------------------------------------------

        modulo_instancia = self.modules.get(modulo)

        if modulo_instancia and hasattr(modulo_instancia, "handle"):
            resposta = modulo_instancia.handle(processed_message)
            if resposta:
                return self.personality.aplicar(resposta)

        # --------------------------------------------------
        # HANDLERS INTERNOS POR MÓDULO
        # --------------------------------------------------

        if modulo == "saudacao":
            respostas = [
                f"Oi, {obter_usuario()}.",
                f"Olá, {obter_usuario()}.",
                f"E aí, {obter_usuario()}."
            ]
            return self.personality.aplicar(random.choice(respostas))

        if modulo == "hora":
            module = self.modules.get("hora")
            if module and hasattr(module, "run"):
                response = module.run(original_message)
                if response:
                    return self.personality.aplicar(response)

        if modulo == "identidade":
            if "se apresente" in original_message or "apresente" in original_message:
                return self.personality.aplicar(apresentar())
            return self.personality.aplicar(
                f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
            )

        if modulo == "calculo":
            expression = (
                processed_message
                .replace("calcule", "")
                .replace("quanto e", "")
                .strip()
            )
            allowed = "0123456789+-*/(). "
            if all(c in allowed for c in expression):
                try:
                    result = eval(expression)
                    return self.personality.aplicar(f"O resultado é {result}")
                except Exception:
                    pass
            return self.personality.aplicar("Não consegui calcular essa conta.")

        if modulo in ("internet", "pesquisa"):
            pergunta = limpar_pergunta(original_message)

            if len(pergunta.split()) >= 2:
                self.context.set_entity(pergunta)

            self.context.update_topic(pergunta)
            query = melhorar_query(pergunta, self.context)
            response = buscar_web(query)

            if response:
                aprender(processed_message, response)
                return self.personality.aplicar(response)

            return self.personality.aplicar(
                "Tive dificuldade para acessar a internet agora."
            )

        if modulo == "memoria":
            conteudo = (
                processed_message
                .replace("lembre que", "")
                .replace("lembrar que", "")
                .strip()
            )
            palavras = conteudo.split()
            categoria = palavras[0] if palavras else "nota"
            self.memory.remember(categoria, conteudo)
            self.context.update_topic(categoria)
            return self.personality.aplicar("Informação salva.")

        # --------------------------------------------------
        # RESPOSTAS FIXAS
        # --------------------------------------------------

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

        if "qual e o seu proposito" in original_message or "qual seu proposito" in original_message:
            return self.personality.aplicar(
                "Meu propósito é te ajudar, aprender com você e facilitar suas tarefas no dia a dia."
            )

        # --------------------------------------------------
        # CONHECIMENTO LOCAL
        # --------------------------------------------------

        response = buscar_conhecimento(processed_message)
        if response:
            return self.personality.aplicar(response)

        # --------------------------------------------------
        # FALLBACK FINAL: OLLAMA COM MEMÓRIA
        # --------------------------------------------------

        contexto_memoria = self.conv_memory.gerar_contexto()
        contexto_extra = self.context.get_entity() or ""
        contexto_final = contexto_memoria + "\n" + contexto_extra

        try:
            response = perguntar_ollama(original_message, contexto_final)
        except Exception:
            response = None

        if response:
            resposta_final = self.personality.aplicar(response)
            self.conv_memory.adicionar(message, resposta_final)
            return resposta_final

        return self.personality.aplicar("Ainda não encontrei uma resposta para isso.")


# =========================
# INSTÂNCIA GLOBAL
# =========================

from core.memory_control import MemoryControl
from modules.hora import Module as HoraModule

brain = Brain()
brain.register_module("memory_control", MemoryControl(brain.memory))
brain.register_module("hora", HoraModule())