# =============================================================
# core/firecrawl_scrape.py — Leitura de páginas via Firecrawl
#
# Falhas viram ErroCota / ErroIndisponivel / ErroLLM. O brain
# trata todas, então a leitura nunca derruba a conversa.
# =============================================================

import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from core import usage_servicos
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel

load_dotenv()

# Se der 404, confira a URL atual na documentação do Firecrawl
# e ajuste FIRECRAWL_URL no .env (ex.: .../v1/scrape).
URL = os.getenv("FIRECRAWL_URL", "https://api.firecrawl.dev/v2/scrape")
TIMEOUT = 45

MAX_CHARS_PAGINA = 4000   # cada página que acompanha uma busca
MAX_CHARS_LINK = 6000     # página que o usuário mandou direto

URL_NA_MENSAGEM = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def _paginas_por_busca() -> int:
    try:
        return max(0, int(os.getenv("FIRECRAWL_PAGINAS", "2")))
    except ValueError:
        return 2


def achar_url(texto: str):
    """Primeiro link http(s) da mensagem, sem pontuação no fim."""
    achado = URL_NA_MENSAGEM.search(texto or "")
    return achado.group(0).rstrip(".,;:!?") if achado else None


def _limpar(markdown: str) -> str:
    """Tira imagens e endereços dos links (economiza tokens)."""
    markdown = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown)
    markdown = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def ler_pagina(url: str, max_chars: int = MAX_CHARS_PAGINA):
    """Devolve {"url","titulo","texto"} ou None se a página vier vazia."""
    chave = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if not chave:
        raise ErroLLM("firecrawl", "FIRECRAWL_API_KEY não configurada")

    if urlparse(url).scheme not in ("http", "https"):
        raise ErroLLM("firecrawl", "endereço inválido")

    corpo = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "timeout": 30000,
    }

    try:
        r = requests.post(
            URL,
            headers={"Authorization": f"Bearer {chave}"},
            json=corpo,
            timeout=TIMEOUT,
        )
    except (requests.Timeout, requests.ConnectionError) as e:
        raise ErroIndisponivel("firecrawl", str(e)[:200]) from e
    except requests.RequestException as e:
        raise ErroLLM("firecrawl", str(e)[:200]) from e

    if r.status_code in (402, 429):
        raise ErroCota("firecrawl", f"HTTP {r.status_code}")
    if r.status_code >= 500:
        raise ErroIndisponivel("firecrawl", f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ErroLLM("firecrawl", f"HTTP {r.status_code}: {r.text[:150]}")

    try:
        dados = r.json()
    except ValueError as e:
        raise ErroLLM("firecrawl", "resposta não é JSON") from e

    conteudo = dados.get("data") or {}
    metadados = conteudo.get("metadata") or {}

    # Usa o valor real quando a API informa; senão, 1 crédito por página.
    creditos = metadados.get("creditsUsed") or 1
    usage_servicos.registrar("firecrawl", creditos)

    texto = _limpar(conteudo.get("markdown") or "")
    if not texto:
        return None

    return {
        "url": url,
        "titulo": (metadados.get("title") or "").strip(),
        "texto": texto[:max_chars],
    }


def ler_varias(urls: list, max_chars: int = MAX_CHARS_PAGINA) -> list:
    """Lê várias páginas ao mesmo tempo. Páginas que falharem são ignoradas."""
    urls = list(dict.fromkeys(u for u in urls if u))[: _paginas_por_busca()]
    if not urls:
        return []

    def _uma(url):
        try:
            return ler_pagina(url, max_chars)
        except ErroLLM as e:
            print(f"[Firecrawl] {url}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        return [p for p in pool.map(_uma, urls) if p]


def formatar_paginas(paginas: list) -> str:
    return "\n\n".join(
        f"=== PÁGINA: {p['titulo'] or p['url']} ({p['url']}) ===\n{p['texto']}"
        for p in paginas
    )