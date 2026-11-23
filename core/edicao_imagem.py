# =============================================================
# core/edicao_imagem.py — Ajustes simples de imagem (Pillow)
#
# O LLM só traduz o pedido em operações de uma lista fechada;
# quem edita é o Pillow. Edição criativa (remover objeto, mudar
# cor, adicionar elemento) NÃO é feita aqui.
# =============================================================

import base64
import io
import json
import re
import unicodedata
import uuid
import os

import requests

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.cloudflare_imagem import PASTA, caminho_da_imagem
from core.llm import perguntar_llm
from core import cloudflare_imagem as cf
from core import usage_servicos
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel
from core import galeria

Image.MAX_IMAGE_PIXELS = 40_000_000

MAX_OPERACOES = 6
LADO_MAX = 2048
MAX_BYTES = 6_000_000

_EDITAR = re.compile(
    r"\b(corte|corta|cortar|recorte|recorta|recortar|gire|gira|girar|rotacione|rotaciona|"
    r"rotacionar|espelhe|espelha|espelhar|inverta|inverte|inverter|redimensione|redimensiona|"
    r"redimensionar|clareie|clareia|clarear|escureca|escurece|escurecer|brilho|contraste|"
    r"saturacao|nitidez|desfoque|desfoca|desfocar|borre|borra|sepia|negativo|"
    r"preto e branco|preta e branca|escala de cinza|cinza)\b"
)
_TAMANHO = re.compile(
    r"\b(aument\w+|diminu\w+|reduz\w*|ampl\w+)\b.{0,30}\b(imagem|foto|tamanho|largura|altura|resolucao)\b"
    r"|\b(aument\w+|diminu\w+|reduz\w*|ampl\w+)\b.{0,15}\b\d{1,3}\s*%"
    r"|\b(remov\w+|tir[ae]|apag\w+|troc\w+|mud\w+)\b.{0,30}\b(pessoa|objeto|fundo|cor)\b"
)


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower().strip())
    return t.encode("ascii", "ignore").decode()


def parece_pedido_de_edicao(texto: str) -> bool:
    """Filtro barato: só chama o LLM quando a frase tem cara de edição."""
    t = _norm(texto)
    return bool(t) and len(t) <= 300 and bool(_EDITAR.search(t) or _TAMANHO.search(t))


# ---------------- arquivo ----------------

def _abrir_bytes(dados: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(dados))
    img.load()
    img = ImageOps.exif_transpose(img)
    rgba = img.convert("RGBA")
    base = Image.new("RGB", rgba.size, (255, 255, 255))
    base.paste(rgba, mask=rgba.split()[3])
    return base


def _salvar(img: Image.Image) -> str:
    imagem_id = uuid.uuid4().hex
    PASTA.mkdir(parents=True, exist_ok=True)
    img.save(PASTA / f"{imagem_id}.jpg", "JPEG", quality=90)
    return imagem_id


def salvar_data_url(data_url: str) -> str:
    cab, sep, dados = str(data_url or "").partition(",")
    if not sep or not cab.startswith("data:image/") or not cab.endswith(";base64"):
        raise ValueError("imagem inválida")
    bruto = base64.b64decode("".join(dados.split()), validate=True)
    if len(bruto) > MAX_BYTES:
        raise ValueError("imagem grande demais")
    return _salvar(_abrir_bytes(bruto))


def _abrir_id(imagem_id: str) -> Image.Image:
    caminho = caminho_da_imagem(imagem_id) or galeria.garantir_em_disco(imagem_id)
    if caminho is None:
        raise ValueError("imagem não encontrada")
    return _abrir_bytes(caminho.read_bytes())


# ---------------- interpretar o pedido (LLM) ----------------

def _ler_json(texto):
    achado = re.search(r"\{.*\}", texto or "", re.DOTALL)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


def interpretar(mensagem: str):
    """{"operacoes": [...], "criativa": bool} ou None se falhar."""
    instrucao = (
        "Tarefa técnica. Converta o pedido de edição de imagem em operações. "
        'Responda SOMENTE com JSON: {"operacoes": [...], "criativa": false}\n'
        "Operações permitidas:\n"
        '{"op":"cortar","esquerda":0,"topo":0,"direita":100,"baixo":100}  (valores em % da imagem)\n'
        '{"op":"girar","graus":90}  (positivo = sentido horário)\n'
        '{"op":"espelhar","eixo":"horizontal"}  (ou "vertical")\n'
        '{"op":"redimensionar","largura":800,"altura":600}  (omita um dos dois para manter a proporção) '
        'ou {"op":"redimensionar","percentual":50}\n'
        '{"op":"brilho","fator":1.3}  {"op":"contraste","fator":1.3}  {"op":"saturacao","fator":1.3}  '
        '{"op":"nitidez","fator":2}  (1 = igual)\n'
        '{"op":"preto_e_branco"}  {"op":"sepia"}  {"op":"negativo"}  {"op":"desfocar","raio":4}\n'
        f"Máximo de {MAX_OPERACOES} operações, na ordem pedida.\n"
        'Se o pedido exigir algo fora da lista (remover ou adicionar objeto, mudar cor de algo, '
        'estilo artístico), responda {"operacoes": [], "criativa": true, "instrucao": "..."} '
        'onde instrucao é UMA frase imperativa em INGLÊS com só a mudança pedida, terminando em '
        '"Keep everything else unchanged." (ex.: "Remove the person in the background. '
        'Keep everything else unchanged."). '
        'Se a mensagem não for um pedido de edição, responda {"operacoes": [], "criativa": false}.\n\n'
        f"Pedido: {mensagem}"
    )
    try:
        texto = perguntar_llm(
            instrucao, "(tarefa técnica, sem cumprimentos)", leve=True, tarefa="roteador"
        )
    except ErroLLM as e:
        print(f"[edicao_imagem] {e}")
        return None

    dados = _ler_json(texto)
    if dados is None:
        return None
    ops = dados.get("operacoes")
    ops = [o for o in ops if isinstance(o, dict)][:MAX_OPERACOES] if isinstance(ops, list) else []
    return {
        "operacoes": ops,
        "criativa": bool(dados.get("criativa")),
        "instrucao": str(dados.get("instrucao") or "").strip()[:400],
    }


# ---------------- aplicar (Pillow) ----------------

def _num(v, lo, hi, padrao=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return padrao
    return max(lo, min(hi, x))


def _aplicar_uma(img: Image.Image, op: dict):
    nome = str(op.get("op") or "")
    w, h = img.size

    if nome == "cortar":
        e = _num(op.get("esquerda"), 0, 100, 0)
        t = _num(op.get("topo"), 0, 100, 0)
        d = _num(op.get("direita"), 0, 100, 100)
        b = _num(op.get("baixo"), 0, 100, 100)
        if d - e < 5 or b - t < 5:
            raise ValueError("corte pequeno demais")
        caixa = (int(w * e / 100), int(h * t / 100), int(w * d / 100), int(h * b / 100))
        return img.crop(caixa), "cortei a imagem"

    if nome == "girar":
        g = _num(op.get("graus"), -360, 360)
        if g is None:
            raise ValueError("faltou o ângulo")
        return img.rotate(-g, expand=True, fillcolor=(255, 255, 255)), f"girei {g:g}° no sentido horário"

    if nome == "espelhar":
        if str(op.get("eixo")).lower() == "vertical":
            return ImageOps.flip(img), "espelhei na vertical"
        return ImageOps.mirror(img), "espelhei na horizontal"

    if nome == "redimensionar":
        pct = _num(op.get("percentual"), 1, 400)
        if pct:
            nl, na = w * pct / 100, h * pct / 100
        else:
            l = _num(op.get("largura"), 1, LADO_MAX)
            a = _num(op.get("altura"), 1, LADO_MAX)
            if l and a:
                nl, na = l, a
            elif l:
                nl, na = l, h * l / w
            elif a:
                nl, na = w * a / h, a
            else:
                raise ValueError("faltou o tamanho")
        escala = min(1.0, LADO_MAX / max(nl, na))
        nl, na = max(1, int(nl * escala)), max(1, int(na * escala))
        return img.resize((nl, na), Image.Resampling.LANCZOS), f"redimensionei para {nl}×{na}px"

    if nome in ("brilho", "contraste", "saturacao", "nitidez"):
        f = _num(op.get("fator"), 0, 5 if nome == "nitidez" else 4)
        if f is None:
            raise ValueError("faltou o fator")
        classe = {
            "brilho": ImageEnhance.Brightness,
            "contraste": ImageEnhance.Contrast,
            "saturacao": ImageEnhance.Color,
            "nitidez": ImageEnhance.Sharpness,
        }[nome]
        rotulo = {"brilho": "o brilho", "contraste": "o contraste",
                  "saturacao": "a saturação", "nitidez": "a nitidez"}[nome]
        return classe(img).enhance(f), f"ajustei {rotulo}"

    if nome == "preto_e_branco":
        return ImageOps.grayscale(img).convert("RGB"), "deixei em preto e branco"

    if nome == "sepia":
        cinza = ImageOps.grayscale(img)
        return ImageOps.colorize(cinza, black="#2b1a0a", mid="#9a7a52", white="#f3e2c0"), "apliquei sépia"

    if nome == "negativo":
        return ImageOps.invert(img.convert("RGB")), "inverti as cores"

    if nome == "desfocar":
        r = _num(op.get("raio"), 0.5, 20, 4)
        return img.filter(ImageFilter.GaussianBlur(r)), "apliquei desfoque"

    raise ValueError(f"operação desconhecida: {nome}")


def aplicar_e_salvar(imagem_id: str, ops: list) -> dict:
    """Levanta ValueError/OSError se algo der errado. Devolve {"id","resumo"}."""
    img = _abrir_id(imagem_id)
    feitas = []
    for op in ops[:MAX_OPERACOES]:
        img, descricao = _aplicar_uma(img, op)
        feitas.append(descricao)
    if not feitas:
        raise ValueError("nenhuma operação")
    return {"id": _salvar(img), "resumo": ", ".join(feitas)}

MODELO_EDICAO = os.getenv("CLOUDFLARE_MODELO_EDICAO", "@cf/black-forest-labs/flux-2-klein-9b")
LADO_ENTRADA = 480   # a Cloudflare exige entrada menor que 512x512
LADO_SAIDA = int(os.getenv("CLOUDFLARE_EDICAO_LADO") or 1024)


def editar_criativa(imagem_id: str, instrucao: str) -> dict:
    """Edição por IA (FLUX.2 klein, imagem para imagem). Devolve {"id"}.
    Levanta ErroLLM (ou ValueError/OSError se a imagem não abrir)."""
    token = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    conta = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not token or not conta:
        raise ErroLLM("cloudflare", "CLOUDFLARE_API_TOKEN/ACCOUNT_ID não configurados")

    instrucao = (instrucao or "").strip()[:500]
    if not instrucao:
        raise ErroLLM("cloudflare", "instrução vazia")

    if usage_servicos.obter("cloudflare")["pedidos"] >= cf._max_por_dia():
        raise ErroCota("cloudflare", "limite diário de imagens da PYXIE atingido")

    img = _abrir_id(imagem_id)
    w, h = img.size

    entrada = ImageOps.contain(img, (LADO_ENTRADA, LADO_ENTRADA))
    buf = io.BytesIO()
    entrada.save(buf, "JPEG", quality=92)

    escala = min(1.0, LADO_SAIDA / max(w, h))
    sw = max(256, int(round(w * escala / 16)) * 16)
    sh = max(256, int(round(h * escala / 16)) * 16)

    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO_EDICAO}"

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"prompt": instrucao, "width": str(sw), "height": str(sh)},
            files={"input_image_0": ("imagem.jpg", buf.getvalue(), "image/jpeg")},
            timeout=cf.TIMEOUT,
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
    if "json" in (r.headers.get("Content-Type") or "").lower():
        try:
            b64 = (r.json().get("result") or {}).get("image") or ""
            conteudo = base64.b64decode(b64)
        except Exception as e:
            raise ErroLLM("cloudflare", "resposta JSON sem imagem") from e

    try:
        nova = _abrir_bytes(conteudo)
    except Exception as e:
        raise ErroLLM("cloudflare", "imagem devolvida ilegível") from e

    usage_servicos.registrar("cloudflare", cf._neuronios_por_imagem())
    return {"id": _salvar(nova)}