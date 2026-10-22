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

load_dotenv()

MODELO = os.getenv(
    "CLOUDFLARE_MODELO_IMAGEM", "@cf/bytedance/stable-diffusion-xl-lightning"
)
PASTA = Path(__file__).resolve().parent.parent / "data" / "imagens"
TIMEOUT = 120
MAX_CHARS_PROMPT = 500

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


def gerar(prompt: str) -> dict:
    """Devolve {"id","arquivo","formato","modelo"} ou levanta ErroLLM."""
    token = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    conta = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not token or not conta:
        raise ErroLLM("cloudflare", "CLOUDFLARE_API_TOKEN/ACCOUNT_ID não configurados")

    prompt = (prompt or "").strip()[:MAX_CHARS_PROMPT]
    if not prompt:
        raise ErroLLM("cloudflare", "prompt vazio")

    if usage_servicos.obter("cloudflare")["pedidos"] >= _max_por_dia():
        raise ErroCota("cloudflare", "limite diário de imagens da PYXIE atingido")

    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO}"
    corpo = {
        "prompt": prompt,
        "negative_prompt": "blurry, distorted, low quality, text, watermark",
        "width": 1024,
        "height": 1024,
        "num_steps": 4,
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
    imagem_id = uuid.uuid4().hex
    arquivo = PASTA / f"{imagem_id}.{ext}"
    arquivo.write_bytes(conteudo)

    usage_servicos.registrar("cloudflare", _neuronios_por_imagem())

    return {"id": imagem_id, "arquivo": str(arquivo), "formato": ext, "modelo": MODELO}


def caminho_da_imagem(imagem_id: str):
    """Caminho do arquivo, ou None. Valida o id (evita acesso a outras pastas)."""
    if not _ID_VALIDO.match(imagem_id or ""):
        return None
    for ext in ("jpg", "png"):
        caminho = PASTA / f"{imagem_id}.{ext}"
        if caminho.exists():
            return caminho
    return None