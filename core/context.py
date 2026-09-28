import re


class TipoIntencao:
    DECLARACAO  = "declaracao"
    PERGUNTA    = "pergunta"
    COMANDO     = "comando"
    CONFIRMACAO = "confirmacao"
    EMOCIONAL   = "emocional"
    DESCONHECIDO = "desconhecido"


class ClassificadorIntencao:

    _PADROES_COMANDO = [
        r"^(pesquise|procure|busque|calcule|abre|abra|abrir|mostra|mostre|"
        r"lista|liste|define|defina|explique|me fale|me diga|me mostre)",
    ]
    _PADROES_DECLARACAO = [
        r"^(meu|minha|eu|sou|estou|tenho|quero|gosto|odeio|adoro|prefiro|"
        r"trabalho|moro|nasci|acredito|acho que|penso que|sonho)",
        r"(é que|foi que|são que)",
    ]
    _PADROES_CONFIRMACAO = [
        r"^(sim|não|nao|ok|okay|certo|entendi|combinado|claro|"
        r"com certeza|exato|correto|errado|talvez|pode ser)$",
    ]
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
        for padrao in self._PADROES_COMANDO:
            if re.search(padrao, msg):
                return TipoIntencao.COMANDO
        for padrao in self._PADROES_CONFIRMACAO:
            if re.search(padrao, msg):
                return TipoIntencao.CONFIRMACAO
        for padrao in self._PADROES_EMOCIONAL:
            if re.search(padrao, msg):
                return TipoIntencao.EMOCIONAL
        for padrao in self._PADROES_DECLARACAO:
            if re.search(padrao, msg):
                return TipoIntencao.DECLARACAO
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


_classificador = ClassificadorIntencao()


class Context:

    def __init__(self):
        self.current_topic = None
        self.history       = []
        self.entity       = None
        self.last_intent  = None
        self._intencao_atual: str = TipoIntencao.DESCONHECIDO
        self._msg_atual:      str = ""

        # NOVO: nome da pessoa que se apresentou nesta conversa
        # (fica None ate alguem se apresentar; usado para nao "esquecer"
        # o nome de quem esta falando entre uma mensagem e outra)
        self._pessoa = None

    def registrar_mensagem(self, msg: str):
        self._msg_atual      = msg
        self._intencao_atual = _classificador.classificar(msg)

    def get_intencao(self) -> str:
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

    def set_entity(self, entity):
        self.entity = entity

    def get_entity(self):
        return self.entity

    def set_intent(self, intent):
        self.last_intent = intent

    def get_intent(self):
        return self.last_intent

    # ----------------------------------------------------------
    # NOVO: quem esta falando nesta conversa
    # ----------------------------------------------------------

    def set_pessoa(self, nome):
        self._pessoa = nome

    def get_pessoa(self):
        return self._pessoa

    def clear(self):
        self.current_topic   = None
        self.entity          = None
        self.last_intent     = None
        self._intencao_atual = TipoIntencao.DESCONHECIDO
        self._msg_atual      = ""
        self._pessoa         = None

    def get(self, key, default=None):
        return getattr(self, key, default)