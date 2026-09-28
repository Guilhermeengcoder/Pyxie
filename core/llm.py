from modules.groq_ai import perguntar_groq
from modules.groq_vision import perguntar_groq_imagem
from modules.ollama_ai import perguntar_ollama
from modules.gemini_ai import perguntar_gemini


LLM_PROVIDER = "groq"


def perguntar_llm(pergunta, contexto):

    if LLM_PROVIDER == "groq":
        return perguntar_groq(pergunta, contexto)

    if LLM_PROVIDER == "gemini":
        return perguntar_gemini(pergunta, contexto)

    return perguntar_ollama(pergunta, contexto)


def perguntar_llm_imagem(pergunta, imagem, contexto):

    # Imagens só funcionam pelo Groq
    # O Ollama local ainda não está configurado com visão.
    return perguntar_groq_imagem(pergunta, imagem, contexto)