class MemoryControl:

    def __init__(self, memory):
        self.memory = memory

    def handle(self, message):


        # listar memórias
        if "liste memorias" in message or "mostrar memorias" in message:

            data = self.memory.data

            if not data:
                return "Não tenho memórias registradas."

            resposta = "Eu lembro de:\n"

            for item in data:
                resposta += f"- {item}\n"

            return resposta

        # apagar memória
        if message.startswith("esqueca") or message.startswith("esqueça"):

            termo = message.replace("esqueca", "").replace("esqueça", "").strip()

            resultados = self.memory.search(termo)

            if not resultados:
                return "Não encontrei essa memória."

            for r in resultados:
                self.memory.data.remove(r)

            self.memory.save()

            return "Memória apagada."

        return None