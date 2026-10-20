import uuid
from core.brain import brain
from core import llm

if __name__ == "__main__":
    chat_id = str(uuid.uuid4())
    print("PYXIE iniciada.\n")

    while True:
        msg = input("Você: ")
        if not msg.strip():
            continue
        llm.iniciar_rastreio()
        resposta = brain.process(msg, chat_id=chat_id)
        print("PYXIE:", resposta)
        aviso = llm.aviso_da_requisicao()
        if aviso:
            print("⚠", aviso)