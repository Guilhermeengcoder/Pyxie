class Context:

    def __init__(self):
        # legado (NÃO MEXER)
        self.current_topic = None
        self.history = []

        # NOVO SISTEMA
        self.entity = None
        self.last_intent = None

    # =========================
    # LEGADO (mantido)
    # =========================

    def update_topic(self, topic):
        self.current_topic = topic
        self.history.append(topic)

        if len(self.history) > 5:
            self.history.pop(0)

        # 🔥 sincroniza com novo sistema
        self.entity = topic

    def add_message(self, message):
        self.history.append(message)

        if len(self.history) > 10:
            self.history.pop(0)

    def get_topic(self):
        return self.current_topic

    # =========================
    # NOVO SISTEMA
    # =========================

    def set_entity(self, entity):
        self.entity = entity

    def get_entity(self):
        return self.entity

    def set_intent(self, intent):
        self.last_intent = intent

    def get_intent(self):
        return self.last_intent

    def clear(self):
        self.current_topic = None
        self.entity = None
        self.last_intent = None
        
    def get(self, key, default=None):
        return getattr(self, key, default)