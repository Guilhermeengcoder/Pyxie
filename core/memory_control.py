from core.memory_manager import (
    buscar_todos_fatos,
    buscar_episodios_recentes,
    buscar_explicitas
)


class MemoryControl:

    def handle(self, message: str):

        msg = message.lower()

        # =========================
        # LISTAR MEMÓRIA (NATURAL)
        # =========================
        if "o que voce lembra" in msg or "o que você lembra" in msg:

            fatos = buscar_todos_fatos()
            episodios = buscar_episodios_recentes(3)

            if not fatos and not episodios:
                return "Ainda não tenho muitas informações sobre você."

            partes = []

            if fatos:
                partes.append("Eu sei algumas coisas sobre você:")
                for k, v in fatos.items():
                    partes.append(f"- Seu {k} é {v}")

            if episodios:
                partes.append("\nTambém lembro de coisas que você comentou recentemente:")
                for e in episodios:
                    partes.append(f"- {e['resumo']}")

            return "\n".join(partes)

        # =========================
        # APAGAR MEMÓRIA
        # =========================
        if msg.startswith("esqueca") or msg.startswith("esqueça"):

            termo = msg.replace("esqueca", "").replace("esqueça", "").strip()

            # aqui você pode evoluir depois pra DELETE real no banco
            return f"Ainda não sei apagar memórias específicas, mas estou evoluindo nisso 😉"

        return None