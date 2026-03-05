from fastapi import FastAPI
from pydantic import BaseModel
from core.brain import Brain   # importa a classe

app = FastAPI(title="PYXIE API")

brain = Brain()  # cria instância do cérebro

class Pergunta(BaseModel):
    mensagem: str

@app.get("/")
def home():
    return {"status": "PYXIE online 🚀"}

@app.post("/perguntar")
def perguntar(pergunta: Pergunta):
    resposta = brain.process(pergunta.mensagem)
    return {"resposta": resposta}