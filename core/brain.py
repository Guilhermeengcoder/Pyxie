# =============================================================
# core/brain.py — Cérebro Central da PYXIE
# =============================================================

import ast
import re
import random
import unicodedata
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from core.multi_task import dividir_tarefas, tem_multiplas_tarefas
from core.module_loader import carregar_modulos
from core.identity import obter_nome, obter_criador, obter_usuario, apresentar
from core.personality import Personality
from core.knowledge import buscar_conhecimento
from core.reminder import adicionar, listar
from core.language_pipeline import LanguagePipeline
from core.decision import decidir
from core.chat_session import SessionManager, ChatSession
from core import memory_json

from core.llm import perguntar_llm, perguntar_llm_imagem


from futuro.LTM import (
    extrair_e_salvar,
    gerar_contexto_para_prompt,
    salvar_permanente,
    apagar_memoria,
    detectar_comando_memoria,
    limpar_expirados,
)


# =============================================================
# ACESSO À MEMÓRIA FIXA EM JSON
# =============================================================

# Localiza memory.json na raiz do projeto PYXIE.
# Exemplo: PYXIE/memory.json
ARQUIVO_MEMORIA_FIXA = Path(__file__).resolve().parent.parent / "memory.json"


def carregar_memoria_fixa():
    """
    Carrega as informações fixas armazenadas no memory.json.

    Retorna um dicionário com as informações do arquivo.
    Caso o arquivo não exista ou contenha JSON inválido,
    retorna um dicionário vazio sem interromper a PYXIE.
    """
    try:
        with ARQUIVO_MEMORIA_FIXA.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        if not isinstance(dados, dict):
            print("[ERRO] O memory.json precisa conter um objeto JSON.")
            return {}

        return dados

    except FileNotFoundError:
        print(f"[AVISO] Arquivo de memória fixa não encontrado: {ARQUIVO_MEMORIA_FIXA}")
        return {}

    except json.JSONDecodeError as erro:
        print(f"[ERRO] JSON inválido no memory.json: {erro}")
        return {}

    except OSError as erro:
        print(f"[ERRO] Não foi possível ler o memory.json: {erro}")
        return {}


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
        "me fale sobre",
        "fale sobre",
        "me diga sobre",
        "diga sobre",
        "quero saber sobre",
        "procure por",
        "procure",
        "pesquise",
        "sobre",
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
    partes = texto.split(",", 1)
    if len(partes) > 1:
        return partes[1].strip()
    return None


def detectar_nome_apresentado(mensagem: str):
    """
    Procura uma apresentação do tipo "meu nome é X" / "me chamo X" /
    "pode me chamar de X" / "eu sou o/a X" na mensagem ORIGINAL da
    pessoa que está falando agora.

    Existe porque a PYXIE tem um usuário principal fixo (Guilherme, via
    obter_usuario()), mas outras pessoas também podem conversar com ela —
    e nesse caso a saudação não pode chamar todo mundo de "Guilherme".

    Retorna o nome (ex.: "Caio") ou None se ninguém se apresentou.
    """
    msg = mensagem.lower()

    padroes = [
        r"meu nome (?:e|é|eh)\s+([a-zà-ÿ]+)",
        r"pode me chamar de\s+([a-zà-ÿ]+)",
        r"me chamo\s+([a-zà-ÿ]+)",
        r"(?:eu\s+)?sou o\s+([a-zà-ÿ]+)",
        r"(?:eu\s+)?sou a\s+([a-zà-ÿ]+)",
    ]

    for padrao in padroes:
        encontrado = re.search(padrao, msg)
        if encontrado:
            return encontrado.group(1).capitalize()

    return None


def calcular_seguro(expression: str):
    """
    Avalia expressões matemáticas simples sem usar eval().
    Suporta: + - * / ** () e números decimais.
    Lança ValueError se a expressão contiver algo não permitido.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("Expressão inválida.")

    NODES_PERMITIDOS = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
    )

    for node in ast.walk(tree):
        if not isinstance(node, NODES_PERMITIDOS):
            raise ValueError(f"Operação não permitida: {type(node).__name__}")

    return eval(compile(tree, "<string>", "eval"))


LIMITE_MEMORIA_FIXA = 8000


def memoria_fixa_relevante(dados: dict, mensagem: str = "", limite: int = LIMITE_MEMORIA_FIXA) -> str:
    base = {k: v for k, v in dados.items() if k not in ("schema_version", "description")}

    partes, total, omitidas = [], 0, []

    for chave, valor in base.items():
        bloco = f'"{chave}":' + json.dumps(valor, ensure_ascii=False, separators=(",", ":"))

        if total + len(bloco) > limite:
            omitidas.append(chave)
            continue

        partes.append(bloco)
        total += len(bloco) + 1

    if omitidas:
        print(f"[memory.json] acima de {limite} caracteres; seções omitidas: {omitidas}")

    return "{" + ",".join(partes) + "}" if partes else ""


# =============================================================
# BRAIN — CLASSE ÚNICA
# =============================================================


class Brain:
    def __init__(self):
        self.modules = carregar_modulos()
        self.personality = Personality()
        self.language = LanguagePipeline()

        # Cada chat tem sua própria STM + Context (ver core/chat_session.py)
        self.sessions = SessionManager()

        # Memória fixa (memory.json) — global, vale para todos os chats
        self.memoria_fixa = carregar_memoria_fixa()

        limpar_expirados()

    def register_module(self, name, module):
        self.modules[name] = module

    def identificar_pessoa(self, message: str, sessao: ChatSession):
        """
        Descobre quem esta falando AGORA na conversa.

        Prioridade:
          1) nome apresentado NESTA mensagem ("meu nome e X") - se achar,
             tambem guarda no Context do chat para as proximas mensagens.
          2) nome ja apresentado antes, neste mesmo chat.
          3) o usuario principal (Guilherme), como padrao.
        """
        nome = detectar_nome_apresentado(message)

        if nome:
            sessao.context.set_pessoa(nome)
            return nome

        return sessao.context.get_pessoa() or obter_usuario()

    # ----------------------------------------------------------
    # EDIÇÃO DA MEMÓRIA FIXA (memory.json)
    # ----------------------------------------------------------

    def _editar_memoria_fixa(self, message):
        norm = normalizar(message)

        if memory_json.eh_pedido_de_desfazer(norm):
            if memory_json.desfazer():
                self.memoria_fixa = memory_json.carregar()
                return "Pronto, desfiz a última alteração na memória fixa."
            return "Não há nenhuma alteração para desfazer."

        try:
            dados = memory_json.carregar_estrito()
        except ValueError as e:
            return f"Não consegui ler o memory.json ({e}). Não alterei nada."

        # O contexto não vazio evita que o prompt peça um cumprimento
        try:
            texto = perguntar_llm(
                memory_json.montar_prompt_edicao(message, dados),
                "(tarefa técnica, sem cumprimentos)",
            )
        except Exception:
            texto = None

        if not texto:
            return "O modelo não respondeu agora (possível limite de cota). Não alterei nada."

        op = memory_json.extrair_operacao(texto)
        if not op:
            return (
                "Não entendi o que alterar. Tente algo como: "
                "salve no json que meu cachorro se chama Rex."
            )

        try:
            descricao = memory_json.aplicar_operacao(op)
        except ValueError as e:
            return f"Não alterei o JSON: {e}"

        self.memoria_fixa = memory_json.carregar()  # já vale na próxima mensagem
        return f"Memória fixa atualizada: {descricao}."

    # ----------------------------------------------------------
    # ENTRY POINT — lida com múltiplas tarefas
    # ----------------------------------------------------------

    def process(self, message, chat_id: str = "default"):
        sessao = self.sessions.get(chat_id)

        if (
            not memory_json.eh_pedido_de_edicao(normalizar(message))
            and tem_multiplas_tarefas(message)
        ):
            respostas = []

            for tarefa in dividir_tarefas(message):
                resp = self._processar_unica(tarefa, sessao)
                if resp:
                    respostas.append(resp)

            if respostas:
                return "\n".join(respostas)

        return self._processar_unica(message, sessao)

    # ----------------------------------------------------------
    # IMAGEM (anexo ou câmera) — chamado pela API quando há imagem
    # ----------------------------------------------------------

    def processar_imagem(self, message, imagem, chat_id: str = "default"):
        sessao = self.sessions.get(chat_id)

        if sessao.stm.is_expired():
            sessao.stm.clear()

        pergunta = (message or "").strip() or "Descreva o que você vê nesta imagem."

        # Histórico curto da conversa (a imagem em si não fica salva na memória)
        historico = ""
        for m in sessao.stm.get_context_seletivo(max_chars=4000):
            if m["role"] == "system":
                historico += m["content"] + "\n\n"
            elif m["role"] == "user":
                historico += f"Usuário: {m['content']}\n"
            elif m["role"] == "assistant":
                historico += f"PYXIE: {m['content']}\n"

        sessao.stm.add_message("user", f"[imagem enviada] {pergunta}")

        try:
            resposta = perguntar_llm_imagem(pergunta, imagem, historico)
        except Exception:
            resposta = None

        if not resposta:
            resposta = "Não consegui analisar essa imagem agora."

        resposta_final = self.personality.aplicar(resposta)
        self._finalizar(sessao, message, resposta_final)
        return resposta_final

    # ----------------------------------------------------------
    # PROCESSAMENTO DE UMA ÚNICA TAREFA
    # ----------------------------------------------------------

    
    def _processar_unica(self, message, sessao: ChatSession):

        if sessao.stm.is_expired():
            sessao.stm.clear()
            sessao.context.clear()

        # Salva o contexto anterior a esta mensagem.
        sessao.context_anterior = sessao.context.criar_snapshot()

        # Uma nova pergunta invalida os dados de regeneração anteriores.
        sessao.ultima_pergunta = None
        sessao.regeneracao_pergunta = None
        sessao.regeneracao_contexto = None

        original_message = normalizar(message)

        if original_message.startswith("pyxie"):
            original_message = original_message.replace("pyxie", "", 1).strip()

        resultado = self.language.processar(original_message)
        processed_message = resultado["corrigido"]

        sessao.stm.add_message("user", processed_message)
        sessao.context.add_message(processed_message)


        # ------------------------------------------------------
        # EDIÇÃO DA MEMÓRIA FIXA (memory.json)
        # ------------------------------------------------------
        if (
            memory_json.eh_pedido_de_edicao(original_message)
            or memory_json.eh_pedido_de_desfazer(original_message)
        ):
            resposta_final = self.personality.aplicar(self._editar_memoria_fixa(message))
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        # ------------------------------------------------------
        # COMANDO DE MEMÓRIA EXPLÍCITA ("se lembre que X")
        # ------------------------------------------------------
        comando_mem = detectar_comando_memoria(message)
        if comando_mem:
            acao, conteudo = comando_mem
            if acao == "salvar":
                salvar_permanente(conteudo)
                resposta_final = self.personality.aplicar("Anotado. Vou lembrar disso.")
                self._finalizar(sessao, message, resposta_final)
                return resposta_final
            elif acao == "apagar":
                apagou = apagar_memoria(conteudo)
                msg = (
                    "Memória apagada." if apagou else "Não encontrei nada para apagar."
                )
                resposta_final = self.personality.aplicar(msg)
                self._finalizar(sessao, message, resposta_final)
                return resposta_final

        # ------------------------------------------------------
        # EXTRAÇÃO AUTOMÁTICA DE FATOS DO USUÁRIO
        # ------------------------------------------------------
        extrair_e_salvar(message)

        entity = sessao.context.get_entity() or sessao.context.get_topic()

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

            nome = self.identificar_pessoa(message, sessao)
            pergunta = extrair_pergunta(message)

            if pergunta:
                # Manda a frase inteira: a IA cumprimenta sozinha, usando o
                # nome certo — evita "Bom dia, Guilherme. Oi Caio, ..." duplicado.
                contexto = (
                    f"(Contexto: é de manhã, hoje é {agora.strftime('%d/%m/%Y')}.)"
                )
                resposta_ia = perguntar_llm(f"{message} {contexto}", "")
                resposta = (
                    resposta_ia
                    or f"Bom dia, {nome}. Hoje é {agora.strftime('%d/%m/%Y')}."
                )
            else:
                resposta = f"Bom dia, {nome}. Hoje é {agora.strftime('%d/%m/%Y')}."

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if original_message.startswith("boa tarde"):
            nome = self.identificar_pessoa(message, sessao)
            pergunta = extrair_pergunta(message)

            if pergunta:
                resposta_ia = perguntar_llm(message, "")
                resposta = resposta_ia or f"Boa tarde, {nome}."
            else:
                resposta = f"Boa tarde, {nome}."

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if original_message.startswith("boa noite"):
            nome = self.identificar_pessoa(message, sessao)
            pergunta = extrair_pergunta(message)

            if pergunta:
                resposta_ia = perguntar_llm(message, "")
                resposta = resposta_ia or f"Boa noite, {nome}."
            else:
                resposta = f"Boa noite, {nome}."

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # DECISÃO CENTRAL
        # --------------------------------------------------

        decisao = decidir(original_message, sessao.context)
        categoria = decisao.get("destino")
        modulo = categoria

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
                    self._finalizar(sessao, message, resposta_final)
                    return resposta_final

            except Exception as e:
                print(f"[ERRO módulo {modulo_instancia.name}]: {e}")

        # --------------------------------------------------
        # MÓDULOS INTERNOS
        # --------------------------------------------------

        if modulo == "saudacao":
            nome = self.identificar_pessoa(message, sessao)
            pergunta = extrair_pergunta(message)

            if pergunta:
                # Tem mais coisa na frase alem do "oi" (ex.: "oi, meu nome e caio").
                # Manda a frase inteira pra IA: ela cumprimenta e responde ao
                # mesmo tempo, usando o nome certo, sem resposta duplicada.
                resposta_ia = perguntar_llm(message, "")
                resposta = resposta_ia or random.choice(
                    [f"Oi, {nome}.", f"Olá, {nome}.", f"E aí, {nome}."]
                )
            else:
                resposta = random.choice(
                    [f"Oi, {nome}.", f"Olá, {nome}.", f"E aí, {nome}."]
                )

            resposta_final = self.personality.aplicar(resposta)
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if modulo == "hora":
            module = self.modules.get("hora")
            if module and hasattr(module, "run"):
                response = module.run(original_message)
                if response:
                    resposta_final = self.personality.aplicar(response)
                    self._finalizar(sessao, message, resposta_final)
                    return resposta_final

        if modulo == "identidade":
            if "se apresente" in original_message or "apresente" in original_message:
                resposta_final = self.personality.aplicar(apresentar())
            else:
                resposta_final = self.personality.aplicar(
                    f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
                )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if modulo == "calculo":
            expression = (
                processed_message.replace("calcule", "").replace("quanto e", "").strip()
            )
            try:
                result = calcular_seguro(expression)
                resposta_final = self.personality.aplicar(f"O resultado é {result}")
                self._finalizar(sessao, message, resposta_final)
                return resposta_final
            except (ValueError, ZeroDivisionError):
                pass

            resposta_final = self.personality.aplicar(
                "Não consegui calcular essa conta."
            )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if modulo == "memoria":
            conteudo = (
                processed_message.replace("lembre que", "")
                .replace("lembrar que", "")
                .strip()
            )
            salvar_permanente(conteudo)
            sessao.context.update_topic(conteudo.split()[0] if conteudo else "nota")

            resposta_final = self.personality.aplicar("Informação salva.")
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # RESPOSTAS FIXAS
        # --------------------------------------------------

        if "quem sou eu" in original_message:
            resposta_final = self.personality.aplicar(
                f"Você é {obter_usuario()}, meu usuário."
            )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if "quem e voce" in original_message or "quem e vc" in original_message:
            resposta_final = self.personality.aplicar(
                f"Eu sou {obter_nome()}, uma assistente criada por {obter_criador()}."
            )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if "quem te criou" in original_message:
            resposta_final = self.personality.aplicar(
                f"Eu fui criada por {obter_criador()}."
            )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        if (
            "qual e o seu proposito" in original_message
            or "qual seu proposito" in original_message
        ):
            resposta_final = self.personality.aplicar(
                "Meu propósito é te ajudar, aprender com você e facilitar suas tarefas no dia a dia."
            )
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # CONHECIMENTO LOCAL
        # --------------------------------------------------

        response = buscar_conhecimento(processed_message)
        if response:
            resposta_final = self.personality.aplicar(response)
            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        # --------------------------------------------------
        # FALLBACK FINAL — IA com contexto seletivo
        # --------------------------------------------------
        contexto_stm = sessao.stm.get_context_seletivo(max_chars=6000)
        contexto_memoria_db = gerar_contexto_para_prompt(original_message)
        contexto_extra = sessao.context.get_entity() or ""

        contexto_historico = ""
        for m in contexto_stm:
            if m["role"] == "system":
                contexto_historico += m["content"] + "\n\n"
            elif m["role"] == "user":
                contexto_historico += f"Usuário: {m['content']}\n"
            elif m["role"] == "assistant":
                contexto_historico += f"PYXIE: {m['content']}\n"

        # ------------------------------------------------------
        # CONVERTE A MEMÓRIA FIXA EM TEXTO PARA A IA
        # ------------------------------------------------------
        # Se o JSON estiver vazio ou indisponível, não adiciona
        # conteúdo à resposta nem interrompe o processamento.
        contexto_memoria_fixa = memoria_fixa_relevante(
            self.memoria_fixa, original_message
        )

        contexto_final = (
            (
                "INFORMAÇÕES FIXAS DA PYXIE (memory.json):\n"
                + contexto_memoria_fixa
                + "\n\n"
                if contexto_memoria_fixa
                else ""
            )
            + contexto_memoria_db[:400]
            + "\n\n"
            + contexto_historico
            + "\n\n"
            + contexto_extra[:100]
        ).strip()

        try:
            response = perguntar_llm(original_message, contexto_final)
        except Exception:
            response = None

        
        if response:
            resposta_final = self.personality.aplicar(response)

            extrair_e_salvar(
                message,
                topico=sessao.context.get_topic()
            )

            # Guarda o prompt e o contexto exatos usados pela IA.
            sessao.regeneracao_pergunta = original_message
            sessao.regeneracao_contexto = contexto_final

            self._finalizar(sessao, message, resposta_final)
            return resposta_final

        resposta_final = self.personality.aplicar(
            "Ainda não encontrei uma resposta para isso."
        )
        self._finalizar(sessao, message, resposta_final)
        return resposta_final

    # ----------------------------------------------------------
    # FINALIZAÇÃO — STM
    # ----------------------------------------------------------

    
    def _finalizar(self, sessao: ChatSession, user_input: str, resposta: str):
        sessao.stm.add_message("assistant", resposta)
        sessao.ultima_pergunta = user_input

    
    
    
    
    def regenerar(self, chat_id: str = "default"):
        """Regenera a última resposta do fallback da IA."""
        sessao = self.sessions.get(chat_id)

        pergunta = sessao.regeneracao_pergunta
        contexto = sessao.regeneracao_contexto

        if pergunta is None or contexto is None:
            return {
                "ok": False,
                "erro": "Esta conversa não possui uma resposta regenerável."
            }

        mensagens = sessao.stm._messages

        # Confirma que a pergunta e a resposta esperadas
        # continuam no final do histórico.
        if (
            len(mensagens) < 2
            or mensagens[-1].role != "assistant"
            or mensagens[-2].role != "user"
        ):
            return {
                "ok": False,
                "erro": "O histórico mudou. Envie uma nova mensagem."
            }

        try:
            response = perguntar_llm(pergunta, contexto)
        except Exception as erro:
            print(f"[ERRO ao regenerar resposta]: {erro}")
            response = None

        if not response:
            return {
                "ok": False,
                "erro": "Não consegui gerar outra resposta agora."
            }

        resposta_final = self.personality.aplicar(response)

        # Substitui somente a resposta; a pergunta permanece intacta.
        mensagens[-1].content = resposta_final
        sessao.stm._salvar()

        # Impede a repetição acidental da mesma regeneração.
        sessao.ultima_pergunta = None
        sessao.regeneracao_pergunta = None
        sessao.regeneracao_contexto = None
        sessao.context_anterior = None

        return {
            "ok": True,
            "resposta": resposta_final
        }





# =============================================================
# INSTÂNCIA GLOBAL
# =============================================================

from core.memory_control import MemoryControl

brain = Brain()
brain.register_module("memory_control", MemoryControl())