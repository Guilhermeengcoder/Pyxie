from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.brain import brain

app = FastAPI(title="PYXIE API")


class Pergunta(BaseModel):
    mensagem: str


@app.post("/perguntar")
def perguntar(pergunta: Pergunta):
    resposta = brain.process(pergunta.mensagem)
    return {"resposta": resposta}


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)