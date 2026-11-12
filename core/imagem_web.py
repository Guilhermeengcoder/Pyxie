# =============================================================
# core/imagem_web.py — Fotos reais da internet (Tavily + Pillow)
#
# montar(itens) -> {"id", "arquivo", "formato", "rotulos", "faltaram", "fontes"}
#   itens = [{"rotulo": "Brasil", "consulta": "flag of Brazil"}, ...]
#
# Baixa as imagens NO SERVIDOR, valida e salva em data/imagens/
# (o mesmo lugar das imagens geradas), então /imagens/{id} serve.
# Vários itens viram uma colagem com legendas. Falhas viram ErroLLM.
# =============================================================

import io
import ipaddress
import os
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import matplotlib
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from core import tavily_search
from core.cloudflare_imagem import PASTA
from core.llm_erros import ErroLLM

MAX_ITENS = 4
CANDIDATAS_POR_ITEM = 4      # quantas URLs tentar por item até uma servir
MAX_BYTES = 6_000_000
TIMEOUT = 8
LADO_MIN = 150               # descarta ícones e miniaturas
LADO_UNICA = 1024
TILE_L, TILE_A, LEGENDA = 480, 320, 36

FUNDO = (13, 11, 16)
TEXTO = (236, 236, 236)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PYXIE-AI/4.6)"}

Image.MAX_IMAGE_PIXELS = 40_000_000   # recusa "bombas" de descompressão


def _host_publico(host: str) -> bool:
    """False se o endereço aponta para rede interna (proteção contra SSRF)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def _baixar(url: str):
    """Baixa só imagens https de hosts públicos, com limite de tamanho."""
    atual = url
    try:
        for _ in range(3):   # até 2 redirecionamentos, validando cada um
            p = urlparse(atual)
            if p.scheme != "https" or not p.hostname or not _host_publico(p.hostname):
                return None

            r = requests.get(
                atual, headers=HEADERS, timeout=TIMEOUT,
                stream=True, allow_redirects=False,
            )
            try:
                if r.status_code in (301, 302, 303, 307, 308):
                    atual = urljoin(atual, r.headers.get("location", ""))
                    continue
                if r.status_code != 200:
                    return None

                tipo = (r.headers.get("content-type") or "").lower()
                if not tipo.startswith("image/") or "svg" in tipo:
                    return None

                dados = bytearray()
                for bloco in r.iter_content(65536):
                    dados.extend(bloco)
                    if len(dados) > MAX_BYTES:
                        return None
                return bytes(dados)
            finally:
                r.close()
    except requests.RequestException:
        return None
    return None


def _abrir(dados):
    if not dados:
        return None
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
        img = ImageOps.exif_transpose(img)
        if min(img.size) < LADO_MIN:
            return None

        # PNG com transparência (bandeiras, logos) vira fundo branco
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.split()[3])
        return base
    except Exception as e:
        print(f"[ImagemWeb] imagem inválida: {e}")
        return None


def _buscar_item(par):
    rotulo, consulta = par
    try:
        busca = tavily_search.buscar(consulta, imagens=True, max_resultados=3)
    except ErroLLM as e:
        print(f"[ImagemWeb] busca falhou ({consulta!r}): {e}")
        return None
    if not busca:
        return None

    for url in (busca.get("imagens") or [])[:CANDIDATAS_POR_ITEM]:
        img = _abrir(_baixar(url))
        if img is not None:
            return rotulo, img, urlparse(url).hostname
    return None


def _fonte():
    try:
        caminho = os.path.join(
            matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf"
        )
        return ImageFont.truetype(caminho, 20)
    except Exception:
        return ImageFont.load_default()


def _colagem(tiles):
    colunas = 2
    linhas = (len(tiles) + colunas - 1) // colunas
    tela = Image.new("RGB", (colunas * TILE_L, linhas * (TILE_A + LEGENDA)), FUNDO)
    desenho = ImageDraw.Draw(tela)
    fonte = _fonte()

    for i, (rotulo, img) in enumerate(tiles):
        x = (i % colunas) * TILE_L
        y = (i // colunas) * (TILE_A + LEGENDA)

        mini = ImageOps.contain(img, (TILE_L - 16, TILE_A - 16))
        tela.paste(
            mini,
            (x + (TILE_L - mini.width) // 2, y + (TILE_A - mini.height) // 2),
        )

        try:
            desenho.text(
                (x + TILE_L // 2, y + TILE_A + LEGENDA // 2),
                rotulo, font=fonte, fill=TEXTO, anchor="mm",
            )
        except ValueError:   # fonte sem suporte a âncora
            desenho.text((x + 10, y + TILE_A + 8), rotulo, font=fonte, fill=TEXTO)

    return tela


def montar(itens: list) -> dict:
    pares = []
    for it in itens[:MAX_ITENS]:
        if not isinstance(it, dict):
            continue
        consulta = str(it.get("consulta") or "").strip()[:200]
        rotulo = str(it.get("rotulo") or consulta).strip()[:30]
        if consulta:
            pares.append((rotulo, consulta))

    if not pares:
        raise ErroLLM("imagem_web", "nenhum item para buscar")

    with ThreadPoolExecutor(max_workers=len(pares)) as pool:
        resultados = list(pool.map(_buscar_item, pares))

    achados = [r for r in resultados if r]
    faltaram = [p[0] for p, r in zip(pares, resultados) if not r]

    if not achados:
        raise ErroLLM("imagem_web", "nenhuma imagem utilizável")

    if len(achados) == 1:
        img = achados[0][1].copy()
        img.thumbnail((LADO_UNICA, LADO_UNICA))   # só reduz, nunca amplia
    else:
        img = _colagem([(rot, im) for rot, im, _ in achados])

    imagem_id = uuid.uuid4().hex
    PASTA.mkdir(parents=True, exist_ok=True)
    caminho = PASTA / f"{imagem_id}.jpg"
    img.save(caminho, "JPEG", quality=88)

    return {
        "id": imagem_id,
        "arquivo": str(caminho),
        "formato": "jpg",
        "rotulos": [rot for rot, _, _ in achados],
        "faltaram": faltaram,
        "fontes": sorted({f for _, _, f in achados if f}),
    }