class ConversationMemory:
    def __init__(self, limite=5):
        self.historico = []
        self.limite = limite

    def adicionar(self, usuario, pyxie):
        self.historico.append({
            "usuario": usuario,
            "pyxie": pyxie
        })

        # 🔒 CONTROLE DE TAMANHO (ESSENCIAL)
        if len(self.historico) > self.limite:
            self.historico.pop(0)

    def gerar_contexto(self):
        contexto = ""

        for item in self.historico:
            contexto += f"Usuário: {item['usuario']}\n"
            contexto += f"PYXIE: {item['pyxie']}\n"

        return contexto