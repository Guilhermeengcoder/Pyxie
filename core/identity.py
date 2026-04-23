import json
import os

ARQUIVO_IDENTIDADE = "data/identity.json"


def carregar_identidade():
    if not os.path.exists(ARQUIVO_IDENTIDADE):
        identidade_padrao = {
            "nome_assistente": "PYXIE",
            "versao": "3.0",
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

# -------------------------------------------------------
# FUNÇÕES DE IDENTIDADE (ADITIVAS)
# -------------------------------------------------------

def apresentar():
    identidade = carregar_identidade()
    return (
        f"Eu sou {identidade.get('nome_assistente', 'PYXIE')}, versão {identidade.get('versao', '1.0')}. "
        f"Fui criada por {identidade.get('criador', 'desconhecido')}. "
        f"Minha personalidade é {identidade.get('personalidade', 'indefinida')} e meu objetivo é: "
        f"{identidade.get('proposito', 'não definido')}."
    )
    


def atualizar_personalidade(nova_personalidade):
    identidade = carregar_identidade()
    identidade["personalidade"] = nova_personalidade

    with open(ARQUIVO_IDENTIDADE, "w") as f:
        json.dump(identidade, f, indent=4)


def atualizar_usuario(novo_usuario):
    identidade = carregar_identidade()
    identidade["usuario_principal"] = novo_usuario

    with open(ARQUIVO_IDENTIDADE, "w") as f:
        json.dump(identidade, f, indent=4)


def atualizar_proposito(novo_proposito):
    identidade = carregar_identidade()
    identidade["proposito"] = novo_proposito

    with open(ARQUIVO_IDENTIDADE, "w") as f:
        json.dump(identidade, f, indent=4)