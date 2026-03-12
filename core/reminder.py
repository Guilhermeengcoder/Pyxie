import json
import os
from datetime import datetime

ARQUIVO = "data/reminders.json"

def carregar():
    if not os.path.exists(ARQUIVO):
        with open(ARQUIVO, "w") as f:
            json.dump([], f)
        return []
    with open(ARQUIVO, "r") as f:
        return json.load(f)

def salvar(lista):
    with open(ARQUIVO, "w") as f:
        json.dump(lista, f, indent=4)

def adicionar(texto, horario):
    lembretes = carregar()
    lembretes.append({
        "texto": texto,
        "horario": horario,
        "notificado": False
    })
    salvar(lembretes)

def listar():
    return carregar()

def verificar():
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    lembretes = carregar()
    atualizados = []

    for l in lembretes:
        if not l["notificado"] and l["horario"] <= agora:
            print(f"⏰ Lembrete: {l['texto']}")
            l["notificado"] = True
        atualizados.append(l)

    salvar(atualizados)