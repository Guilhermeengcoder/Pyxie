from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.brain import brain

app = FastAPI(title="PYXIE API")

# ~4,5 MB de imagem em base64. O front-end já reduz a foto antes de enviar
# (lado máximo de 1280px), então isso só protege contra abuso.
MAX_IMAGEM_CHARS = 6_000_000


class MensagemHistorico(BaseModel):
    role: str       # "user" ou "assistant"
    content: str


class Pergunta(BaseModel):
    mensagem: str = ""
    conversa_id: Optional[str] = None
    historico: List[MensagemHistorico] = []
    imagem: Optional[str] = None    # data URL: "data:image/jpeg;base64,..."


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

    # Garante que a PYXIE está usando o contexto DESTA conversa
    brain.selecionar_conversa(
        pergunta.conversa_id,
        [{"role": m.role, "content": m.content} for m in pergunta.historico],
    )

    if pergunta.imagem:
        resposta = brain.processar_imagem(pergunta.mensagem, pergunta.imagem)
    else:
        resposta = brain.process(pergunta.mensagem)

    return {"resposta": resposta}


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)