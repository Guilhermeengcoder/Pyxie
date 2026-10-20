import os

from dotenv import load_dotenv
from google import genai

from core.prompt import montar_prompt
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel

from core import usage_gemini

# ================================================================
# CONFIGURAÇÃO
# ================================================================

load_dotenv()

# gemini-3.6-flash foi o que respondeu nos testes.
# Se o .env tiver GEMINI_MODEL, ele manda no valor padrão.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# A busca do Gemini (google_search) deu 429 no plano gratuito.
# Fica DESLIGADA; só ligue com GEMINI_BUSCA=1 se passar para um plano que a inclua.
GEMINI_BUSCA = os.getenv("GEMINI_BUSCA", "0").strip() == "1"

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY não encontrada no arquivo .env"
    )

client = genai.Client(api_key=api_key)


# ================================================================
# TRADUÇÃO DE ERROS
# interactions e generate_content levantam classes diferentes,
# mas as duas trazem o código HTTP em status_code ou code.
# ================================================================

def _traduzir_erro(e: Exception) -> ErroLLM:
    codigo = getattr(e, "status_code", None) or getattr(e, "code", None)

    try:
        codigo = int(codigo)
    except (TypeError, ValueError):
        codigo = None

    detalhe = str(e)[:200]

    if codigo == 429:
        return ErroCota("gemini", detalhe)

    if codigo is not None and 500 <= codigo <= 599:
        return ErroIndisponivel("gemini", detalhe)

    nome = type(e).__name__.lower()
    if "timeout" in nome or "connection" in nome:
        return ErroIndisponivel("gemini", detalhe)

    return ErroLLM("gemini", detalhe)


# ================================================================
# GEMINI
# ================================================================

def perguntar_gemini(comando: str, memoria: str = "") -> str:
    """
    Envia uma pergunta ao Gemini e retorna o texto da resposta.
    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """

    prompt = montar_prompt(comando, memoria)

    argumentos = {"model": GEMINI_MODEL, "input": prompt}

    if GEMINI_BUSCA:
        argumentos["tools"] = [{"type": "google_search"}]

    try:
        interaction = client.interactions.create(**argumentos)
    except Exception as e:
        print(f"[Gemini] {e}")
        raise _traduzir_erro(e) from e
    
    try:
        usage_gemini.registrar(
            usage_gemini.tokens_da_interacao(interaction, prompt)
        )
    except Exception as e:
        print(f"[usage_gemini] {e}")  # nunca quebra a resposta

    texto = (interaction.output_text or "").strip()

    if not texto:
        raise ErroLLM("gemini", "resposta vazia")

    return texto


# ================================================================
# TESTE DIRETO:  python -m modules.gemini_ai
# ================================================================

if __name__ == "__main__":
    print(f"Modelo: {GEMINI_MODEL} | busca: {GEMINI_BUSCA}")

    try:
        print("\nPYXIE:")
        print(perguntar_gemini("Responda apenas confirmando que você está funcionando."))
    except ErroLLM as erro:
        print(f"{type(erro).__name__}: {erro}")