# =============================================================
# core/cloudflare_imagem.py — Geração de imagens (Workers AI)
#
# Falhas viram ErroCota / ErroIndisponivel / ErroLLM, como nos
# outros serviços. As imagens ficam em data/imagens/.
# =============================================================

import base64
import os
import re
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

from core import usage_servicos
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel
from core import db

load_dotenv()

MODELO = os.getenv(
    "CLOUDFLARE_MODELO_IMAGEM", "@cf/bytedance/stable-diffusion-xl-lightning"
)
PASTA = Path(__file__).resolve().parent.parent / "data" / "imagens"
TIMEOUT = 120
MAX_CHARS_PROMPT = 500
LARGURA = 1024
ALTURA = 1024
ETAPAS = 4

_ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


def _max_por_dia() -> int:
    try:
        return max(0, int(os.getenv("CLOUDFLARE_MAX_IMAGENS_DIA", "20")))
    except ValueError:
        return 20


def _neuronios_por_imagem() -> int:
    # A API não informa o custo na resposta. Veja o consumo real no painel
    # da Cloudflare (Workers AI) e ajuste este valor no .env.
    try:
        return max(0, int(os.getenv("CLOUDFLARE_NEURONIOS_POR_IMAGEM", "0")))
    except ValueError:
        return 0


def _gerar_e_salvar(prompt: str, imagem_id: str) -> dict:
    """Chama a Cloudflare e grava o arquivo. Levanta ErroLLM em falha."""
    token = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    conta = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not token or not conta:
        raise ErroLLM("cloudflare", "CLOUDFLARE_API_TOKEN/ACCOUNT_ID não configurados")

    if not prompt:
        raise ErroLLM("cloudflare", "prompt vazio")

    if usage_servicos.obter("cloudflare")["pedidos"] >= _max_por_dia():
        raise ErroCota("cloudflare", "limite diário de imagens da PYXIE atingido")

    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO}"
    corpo = {
        "prompt": prompt,
        "negative_prompt": "blurry, distorted, low quality, text, watermark",
        "width": LARGURA,
        "height": ALTURA,
        "num_steps": ETAPAS,
    }

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=corpo,
            timeout=TIMEOUT,
        )
    except (requests.Timeout, requests.ConnectionError) as e:
        raise ErroIndisponivel("cloudflare", str(e)[:200]) from e
    except requests.RequestException as e:
        raise ErroLLM("cloudflare", str(e)[:200]) from e

    if r.status_code == 429:
        raise ErroCota("cloudflare", "HTTP 429")
    if r.status_code >= 500:
        raise ErroIndisponivel("cloudflare", f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ErroLLM("cloudflare", f"HTTP {r.status_code}: {r.text[:200]}")

    conteudo = r.content

    # Alguns modelos devolvem JSON com a imagem em base64.
    if "json" in (r.headers.get("Content-Type") or "").lower():
        try:
            b64 = (r.json().get("result") or {}).get("image") or ""
            conteudo = base64.b64decode(b64)
        except Exception as e:
            raise ErroLLM("cloudflare", "resposta JSON sem imagem") from e

    if conteudo.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = "png"
    else:
        raise ErroLLM("cloudflare", "formato de imagem não reconhecido")

    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{imagem_id}.{ext}"
    arquivo.write_bytes(conteudo)

    usage_servicos.registrar("cloudflare", _neuronios_por_imagem())

    return {
        "id": imagem_id,
        "arquivo": str(arquivo),
        "formato": ext,
        "modelo": MODELO,
    }


def _registrar_geracao(imagem_id, chat_id, prompt_original, prompt_enviado,
                       resultado, erro=None, arquivo_chave=None):
    """Grava no banco. db.registrar_geracao nunca levanta erro."""
    neuronios = _neuronios_por_imagem() if resultado == "ok" else 0

    db.registrar_geracao(
        imagem_id=imagem_id,
        chat_id=chat_id,
        servico="cloudflare",
        modelo=MODELO,
        operacao="texto_para_imagem",
        prompt_original=prompt_original,
        prompt_enviado=prompt_enviado,
        resultado=resultado,
        erro=(str(erro)[:500] if erro else None),
        etapas=ETAPAS,
        largura=LARGURA,
        altura=ALTURA,
        neuronios=(neuronios or None),   # NULL quando não confirmado
        custo_usd=None,                  # NULL quando não confirmado
        arquivo_chave=arquivo_chave,
    )


def gerar(prompt: str, prompt_original: str = None, chat_id: str = None) -> dict:
    """Devolve {"id","arquivo","formato","modelo"} ou levanta ErroLLM.

    prompt           -> prompt em inglês enviado ao modelo
    prompt_original  -> descrição em português (só para o registro)
    chat_id          -> chat de origem (só para o registro)
    """
    imagem_id = uuid.uuid4().hex
    prompt = (prompt or "").strip()[:MAX_CHARS_PROMPT]

    try:
        resultado = _gerar_e_salvar(prompt, imagem_id)
    except ErroLLM as erro:
        _registrar_geracao(
            imagem_id, chat_id, prompt_original, prompt,
            "erro", erro=erro,
        )
        raise

    _registrar_geracao(
        imagem_id, chat_id, prompt_original, prompt,
        "ok", arquivo_chave=f"{imagem_id}.{resultado['formato']}",
    )
    return resultado


def caminho_da_imagem(imagem_id: str):
    """Caminho do arquivo, ou None. Valida o id (evita acesso a outras pastas)."""
    if not _ID_VALIDO.match(imagem_id or ""):
        return None
    for ext in ("jpg", "png"):
        caminho = PASTA / f"{imagem_id}.{ext}"
        if caminho.exists():
            return caminho
    return None