import json
import os
from core.language_pipeline import pipeline

ARQUIVO_KNOWLEDGE = "data/knowledge.json"
MAX_ENTRADAS = 500


def _normalizar_chave(pergunta: str) -> str:
    resultado = pipeline.processar(pergunta)
    return resultado["corrigido"].lower()


def carregar_conhecimento():
    if not os.path.exists(ARQUIVO_KNOWLEDGE):
        with open(ARQUIVO_KNOWLEDGE, "w") as f:
            json.dump({}, f)

    with open(ARQUIVO_KNOWLEDGE, "r") as f:
        return json.load(f)


def salvar_conhecimento(data):
    with open(ARQUIVO_KNOWLEDGE, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def aprender(pergunta, resposta):
    if len(resposta) <= 20:
        return

    data = carregar_conhecimento()

    if len(data) >= MAX_ENTRADAS:
        chave_mais_antiga = next(iter(data))
        del data[chave_mais_antiga]

    chave = _normalizar_chave(pergunta)
    data[chave] = resposta

    salvar_conhecimento(data)


def buscar_conhecimento(pergunta):
    data = carregar_conhecimento()
    chave = _normalizar_chave(pergunta)
    return data.get(chave)