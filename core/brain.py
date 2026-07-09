# =============================================================
# core/brain.py — Cérebro Central da PYXIE
# =============================================================

import ast
import random
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from core.multi_task import dividir_tarefas, tem_multiplas_tarefas
from core.module_loader import carregar_modulos
from core.identity import obter_nome, obter_criador, obter_usuario, apresentar
from core.personality import Personality
from core.internet import buscar_web
from core.knowledge import buscar_conhecimento, aprender
from core.reminder import adicionar, listar
from core.context import Context
from core.language_pipeline import LanguagePipeline
from core.decision import decidir
from core.memory.short_term import ShortTermMemory


from core.memory.LTM import (
    extrair_e_salvar,
    gerar_contexto_para_prompt,
    salvar_permanente,
    apagar_memoria,
    detectar_comando_memoria,
    limpar_expirados,
)

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
    if entity and len(pergunta.split()) <= 3:
        return f"{entity} {pergunta}"
    return pergunta


def extrair_pergunta(texto):
    partes = texto.split(",")
    if len(partes) > 1:
        return partes[1].strip()
    return None


def calcular_seguro(expression: str):
    """
    Avalia expressões matemáticas simples sem usar eval().
    Suporta: + - * / ** () e números decimais.
    Lança ValueError se a expressão contiver algo não permitido.
    """
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError:
        raise ValueError("Expressão inválida.")

    NODES_PERMITIDOS = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div,
        ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd,
    )

    for node in ast.walk(tree):
        if not isinstance(node, NODES_PERMITIDOS):
            raise ValueError(f"Operação não permitida: {type(node).__name__}")

    return eval(compile(tree, "<string>", "eval"))


# =============================================================
# BRAIN — CLASSE ÚNICA
# =============================================================

class Brain:

    def __init__(self):
        self.modules     = carregar_modulos()
        self.personality = Personality()
        self.context     = Context()
        self.language    = LanguagePipeline()
        self.stm         = ShortTermMemory()

        limpar_expirados()

    def register_module(self, name, module):
        self.modules[name] = module

    # ----------------------------------------------------------
    # ENTRY POINT — lida com múltiplas tarefas
    # ----------------------------------------------------------

    def process(self, message):

        if tem_multiplas_tarefas(message):
            tarefas = dividir_tarefas(message)
            respostas = []

            for tarefa in tarefas:
                resp = self._processar_unica(tarefa)
                if resp:
                    respostas.append(resp)

            if respostas:
                return "\n".join(respostas)

        return self._processar_unica(message)

    # ----------------------------------------------------------
    # PROCESSAMENTO DE UMA ÚNICA TAREFA
    # ----------------------------------------------------------

    def _processar_unica(self, message):

        if self.stm.is_expired():
            self.stm.clear()

        original_message = normalizar(message)

        if original_message.startswith("pyxie"):
            original_message = original_message.replace("pyxie", "", 1).strip()

        resultado         = self.language.processar(original_message)
        processed_message = resultado["corrigido"]

        self.stm.add_message("user", processed_message)
        self.context.add_message(processed_message)

        # ------------------------------------------------------
        # COMANDO DE MEMÓRIA EXPLÍCITA ("se lembre que X")
        # ------------------------------------------------------
        comando_mem = detectar_comando_memoria(message)
        if comando_mem:
            acao, conteudo = comando_mem
            if acao == "salvar":
                salvar_permanente(conteudo)
                resposta_final = self.personality.aplicar("Anotado. Vou lembrar disso.")
                self._finalizar(message, resposta_final)
                return resposta_final
            elif acao == "apagar":
                apagou = apagar_memoria(conteudo)
                msg = "Memória apagada." if apagou else "Não encontrei nada para apagar."
                resposta_final = self.personality.aplicar(msg)
                self._finalizar(message, resposta_final)
                return resposta_final

        # ------------------------------------------------------
        # EXTRAÇÃO AUTOMÁTICA DE FATOS DO USUÁRIO
        # ------------------------------------------------------
        extrair_e_salvar(message)

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
            try:
                result = calcular_seguro(expression)
                resposta_final = self.personality.aplicar(f"O resultado é {result}")
                self._finalizar(message, resposta_final)
                return resposta_final
            except (ValueError, ZeroDivisionError):
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
                extrair_e_salvar(message, topico=pergunta)
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
            salvar_permanente(conteudo)
            self.context.update_topic(conteudo.split()[0] if conteudo else "nota")

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
        # FALLBACK FINAL — Ollama com contexto seletivo
        # --------------------------------------------------
        contexto_stm        = self.stm.get_context_seletivo(max_chars=1200)
        contexto_memoria_db = gerar_contexto_para_prompt(original_message)
        contexto_extra      = self.context.get_entity() or ""

        contexto_historico = ""
        for m in contexto_stm:
            if m["role"] == "system":
                contexto_historico += m["content"] + "\n\n"
            elif m["role"] == "user":
                contexto_historico += f"Usuário: {m['content']}\n"
            elif m["role"] == "assistant":
                contexto_historico += f"PYXIE: {m['content']}\n"

        contexto_final = (
            contexto_memoria_db[:400] + "\n\n" +
            contexto_historico        + "\n\n" +
            contexto_extra[:100]
        ).strip()

        try:
            response = perguntar_ollama(original_message, contexto_final)
        except Exception:
            response = None

        if response:
            resposta_final = self.personality.aplicar(response)
            extrair_e_salvar(message, topico=self.context.get_topic())
            self._finalizar(message, resposta_final)
            return resposta_final

        resposta_final = self.personality.aplicar("Ainda não encontrei uma resposta para isso.")
        self._finalizar(message, resposta_final)
        return resposta_final

    # ----------------------------------------------------------
    # FINALIZAÇÃO — STM 
    # ----------------------------------------------------------

    def _finalizar(self, user_input: str, resposta: str):
        self.stm.add_message("assistant", resposta)

# =============================================================
# INSTÂNCIA GLOBAL
# =============================================================

from core.memory_control import MemoryControl

brain = Brain()
brain.register_module("memory_control", MemoryControl())