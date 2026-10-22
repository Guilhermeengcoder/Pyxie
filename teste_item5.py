
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")

MODELO = "@cf/bytedance/stable-diffusion-xl-lightning"

if not API_TOKEN or not ACCOUNT_ID:
    raise SystemExit(
        "Configure CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID no .env."
    )

url = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{ACCOUNT_ID}/ai/run/{MODELO}"
)

cabecalhos = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

dados = {
    "prompt": (
        "A beautiful little magical fairy assistant, "
        "anime style, red and black colors, glowing wings, "
        "high detail, digital illustration"
    ),
    "negative_prompt": "blurry, distorted, low quality, text, watermark",
    "width": 1024,
    "height": 1024,
    "num_steps": 4,
}

print("Solicitando geração de imagem ao Cloudflare Workers AI...")

try:
    resposta = requests.post(
        url,
        headers=cabecalhos,
        json=dados,
        timeout=180,
    )

    print("Status HTTP:", resposta.status_code)
    print("Content-Type:", resposta.headers.get("Content-Type"))
    print("Tamanho:", len(resposta.content), "bytes")

    if not resposta.ok:
        print("Detalhes do erro:", resposta.text[:2000])
        raise SystemExit(1)

    inicio = resposta.content[:8]

    if resposta.content.startswith(b"\xff\xd8\xff"):
        extensao = ".jpg"
        formato = "JPEG"
    elif inicio == b"\x89PNG\r\n\x1a\n":
        extensao = ".png"
        formato = "PNG"
    else:
        print("Formato de imagem não reconhecido.")
        print("Primeiros bytes:", repr(resposta.content[:100]))
        raise SystemExit(1)

    arquivo_saida = BASE_DIR / "data" / f"teste_cloudflare{extensao}"
    arquivo_saida.parent.mkdir(parents=True, exist_ok=True)
    arquivo_saida.write_bytes(resposta.content)

    print(f"Imagem {formato} salva com sucesso!")
    print("Arquivo:", arquivo_saida.resolve())
    print(f"Tamanho: {len(resposta.content):,} bytes")

except requests.RequestException as erro:
    print("Falha na comunicação com a Cloudflare:", erro)
