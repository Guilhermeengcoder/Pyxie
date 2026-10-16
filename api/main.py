from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.brain import brain
from core import usage

app = FastAPI(title="PYXIE API")

# ~4,5 MB de imagem em base64. O front-end já reduz a foto antes de enviar
# (lado máximo de 1280px), então isso só protege contra abuso.
MAX_IMAGEM_CHARS = 6_000_000


class MensagemHistorico(BaseModel):
    role: str       # "user" ou "assistant"
    content: str


class Pergunta(BaseModel):
    mensagem: str = ""
    chat_id: str = "default"
    # O front-end ainda envia isso; por enquanto o brain não usa.
    historico: Optional[List[MensagemHistorico]] = None
    imagem: Optional[str] = None


@app.post("/perguntar")
def perguntar(pergunta: Pergunta):

    if pergunta.imagem:
        if (
            not pergunta.imagem.startswith("data:image/")
            or len(pergunta.imagem) > MAX_IMAGEM_CHARS
        ):
            raise HTTPException(status_code=400, detail="Imagem inválida ou grande demais.")

    if not pergunta.mensagem.strip() and not pergunta.imagem:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    if pergunta.imagem:
        resposta = brain.processar_imagem(
            pergunta.mensagem,
            pergunta.imagem,
            chat_id=pergunta.chat_id,
        )
    else:
        resposta = brain.process(pergunta.mensagem, chat_id=pergunta.chat_id)

    return {"resposta": resposta, "uso": usage.ultimo()}



@app.post("/regenerar/{chat_id}")
def regenerar_resposta(chat_id: str):
    resultado = brain.regenerar(chat_id=chat_id)

    if not resultado["ok"]:
        raise HTTPException(
            status_code=400,
            detail=resultado["erro"]
        )

    return {
        "resposta": resultado["resposta"],
        "uso": usage.ultimo()
    }



@app.delete("/chat/{chat_id}")
def encerrar_chat(chat_id: str):
    brain.sessions.delete(chat_id)
    return {"ok": True}


@app.get("/uso")
def uso():
    return usage.ultimo()


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)