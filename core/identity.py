import json
import os

ARQUIVO_IDENTIDADE = "data/identity.json"


def carregar_identidade():
    if not os.path.exists(ARQUIVO_IDENTIDADE):
        identidade_padrao = {
            "nome_assistente": "PYXIE",
            "versao": "1.0",
            "criador": "Guilherme",
            "usuario_principal": "Guilherme",
            "proposito": "Ser uma assistente pessoal inteligente",
            "personalidade": "amigavel",
            "lingua": "pt-br"
        }

        with open(ARQUIVO_IDENTIDADE, "w") as f:
            json.dump(identidade_padrao, f, indent=4)

        return identidade_padrao

    with open(ARQUIVO_IDENTIDADE, "r") as f:
        return json.load(f)


def obter_nome():
    identidade = carregar_identidade()
    return identidade["nome_assistente"]


def obter_criador():
    identidade = carregar_identidade()
    return identidade["criador"]


def obter_usuario():
    identidade = carregar_identidade()
    return identidade["usuario_principal"]