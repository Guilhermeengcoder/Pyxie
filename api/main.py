# api/main.py — APENAS API
from fastapi import FastAPI
from pydantic import BaseModel
from core.brain import brain

app = FastAPI(title="PYXIE API")

class Pergunta(BaseModel):
    mensagem: str

@app.get("/")
def home():
    return {"status": "PYXIE online 🚀"}

@app.post("/perguntar")
def perguntar(pergunta: Pergunta):
    resposta = brain.process(pergunta.mensagem)
    return {"resposta": resposta}