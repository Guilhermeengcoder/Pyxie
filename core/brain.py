# =============================================================
# core/brain.py — Cérebro Central da PYXIE
# =============================================================

import random
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from core.module_loader import carregar_modulos
from core.memory import Memory
from core.identity import obter_nome, obter_criador, obter_usuario, apresentar
from core.personality import Personality
from core.internet import buscar_web
from core.knowledge import buscar_conhecimento, aprender
from core.reminder import adicionar, listar
from core.context import Context
from core.language_pipeline import LanguagePipeline
from core.conversation_memory import ConversationMemory
from core.decision import decidir
from core.memory_extractor import extrair_e_salvar
from core.memory_manager import gerar_contexto_para_prompt
from core.memory.short_term import ShortTermMemory
from core.memory.session_memory import session_memory

from modules.ollama_ai import perguntar_ollama


# =============================================================
# FUNÇÕES AUXILIARES
# =============================================================

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


# =============================================================
# BRAIN — CLASSE ÚNICA
# =============================================================

class Brain:

    def __init__(self):
        self.memory      = Memory()
        self.modules     = carregar_modulos()
        self.personality = Personality()
        self.context     = Context()
        self.language    = LanguagePipeline()
        self.conv_memory = ConversationMemory(limite=5)
        self.stm         = ShortTermMemory()
       
        session_memory.start_session()

    def register_module(self, name, module):
        self.modules[name] = module

    # ----------------------------------------------------------
    # ENTRY POINT
    # ----------------------------------------------------------

    def process(self, message):

        # ------------------------------------------------------
        # STM — verifica expiração
        # ------------------------------------------------------
        if self.stm.is_expired():
            self.stm.clear()

        # ------------------------------------------------------
        # NORMALIZAÇÃO
        # ------------------------------------------------------
        original_message = normalizar(message)

        if original_message.startswith("pyxie"):
            original_message = original_message.replace("pyxie", "", 1).strip()

        resultado         = self.language.processar(original_message)
        processed_message = resultado["corrigido"]

        # ✅ CORREÇÃO AQUI
        self.stm.add_message("user", processed_message)

        self.context.add_message(processed_message)

        # 🔥 EXTRAÇÃO DE MEMÓRIA AUTOMÁTICA
        extrair_e_salvar(message)

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

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(message, resposta_final)
            return resposta_final

        if original_message.startswith("boa tarde"):
            resposta = f"Boa tarde, {obter_usuario()}."
            pergunta = extrair_pergunta(original_message)

            if pergunta:
                resposta_ia = perguntar_ollama(pergunta, "")
                if resposta_ia:
                    resposta += " " + resposta_ia

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(message, resposta_final)
            return resposta_final

        if original_message.startswith("boa noite"):
            resposta = f"Boa noite, {obter_usuario()}."
            pergunta = extrair_pergunta(original_message)

            if pergunta:
                resposta_ia = perguntar_ollama(pergunta, "")
                if resposta_ia:
                    resposta += " " + resposta_ia

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # DECISÃO CENTRAL
        # --------------------------------------------------

        decisao   = decidir(original_message, self.context)
        categoria = decisao.get("destino")
        modulo    = categoria

        modulos_candidatos = []

        if categoria:
            for m in self.modules.values():
                if getattr(m, "category", None) == categoria:
                    modulos_candidatos.append(m)

        if not modulos_candidatos:
            modulos_candidatos = list(self.modules.values())

        for modulo_instancia in modulos_candidatos:
            try:
                if hasattr(modulo_instancia, "handle"):
                    resposta = modulo_instancia.handle(processed_message)
                elif hasattr(modulo_instancia, "run"):
                    resposta = modulo_instancia.run(processed_message)
                else:
                    continue

                if resposta:
                    resposta_final = self.personality.aplicar(resposta)
                    self._finalizar(message, resposta_final)
                    return resposta_final

            except Exception as e:
                print(f"[ERRO módulo {modulo_instancia.name}]: {e}")

        # --------------------------------------------------
        # MÓDULOS INTERNOS
        # --------------------------------------------------

        if modulo == "saudacao":
            respostas = [
                f"Oi, {obter_usuario()}.",
                f"Olá, {obter_usuario()}.",
                f"E aí, {obter_usuario()}."
            ]
            resposta_final = self.personality.aplicar(random.choice(respostas))
            self._finalizar(message, resposta_final)
            return resposta_final

        if modulo == "hora":
            module = self.modules.get("hora")
            if module and hasattr(module, "run"):
                response = module.run(original_message)
                if response:
                    resposta_final = self.personality.aplicar(response)
                    self._finalizar(message, resposta_final)
                    return resposta_final

        if modulo == "identidade":
            if "se apresente" in original_message or "apresente" in original_message:
                resposta_final = self.personality.aplicar(apresentar())
            else:
                resposta_final = self.personality.aplicar(
                    f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
                )
            self._finalizar(message, resposta_final)
            return resposta_final

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
                    resposta_final = self.personality.aplicar(f"O resultado é {result}")
                    self._finalizar(message, resposta_final)
                    return resposta_final
                except Exception:
                    pass
            resposta_final = self.personality.aplicar("Não consegui calcular essa conta.")
            self._finalizar(message, resposta_final)
            return resposta_final

        if modulo in ("internet", "internet_explicita", "pesquisa"):
            pergunta = limpar_pergunta(original_message)

            if len(pergunta.split()) >= 2:
                self.context.set_entity(pergunta)

            self.context.update_topic(pergunta)
            query    = melhorar_query(pergunta, self.context)
            response = buscar_web(query)

            if response:
                aprender(processed_message, response)
                extrair_e_salvar(message, response, pergunta)
                resposta_final = self.personality.aplicar(response)
                self._finalizar(message, resposta_final)
                return resposta_final

            resposta_final = self.personality.aplicar(
                "Tive dificuldade para acessar a internet agora."
            )
            self._finalizar(message, resposta_final)
            return resposta_final

        if modulo == "memoria":
            conteudo = (
                processed_message
                .replace("lembre que", "")
                .replace("lembrar que", "")
                .strip()
            )
            palavras  = conteudo.split()
            categoria = palavras[0] if palavras else "nota"
            self.memory.remember(categoria, conteudo)
            self.context.update_topic(categoria)

            extrair_e_salvar(message)
            resposta_final = self.personality.aplicar("Informação salva.")
            self._finalizar(message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # RESPOSTAS FIXAS
        # --------------------------------------------------

        if "quem sou eu" in original_message:
            resposta_final = self.personality.aplicar(
                f"Você é {obter_usuario()}, meu usuário."
            )
            self._finalizar(message, resposta_final)
            return resposta_final

        if "quem e voce" in original_message or "quem e vc" in original_message:
            resposta_final = self.personality.aplicar(
                f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
            )
            self._finalizar(message, resposta_final)
            return resposta_final

        if "quem te criou" in original_message:
            resposta_final = self.personality.aplicar(
                f"Eu fui criada por {obter_criador()}."
            )
            self._finalizar(message, resposta_final)
            return resposta_final

        if "qual e o seu proposito" in original_message or "qual seu proposito" in original_message:
            resposta_final = self.personality.aplicar(
                "Meu propósito é te ajudar, aprender com você e facilitar suas tarefas no dia a dia."
            )
            self._finalizar(message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # CONHECIMENTO LOCAL
        # --------------------------------------------------

        response = buscar_conhecimento(processed_message)
        if response:
            resposta_final = self.personality.aplicar(response)
            self._finalizar(message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # FALLBACK FINAL — Ollama com contexto completo
        # --------------------------------------------------

        contexto_stm       = self.stm.get_context()          # ← STM agora alimenta o Ollama
        contexto_memoria_db = gerar_contexto_para_prompt(original_message)
        contexto_extra      = self.context.get_entity() or ""

        # monta string de contexto histórico para perguntar_ollama
        contexto_historico = ""
        for m in contexto_stm:
            if m["role"] == "system":
                contexto_historico += m["content"] + "\n\n"
            elif m["role"] == "user":
                contexto_historico += f"Usuário: {m['content']}\n"
            elif m["role"] == "assistant":
                contexto_historico += f"PYXIE: {m['content']}\n"

        contexto_final = (
            contexto_memoria_db + "\n\n" +
            contexto_historico  + "\n\n" +
            contexto_extra
        )

        try:
            response = perguntar_ollama(original_message, contexto_final)
        except Exception:
            response = None

        if response:
            resposta_final = self.personality.aplicar(response)
            self.conv_memory.adicionar(message, resposta_final)
            extrair_e_salvar(message, resposta_final, self.context.get_topic())
            self._finalizar(message, resposta_final)
            return resposta_final

        resposta_final = self.personality.aplicar("Ainda não encontrei uma resposta para isso.")
        self._finalizar(message, resposta_final)
        return resposta_final

    # ----------------------------------------------------------
    # FINALIZAÇÃO — STM + SessionMemory após cada resposta
    # ----------------------------------------------------------

    def _finalizar(self, user_input: str, resposta: str):
        """
        Registra a resposta na STM e na SessionMemory.
        Chamado em todos os pontos de retorno do process().
        """
        self.stm.add_message("assistant", resposta)

        try:
            session_memory.add_turn(
                user_input=user_input,
                pyxie_response=resposta,
            )
        except Exception as e:
            print(f"[WARN] SessionMemory não registrou turno: {e}")

# =============================================================
# INSTÂNCIA GLOBAL
# =============================================================

from core.memory_control import MemoryControl
from modules.hora import Module as HoraModule

brain = Brain()
brain.register_module("memory_control", MemoryControl())
brain.register_module("hora", HoraModule())