from core.memory.LTM import (
    buscar_relevantes,
    apagar_memoria,
)


class MemoryControl:

    def handle(self, message: str):

        msg = message.lower()

        # =========================
        # LISTAR MEMÓRIA
        # =========================
        if "o que voce lembra" in msg or "o que você lembra" in msg:

            memoria = buscar_relevantes(message)

            fatos    = memoria.get("fatos", {})
            perma    = memoria.get("permanente", [])
            episodios = memoria.get("episodios", [])

            if not fatos and not perma and not episodios:
                return "Ainda não tenho muitas informações sobre você."

            partes = []

            if fatos:
                partes.append("Eu sei algumas coisas sobre você:")
                for k, v in fatos.items():
                    partes.append(f"- Seu {k} é {v}")

            if perma:
                partes.append("\nCoisas que você me pediu para lembrar:")
                for p in perma:
                    partes.append(f"- {p}")

            if episodios:
                partes.append("\nCoisas que você comentou recentemente:")
                for e in episodios:
                    partes.append(f"- {e[:100]}")

            return "\n".join(partes)

        # =========================
        # APAGAR MEMÓRIA
        # =========================
        if msg.startswith("esqueca") or msg.startswith("esqueça"):

            termo = msg.replace("esqueca", "").replace("esqueça", "").strip()

            if not termo:
                return "O que você quer que eu esqueça?"

            apagou = apagar_memoria(termo)
            if apagou:
                return "Pronto, não lembro mais disso."
            return "Não encontrei nada relacionado a isso na minha memória."

        return None