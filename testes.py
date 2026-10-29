import asyncio
import json
import os

from dotenv import load_dotenv
load_dotenv()

import websockets

URL = "ws://localhost:10000/ws/voz"
PERGUNTAS = ["Conta uma piada curta.", "Qual é a capital da Austrália?", "Quem ganhou a Bola de Ouro este ano?"]

async def main():
    async with websockets.connect(URL, max_size=None) as ws:
        await ws.send(json.dumps(
            {"token": os.getenv("PYXIE_TOKEN"), "chat_id": "teste-ws"}
        ))
        print("servidor:", await ws.recv())

        for pergunta in PERGUNTAS:
            print(f"\nVocê: {pergunta}")
            await ws.send(json.dumps({"texto": pergunta}))
            bytes_audio, legenda = 0, ""

            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    bytes_audio += len(msg)
                    continue
                d = json.loads(msg)
                if d["tipo"] == "legenda" and d["quem"] == "pyxie":
                    legenda = d["texto"]
                elif d["tipo"] == "fim_turno":
                    break
                elif d["tipo"] in ("encerrada", "erro"):
                    print(d)
                    return

            print(f"PYXIE: {legenda}  [{bytes_audio} bytes de áudio]")


asyncio.run(main()) 