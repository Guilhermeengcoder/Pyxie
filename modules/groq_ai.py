from groq import (
    Groq,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)
from dotenv import load_dotenv
import os

from core.usage import registrar_headers
from core.prompt import montar_prompt as _montar_prompt
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-120b"

api_key = os.getenv("GROQ_API_KEY")

client = Groq(api_key=api_key)


# ================================================================
# TRADUÇÃO DE ERROS
# Usada também pelo groq_vision.py.
# ================================================================

def _espera_do_erro(e: Exception):
    """Segundos até poder tentar de novo (header retry-after), ou None."""
    try:
        valor = e.response.headers.get("retry-after")
        return float(valor) if valor else None
    except (AttributeError, TypeError, ValueError):
        return None


def traduzir_erro_groq(e: Exception) -> ErroLLM:
    detalhe = f"{type(e).__name__}: {str(e)[:200]}"

    if isinstance(e, RateLimitError):
        return ErroCota("groq", detalhe, espera_s=_espera_do_erro(e))

    if isinstance(
        e, (APITimeoutError, APIConnectionError, InternalServerError)
    ):
        return ErroIndisponivel("groq", detalhe)

    return ErroLLM("groq", detalhe)


def _montar_mensagens(comando: str, memoria: str) -> list:
    prompt = _montar_prompt(comando, memoria)
    regras, _, resto = prompt.partition("### Histórico")
    return [
        {"role": "system", "content": regras.strip()},
        {"role": "user", "content": ("### Histórico" + resto).strip()},
    ]


def perguntar_groq(comando: str, memoria: str = "") -> str:
    """
    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """
    try:
        raw = client.chat.completions.with_raw_response.create(
            model=GROQ_MODEL,
            messages=_montar_mensagens(comando, memoria),
            tools=[{"type": "browser_search"}],
            tool_choice="auto"
        )

        try:
            registrar_headers(raw.headers, GROQ_MODEL)
        except Exception:
            pass  # nunca deixa isso quebrar a resposta principal

        response = raw.parse()
        return response.choices[0].message.content or ""

    except Exception as e:
        erro = traduzir_erro_groq(e)
        print(f"[Groq] {erro}")
        raise erro from e