class Context:

    def __init__(self):
        self.current_topic = None
        self.history = []

    def update_topic(self, topic):

        self.current_topic = topic
        self.history.append(topic)

        if len(self.history) > 5:
            self.history.pop(0)

    def add_message(self, message):

        self.history.append(message)

        if len(self.history) > 10:
            self.history.pop(0)

    def get_topic(self):
        return self.current_topic