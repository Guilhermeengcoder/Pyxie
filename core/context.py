class Context:

    def __init__(self):
        self.current_topic = None
        self.last_messages = []

    def update_topic(self, topic):
        self.current_topic = topic

    def add_message(self, message):
        self.last_messages.append(message)
        if len(self.last_messages) > 5:
            self.last_messages.pop(0)

    def get_topic(self):
        return self.current_topic