from core.brain import brain
from core.memory import Memory
from core.context import Context
from fastapi import FastAPI
from core.module_loader import carregar_modulos

modulos = carregar_modulos()

print("Módulos carregados:")

for m in modulos:
    print("-", m.__name__)

    if hasattr(m, "Module"):
        instancia = m.Module()
        brain.register_module(instancia.name, instancia)


memory = Memory()
context = Context()

app = FastAPI()


@app.post("/perguntar")
def perguntar(pergunta: str):
    resposta = brain.process(pergunta)
    return {"resposta": resposta}


if __name__ == "__main__":

    print("PYXIE iniciada.\n")

    STOPWORDS = ["a", "o", "de", "do", "da", "e", "é", "que", "no", "na"]

    while True:
        msg = input("Você: ").lower()
        context.add_message(msg)

        # NOVO: listar memória quando perguntar
        if "o que voce lembra" in msg or "oque voce lembra" in msg:
            if memory.data:
                print("PYXIE: Eu lembro de:")
                for cat in memory.data:
                    print("-", memory.data[cat]["current"])
            else:
                print("PYXIE: Ainda não lembro de nada.")
            continue

        # NOVO: comando de pesquisa web (não interfere na memória)
        if msg.startswith("pesquise"):
            resposta = brain.process(msg)

            if resposta:
                print("PYXIE:", resposta)
            else:
                print("PYXIE: Não encontrei nada relevante.")

            continue

        if "lembre que" in msg or "lembrar que" in msg:
            content = msg.replace("lembre que", "").replace("lembrar que", "").strip()
            words = content.split()

            # proteção contra erro
            category = words[0] if words else "nota"

            memory.remember(category, content)
            context.update_topic(category)

            print("PYXIE: Informação salva.")
            continue

        words = [w for w in msg.split() if w not in STOPWORDS and len(w) > 2]

        found = False
        for word in words:
            results = memory.search(word)
            if results:
                context.update_topic(word)
                print("PYXIE: Encontrei isso na memória:")
                for r in results:
                    print("-", r)
                found = True
                break

        if not found and len(words) <= 2 and context.get_topic():
            results = memory.search(context.get_topic())
            if results:
                print("PYXIE: Considerando que estamos falando sobre", context.get_topic())
                for r in results:
                    print("-", r)
                continue

        if not found:
            print("PYXIE:", brain.process(msg))