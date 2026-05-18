# =============================================================
# core/context.py — Contexto Central da PYXIE
#
# Responsabilidades:
#   - Rastrear tópico e histórico da conversa
#   - Classificar a intenção real de cada mensagem
#   - Disponibilizar essa classificação para todos os módulos
#     antes que eles tomem qualquer decisão
#
# Por que aqui e não no prompt ou nas keywords:
#   - Centraliza a inteligência de interpretação num lugar só
#   - Qualquer módulo consulta antes de agir — sem duplicação
#   - Não depende de palavras pré-definidas por módulo
# =============================================================

import re


# =============================================================
# TIPOS DE INTENÇÃO
# Cobrem os casos mais comuns de linguagem natural.
# Novos tipos podem ser adicionados sem quebrar nada.
# =============================================================

class TipoIntencao:
    DECLARACAO  = "declaracao"   # "meu sonho é...", "eu gosto de..."
    PERGUNTA    = "pergunta"     # "como funciona?", "o que é X?"
    COMANDO     = "comando"      # "abra o chrome", "pesquise...", "calcule..."
    CONFIRMACAO = "confirmacao"  # "sim", "entendi", "ok", "certo"
    EMOCIONAL   = "emocional"    # "estou cansado", "me arrependo", "que legal"
    DESCONHECIDO = "desconhecido"


# =============================================================
# CLASSIFICADOR DE INTENÇÃO
# Analisa a mensagem como um todo — não palavra isolada.
# A ordem das verificações importa: do mais específico ao mais geral.
# =============================================================

class ClassificadorIntencao:

    # Padrões de COMANDO — geralmente começam com verbo no imperativo
    _PADROES_COMANDO = [
        r"^(pesquise|procure|busque|calcule|abre|abra|abrir|mostra|mostre|"
        r"lista|liste|define|defina|explique|me fale|me diga|me mostre)",
    ]

    # Padrões de DECLARAÇÃO — afirmações sobre si mesmo ou o mundo
    _PADROES_DECLARACAO = [
        r"^(meu|minha|eu|sou|estou|tenho|quero|gosto|odeio|adoro|prefiro|"
        r"trabalho|moro|nasci|acredito|acho que|penso que|sonho)",
        r"(é que|foi que|são que)",   # "a verdade é que...", "o problema é que..."
    ]

    # Padrões de CONFIRMAÇÃO — respostas curtas afirmativas/negativas
    _PADROES_CONFIRMACAO = [
        r"^(sim|não|nao|ok|okay|certo|entendi|combinado|claro|"
        r"com certeza|exato|correto|errado|talvez|pode ser)$",
    ]

    # Padrões de ESTADO EMOCIONAL
    _PADROES_EMOCIONAL = [
        r"(estou|tô|to|me sinto|me senti|fiquei|fico)\s+"
        r"(cansado|feliz|triste|animado|frustrado|preocupado|"
        r"nervoso|ansioso|empolgado|entediado|arrepend)",
        r"(que (legal|chato|triste|ótimo|boa|ruim)|"
        r"que pena|que bom|infelizmente|felizmente)",
    ]

    def classificar(self, msg: str) -> str:
        msg = msg.strip().lower()

        if not msg:
            return TipoIntencao.DESCONHECIDO

        # 1. COMANDO — verifica primeiro porque é mais explícito
        for padrao in self._PADROES_COMANDO:
            if re.search(padrao, msg):
                return TipoIntencao.COMANDO

        # 2. CONFIRMAÇÃO — mensagens muito curtas e diretas
        for padrao in self._PADROES_CONFIRMACAO:
            if re.search(padrao, msg):
                return TipoIntencao.CONFIRMACAO

        # 3. EMOCIONAL — antes de declaração para não confundir
        for padrao in self._PADROES_EMOCIONAL:
            if re.search(padrao, msg):
                return TipoIntencao.EMOCIONAL

        # 4. DECLARAÇÃO — afirmações sobre si ou o mundo
        for padrao in self._PADROES_DECLARACAO:
            if re.search(padrao, msg):
                return TipoIntencao.DECLARACAO

        # 5. PERGUNTA — termina com ? ou começa com palavra interrogativa
        if msg.endswith("?"):
            return TipoIntencao.PERGUNTA

        palavras_interrogativas = {
            "quem", "qual", "quais", "quando", "onde",
            "como", "porque", "por que", "quanto", "quantos",
            "o que", "oque"
        }
        primeira_palavra = msg.split()[0] if msg.split() else ""
        duas_primeiras   = " ".join(msg.split()[:2])

        if primeira_palavra in palavras_interrogativas:
            return TipoIntencao.PERGUNTA
        if duas_primeiras in palavras_interrogativas:
            return TipoIntencao.PERGUNTA

        return TipoIntencao.DESCONHECIDO


# =============================================================
# CONTEXT
# =============================================================

_classificador = ClassificadorIntencao()


class Context:

    def __init__(self):
        # --------------------------------------------------
        # Sistema legado (mantido para compatibilidade)
        # --------------------------------------------------
        self.current_topic = None
        self.history       = []

        # --------------------------------------------------
        # Sistema novo
        # --------------------------------------------------
        self.entity       = None
        self.last_intent  = None        # destino decidido pelo decidir()

        # --------------------------------------------------
        # Intenção real da mensagem atual
        # Qualquer módulo pode consultar antes de agir.
        # --------------------------------------------------
        self._intencao_atual: str = TipoIntencao.DESCONHECIDO
        self._msg_atual:      str = ""

    # ----------------------------------------------------------
    # CLASSIFICAÇÃO — chamada uma vez por mensagem no brain.py
    # ----------------------------------------------------------

    def registrar_mensagem(self, msg: str):
        """
        Classifica a intenção da mensagem e armazena no contexto.
        Deve ser chamado no início do process() antes de qualquer módulo.

        Uso no brain.py:
            self.context.registrar_mensagem(processed_message)

        Qualquer módulo então consulta:
            if context.get_intencao() == TipoIntencao.DECLARACAO:
                return None  # ignora, não é um comando
        """
        self._msg_atual      = msg
        self._intencao_atual = _classificador.classificar(msg)

    def get_intencao(self) -> str:
        """Retorna o tipo de intenção da mensagem atual."""
        return self._intencao_atual

    def is_declaracao(self) -> bool:
        return self._intencao_atual == TipoIntencao.DECLARACAO

    def is_pergunta(self) -> bool:
        return self._intencao_atual == TipoIntencao.PERGUNTA

    def is_comando(self) -> bool:
        return self._intencao_atual == TipoIntencao.COMANDO

    def is_emocional(self) -> bool:
        return self._intencao_atual == TipoIntencao.EMOCIONAL

    def is_confirmacao(self) -> bool:
        return self._intencao_atual == TipoIntencao.CONFIRMACAO

    # ----------------------------------------------------------
    # LEGADO (mantido intacto para não quebrar brain.py)
    # ----------------------------------------------------------

    def update_topic(self, topic):
        self.current_topic = topic
        self.history.append(topic)

        if len(self.history) > 5:
            self.history.pop(0)

        self.entity = topic

    def add_message(self, message):
        self.history.append(message)

        if len(self.history) > 10:
            self.history.pop(0)

    def get_topic(self):
        return self.current_topic

    def get_context(self):
        return self.history

    # ----------------------------------------------------------
    # SISTEMA NOVO
    # ----------------------------------------------------------

    def set_entity(self, entity):
        self.entity = entity

    def get_entity(self):
        return self.entity

    def set_intent(self, intent):
        self.last_intent = intent

    def get_intent(self):
        return self.last_intent

    def clear(self):
        self.current_topic   = None
        self.entity          = None
        self.last_intent     = None
        self._intencao_atual = TipoIntencao.DESCONHECIDO
        self._msg_atual      = ""

    def get(self, key, default=None):
        return getattr(self, key, default)