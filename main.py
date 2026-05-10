from core.brain import brain

if __name__ == "__main__":
    print("PYXIE iniciada.\n")

    while True:
        msg = input("Você: ")
        if not msg.strip():
            continue
        resposta = brain.process(msg)
        print("PYXIE:", resposta)