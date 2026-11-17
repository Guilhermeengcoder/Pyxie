import base64
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

# Modelo de volume: reserva do Auto, tarefas internas e imagens (500 pedidos/dia).
# GEMINI_MODEL fica reservado ao trabalho "longo" (arquivos e código grandes).
GEMINI_MODEL_VOLUME = (
    os.getenv("GEMINI_MODEL_VOLUME", "gemini-3.5-flash-lite").strip() or GEMINI_MODEL
)

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

# Pedidos que continuam um arquivo grande já enviado: modelo de volume por padrão.
GEMINI_MODEL_CONTINUACAO = (
    os.getenv("GEMINI_MODEL_CONTINUACAO", "").strip() or GEMINI_MODEL_VOLUME
)


def _modelo_da_tarefa(tarefa: str) -> str:
    if tarefa == "longo":
        return GEMINI_MODEL
    if tarefa == "continuacao":
        return GEMINI_MODEL_CONTINUACAO
    return GEMINI_MODEL_VOLUME


def _gerar_texto(prompt: str, modelo: str) -> str:
    argumentos = {"model": modelo, "input": prompt}

    if GEMINI_BUSCA:
        argumentos["tools"] = [{"type": "google_search"}]

    try:
        interaction = client.interactions.create(**argumentos)
    except Exception as e:
        print(f"[Gemini] {modelo}: {e}")
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

    print(f"[Gemini] {modelo} ok")
    return texto


def perguntar_gemini(comando: str, memoria: str = "", tarefa: str = "conversa") -> str:
    """
    tarefa="longo" usa GEMINI_MODEL (3.6 Flash); as demais usam o modelo
    de volume. Se o modelo "longo" estourar a cota, tenta o de volume.
    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """
    prompt = montar_prompt(comando, memoria)
    modelo = _modelo_da_tarefa(tarefa)

    try:
        return _gerar_texto(prompt, modelo)
    except ErroCota:
        if modelo == GEMINI_MODEL_VOLUME:
            raise
        print(f"[Gemini] cota de {modelo} esgotada; usando {GEMINI_MODEL_VOLUME}")
        return _gerar_texto(prompt, GEMINI_MODEL_VOLUME)

# ================================================================
# GEMINI — IMAGEM
#
# Privacidade (decisão "opção A"): o Gemini recebe SÓ a imagem e a
# pergunta. O histórico da conversa e a memória fixa NÃO vão junto;
# o parâmetro `memoria` existe apenas para manter a mesma assinatura
# do Groq e é ignorado de propósito.
# ================================================================

MIMES_IMAGEM = {"image/jpeg", "image/png", "image/webp"}

# Texto no lugar do histórico: evita que o prompt peça um cumprimento
# (ele só cumprimenta quando o histórico está vazio).
SEM_HISTORICO = "(sem histórico: neste modo a imagem é enviada sozinha)"


def _separar_data_url(data_url: str):
    """'data:image/jpeg;base64,AAAA' -> ('image/jpeg', 'AAAA'). Valida o formato."""
    cabecalho, separador, dados = str(data_url or "").partition(",")

    if (
        not separador
        or not cabecalho.startswith("data:")
        or not cabecalho.endswith(";base64")
    ):
        raise ErroLLM("gemini", "imagem inválida (esperado data URL base64)")

    mime = cabecalho[len("data:"):-len(";base64")].strip().lower()

    if mime not in MIMES_IMAGEM:
        raise ErroLLM("gemini", f"tipo de imagem não suportado: {mime or '?'}")

    dados = "".join(dados.split())

    try:
        base64.b64decode(dados, validate=True)
    except Exception:
        raise ErroLLM("gemini", "imagem inválida (base64 corrompido)")

    return mime, dados


def perguntar_gemini_imagem(comando: str, imagem_data_url: str, memoria: str = "") -> str:
    """
    comando          -> o que o usuário escreveu (pode vir vazio)
    imagem_data_url  -> "data:image/jpeg;base64,...."
    memoria          -> IGNORADA (ver nota de privacidade acima)

    Em caso de falha levanta ErroCota, ErroIndisponivel ou ErroLLM.
    """
    mime, dados = _separar_data_url(imagem_data_url)

    pergunta = (comando or "").strip() or "Descreva o que você vê nesta imagem."
    pergunta += (
        "\n(O usuário anexou uma imagem. Responda com base no que você vê nela.)"
    )

    prompt = montar_prompt(pergunta, SEM_HISTORICO)

    entrada = [
        {"type": "text", "text": prompt},
        {"type": "image", "data": dados, "mime_type": mime},
    ]

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL_VOLUME, input=entrada
        )
    except Exception as e:
        print(f"[Gemini imagem] {e}")
        raise _traduzir_erro(e) from e

    try:
        usage_gemini.registrar(
            usage_gemini.tokens_da_interacao(interaction, prompt)
        )
    except Exception as e:
        print(f"[usage_gemini] {e}")  # nunca quebra a resposta

    texto = (interaction.output_text or "").strip()

    if not texto:
        raise ErroLLM("gemini", "resposta vazia da imagem")

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