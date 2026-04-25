# main.py — APENAS terminal
from core.brain import brain
from core.memory import Memory
from core.context import Context

memory = Memory()
context = Context()

STOPWORDS = ["a", "o", "de", "do", "da", "e", "é", "que", "no", "na"]

if __name__ == "__main__":
    print("PYXIE iniciada.\n")

    while True:
        msg = input("Você: ").lower()
        context.add_message(msg)

        if "o que voce lembra" in msg or "oque voce lembra" in msg:
            if memory.data:
                print("PYXIE: Eu lembro de:")
                for cat in memory.data:
                    print("-", memory.data[cat]["current"])
            else:
                print("PYXIE: Ainda não lembro de nada.")
            continue

        if msg.startswith("pesquise"):
            resposta = brain.process(msg)
            print("PYXIE:", resposta if resposta else "Não encontrei nada relevante.")
            continue

        if "lembre que" in msg or "lembrar que" in msg:
            content = msg.replace("lembre que", "").replace("lembrar que", "").strip()
            words = content.split()
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