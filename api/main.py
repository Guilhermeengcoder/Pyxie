from fastapi import FastAPI
from pydantic import BaseModel
from core.engine import processar_mensagem

app = FastAPI(title="PYXIE API")

class Pergunta(BaseModel):
    mensagem: str


@app.get("/")
def home():
    return {"status": "PYXIE online 🚀"}


@app.post("/perguntar")
def perguntar(pergunta: Pergunta):
    resposta = processar_mensagem(pergunta.mensagem)
    return {"resposta": resposta}