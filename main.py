import uuid
from core.brain import brain

if __name__ == "__main__":
    chat_id = str(uuid.uuid4())
    print("PYXIE iniciada.\n")

    while True:
        msg = input("Você: ")
        if not msg.strip():
            continue
        resposta = brain.process(msg, chat_id=chat_id)
        print("PYXIE:", resposta)