from modules.groq_ai import perguntar_groq
from modules.groq_vision import perguntar_groq_imagem
from modules.ollama_ai import perguntar_ollama

LLM_PROVIDER = "groq"

def perguntar_llm(pergunta, contexto):

    if LLM_PROVIDER == "groq":
        return perguntar_groq(pergunta, contexto)

    return perguntar_ollama(pergunta, contexto)


def perguntar_llm_imagem(pergunta, imagem, contexto):

    # Imagens só funcionam pelo Groq (o Ollama local não está configurado com visão)
    return perguntar_groq_imagem(pergunta, imagem, contexto)