import json
import os

ARQUIVO_KNOWLEDGE = "data/knowledge.json"


def carregar_conhecimento():

    if not os.path.exists(ARQUIVO_KNOWLEDGE):
        with open(ARQUIVO_KNOWLEDGE, "w") as f:
            json.dump({}, f)

    with open(ARQUIVO_KNOWLEDGE, "r") as f:
        return json.load(f)


def salvar_conhecimento(data):
    with open(ARQUIVO_KNOWLEDGE, "w") as f:
        json.dump(data, f, indent=4)


def aprender(pergunta, resposta):

    data = carregar_conhecimento()

    chave = pergunta.lower()

    # Só aprende se resposta for relevante
    if len(resposta) > 20:
        data[chave] = resposta

    salvar_conhecimento(data)


def buscar_conhecimento(pergunta):

    data = carregar_conhecimento()

    pergunta = pergunta.lower()

    return data.get(pergunta)