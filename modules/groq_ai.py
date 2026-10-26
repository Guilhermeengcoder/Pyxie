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
from core import usage_groq
from core.prompt import montar_prompt as _montar_prompt
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel, ErroEntradaGrande
load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Busca embutida do Groq: desligada por padrão (gasta muitos tokens).
# Ligue com GROQ_BUSCA=1 no .env.
BUSCA_GROQ = os.getenv("GROQ_BUSCA", "0").strip() == "1"

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
    detalhe = f"{type(e).__name__}: {str(e)[:900]}"

    if isinstance(e, RateLimitError):
        return ErroCota("groq", detalhe, espera_s=_espera_do_erro(e))

    # 413: o pedido passa do limite de tokens do modelo/plano.
    if getattr(e, "status_code", None) == 413:
        return ErroEntradaGrande("groq", detalhe)

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


def _chamar(comando: str, memoria: str, com_busca: bool, limite_saida=None) -> str:
    argumentos = {
        "model": GROQ_MODEL,
        "messages": _montar_mensagens(comando, memoria),
        "reasoning_effort": "low",
    }

    if com_busca:
        argumentos["tools"] = [{"type": "browser_search"}]
        argumentos["tool_choice"] = "auto"

    if limite_saida:
        argumentos["max_completion_tokens"] = limite_saida

    raw = client.chat.completions.with_raw_response.create(**argumentos)

    try:
        registrar_headers(raw.headers, GROQ_MODEL)
    except Exception:
        pass  # nunca deixa isso quebrar a resposta principal

    response = raw.parse()

    uso = getattr(response, "usage", None)
    if uso:
        print(
            f"[Groq] tokens: entrada={uso.prompt_tokens} "
            f"saída={uso.completion_tokens} total={uso.total_tokens}"
        )
        try:
            usage_groq.registrar(GROQ_MODEL, uso.total_tokens)
        except Exception as e:
            print(f"[usage_groq] {e}")

    escolha = response.choices[0]
    texto = (escolha.message.content or "").strip()

    if not texto:
        print(
            f"[Groq] resposta vazia: finish_reason={escolha.finish_reason}, "
            f"tool_calls={bool(getattr(escolha.message, 'tool_calls', None))}"
        )

    return texto


def perguntar_groq(comando: str, memoria: str = "", busca: bool = BUSCA_GROQ) -> str:
    """
    busca=False desliga a ferramenta browser_search.
    Se a resposta vier vazia, tenta uma vez de novo sem ferramentas e
    com mais espaço de saída.
    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """
    try:
        texto = _chamar(comando, memoria, busca)

        if not texto:
            texto = _chamar(comando, memoria, False, limite_saida=2000)

        return texto

    except Exception as e:
        erro = traduzir_erro_groq(e)
        print(f"[Groq] {erro}")
        raise erro from e