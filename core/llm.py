from modules.groq_ai import perguntar_groq
from modules.ollama_ai import perguntar_ollama

LLM_PROVIDER = "groq"

def perguntar_llm(pergunta, contexto):

    if LLM_PROVIDER == "groq":
        return perguntar_groq(pergunta, contexto)

    return perguntar_ollama(pergunta, contexto)