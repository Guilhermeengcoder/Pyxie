from groq import (
    Groq,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)
from dotenv import load_dotenv
import os
import re

from core.usage import registrar_headers
from core import usage_groq
from core.prompt import montar_prompt as _montar_prompt
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel, ErroEntradaGrande
load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Modelo menor para tarefas internas (roteador, comentários, prompts de imagem).
# Cada modelo do Groq tem cota própria, então isso poupa o GROQ_MODEL.
# Para desligar sem mexer no código: GROQ_MODEL_ROTEADOR igual ao GROQ_MODEL.
GROQ_MODEL_ROTEADOR = (
    os.getenv("GROQ_MODEL_ROTEADOR", "qwen/qwen3.8-27b").strip() or GROQ_MODEL
)
MODELO_POR_TAREFA = {
    "roteador": GROQ_MODEL_ROTEADOR,
    "interna": GROQ_MODEL_ROTEADOR,
}

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


def _eh_gpt_oss(modelo: str) -> bool:
    return modelo.startswith("openai/gpt-oss")


def _chamar(
    comando: str, memoria: str, com_busca: bool, limite_saida=None, modelo=None
) -> str:
    modelo = modelo or GROQ_MODEL

    argumentos = {
        "model": modelo,
        "messages": _montar_mensagens(comando, memoria),
    }

    # reasoning_effort e browser_search só existem nos modelos gpt-oss;
    # em outros modelos (llama) o Groq devolveria erro 400.
    if _eh_gpt_oss(modelo):
        argumentos["reasoning_effort"] = "low"
        if com_busca:
            argumentos["tools"] = [{"type": "browser_search"}]
            argumentos["tool_choice"] = "auto"
    elif modelo.startswith("qwen/"):
        argumentos["reasoning_effort"] = "none"   # sem raciocínio: só a resposta

    if limite_saida:
        argumentos["max_completion_tokens"] = limite_saida

    raw = client.chat.completions.with_raw_response.create(**argumentos)

    # O painel de limites por minuto continua mostrando só o modelo principal.
    try:
        if modelo == GROQ_MODEL:
            registrar_headers(raw.headers, modelo)
    except Exception:
        pass  # nunca deixa isso quebrar a resposta principal

    response = raw.parse()

    uso = getattr(response, "usage", None)
    if uso:
        print(
            f"[Groq] {modelo} tokens: entrada={uso.prompt_tokens} "
            f"saída={uso.completion_tokens} total={uso.total_tokens}"
        )
        try:
            usage_groq.registrar(modelo, uso.total_tokens)
        except Exception as e:
            print(f"[usage_groq] {e}")

    escolha = response.choices[0]
    texto = (escolha.message.content or "").strip()
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

    if not texto:
        print(
            f"[Groq] resposta vazia: finish_reason={escolha.finish_reason}, "
            f"tool_calls={bool(getattr(escolha.message, 'tool_calls', None))}"
        )

    return texto


def _perguntar(comando: str, memoria: str, busca: bool, modelo: str) -> str:
    """Uma tentativa completa com UM modelo. Levanta ErroLLM em falha."""
    try:
        texto = _chamar(comando, memoria, busca, modelo=modelo)

        if not texto:
            texto = _chamar(
                comando, memoria, False, limite_saida=2000, modelo=modelo
            )

        return texto

    except Exception as e:
        if "tool_use_failed" in str(e):
            try:
                return _chamar(
                    comando + "\n\n(Responda apenas com texto. Você não tem "
                    "ferramentas de execução de código.)",
                    memoria,
                    False,
                    limite_saida=2000,
                    modelo=modelo,
                )
            except Exception as e2:
                e = e2

        erro = traduzir_erro_groq(e)
        print(f"[Groq] {erro}")
        raise erro from e


def perguntar_groq(
    comando: str,
    memoria: str = "",
    busca: bool = BUSCA_GROQ,
    tarefa: str = "conversa",
) -> str:
    """
    busca=False desliga a ferramenta browser_search.
    tarefa: "conversa" usa GROQ_MODEL; "roteador"/"interna" usam o modelo
    menor. Se o modelo menor falhar (cota, 413, vazio), tenta o GROQ_MODEL
    aqui dentro, para a cota do modelo menor NÃO pausar o Groq inteiro.
    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """
    modelo = MODELO_POR_TAREFA.get(tarefa, GROQ_MODEL)

    try:
        texto = _perguntar(comando, memoria, busca, modelo)
        if texto.strip() or modelo == GROQ_MODEL:
            return texto
        print(f"[Groq] {modelo} respondeu vazio; usando {GROQ_MODEL}")
    except ErroLLM as erro:
        if modelo == GROQ_MODEL:
            raise
        print(
            f"[Groq] {modelo} falhou ({type(erro).__name__}); "
            f"usando {GROQ_MODEL}"
        )

    return _perguntar(comando, memoria, busca, GROQ_MODEL)