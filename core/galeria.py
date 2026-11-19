# =============================================================
# core/galeria.py — Galeria de imagens (Postgres) + busca no acervo
#
# registrar/listar/excluir: a galeria que o usuário vê.
# catalogo/escolher/como_data_url: a PYXIE rever e comparar imagens.
# Nenhuma função daqui derruba o chat: falhas viram False/[]/None.
# =============================================================

import base64
import io
import json
import os
import re
import unicodedata
from zoneinfo import ZoneInfo

from PIL import Image

from core import db
from core.cloudflare_imagem import PASTA, caminho_da_imagem, _ID_VALIDO
from core.llm import perguntar_llm
from core.llm_erros import ErroLLM

MAX_IMAGENS = int(os.getenv("GALERIA_MAX", "200"))
GUARDAR_ENVIADAS = os.getenv("GALERIA_ENVIADAS", "1").strip() != "0"
LADO_ANALISE = 1024
MAX_ESCOLHIDAS = 4


# ---------------- bytes ----------------

def _bytes(imagem_id: str):
    caminho = caminho_da_imagem(imagem_id)
    if caminho is not None:
        return caminho.read_bytes()
    if not _ID_VALIDO.match(imagem_id or ""):
        return None
    linhas = db.executar("SELECT dados FROM galeria WHERE imagem_id = %s", (imagem_id,))
    return bytes(linhas[0]["dados"]) if linhas else None


def _miniatura(dados: bytes) -> bytes:
    img = Image.open(io.BytesIO(dados))
    img.load()
    img = img.convert("RGB")
    img.thumbnail((320, 320))
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=70)
    return saida.getvalue()


def garantir_em_disco(imagem_id: str):
    """Caminho do arquivo; se o disco foi apagado, recria a partir do banco."""
    caminho = caminho_da_imagem(imagem_id)
    if caminho is not None:
        return caminho
    if not _ID_VALIDO.match(imagem_id or ""):
        return None
    try:
        linhas = db.executar(
            "SELECT dados, formato FROM galeria WHERE imagem_id = %s", (imagem_id,)
        )
        if not linhas:
            return None
        ext = "png" if linhas[0]["formato"] == "png" else "jpg"
        PASTA.mkdir(parents=True, exist_ok=True)
        destino = PASTA / f"{imagem_id}.{ext}"
        destino.write_bytes(bytes(linhas[0]["dados"]))
        return destino
    except Exception as e:
        print(f"[galeria] não consegui restaurar {imagem_id}: {e}")
        return None


# ---------------- galeria (o que o usuário vê) ----------------

def registrar(imagem_id: str, origem: str, descricao: str = "", chat_id=None) -> bool:
    try:
        if not db.disponivel():
            return False
        if origem == "enviada" and not GUARDAR_ENVIADAS:
            return False
        caminho = caminho_da_imagem(imagem_id)
        if caminho is None:
            return False

        dados = caminho.read_bytes()
        db.executar(
            """
            INSERT INTO galeria
                (imagem_id, origem, descricao, chat_id, formato, tamanho, miniatura, dados)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (imagem_id) DO NOTHING
            """,
            (
                imagem_id, origem, (descricao or "")[:300], chat_id,
                caminho.suffix.lstrip("."), len(dados), _miniatura(dados), dados,
            ),
        )
        # Passou do limite: remove as mais antigas.
        db.executar(
            """
            DELETE FROM galeria WHERE id IN (
                SELECT id FROM galeria ORDER BY criada_em DESC OFFSET %s
            )
            """,
            (MAX_IMAGENS,),
        )
        return True
    except Exception as e:
        print(f"[galeria] não consegui registrar: {e}")
        return False


def descrever(imagem_id: str, descricao: str):
    try:
        db.executar(
            "UPDATE galeria SET descricao = %s WHERE imagem_id = %s",
            ((descricao or "")[:300], imagem_id),
        )
    except Exception as e:
        print(f"[galeria] não consegui descrever: {e}")


def listar(limite: int = 100) -> list:
    limite = max(1, min(int(limite), 500))
    try:
        return db.executar(
            """
            SELECT imagem_id, origem, descricao, chat_id, formato, tamanho, criada_em
            FROM galeria ORDER BY criada_em DESC LIMIT %s
            """,
            (limite,),
        ) or []
    except Exception as e:
        print(f"[galeria] não consegui listar: {e}")
        return []


def obter_miniatura(imagem_id: str):
    if not _ID_VALIDO.match(imagem_id or ""):
        return None
    try:
        linhas = db.executar(
            "SELECT miniatura FROM galeria WHERE imagem_id = %s", (imagem_id,)
        )
        return bytes(linhas[0]["miniatura"]) if linhas and linhas[0]["miniatura"] else None
    except Exception as e:
        print(f"[galeria] miniatura: {e}")
        return None


def excluir(imagem_id: str) -> bool:
    if not _ID_VALIDO.match(imagem_id or ""):
        return False
    try:
        linhas = db.executar(
            "DELETE FROM galeria WHERE imagem_id = %s RETURNING id", (imagem_id,)
        )
    except Exception as e:
        print(f"[galeria] não consegui excluir: {e}")
        return False

    for ext in ("jpg", "png"):
        arq = PASTA / f"{imagem_id}.{ext}"
        try:
            if arq.exists():
                arq.unlink()
        except OSError:
            pass

    return bool(linhas)


# ---------------- rever e comparar imagens antigas ----------------

_OBJETO = re.compile(
    r"\b(imagem|imagens|foto|fotos|figura|figuras|print|prints|desenho|desenhos|"
    r"grafico|graficos|ilustracao|ilustracoes)\b"
)
_ACAO = re.compile(
    r"\b(compar\w+|diferenc\w+|semelhan\w+|parecid\w+|igual|iguais|anterior|anteriores|"
    r"antiga|antigas|antigo|antigos|aquela|aquelas|aquele|primeira|segunda|terceira|"
    r"ultima|ontem|outra|outras|duas|dois|ambas|ambos|de novo|novamente|mesma|mesmas|"
    r"rever|reveja|lembra)\b"
)


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return t.encode("ascii", "ignore").decode()


def parece_referencia_a_imagens(texto: str) -> bool:
    """Filtro barato: só chama o LLM quando a frase fala de imagens já vistas."""
    t = _norm(texto).strip()
    return bool(t) and len(t) <= 300 and bool(_OBJETO.search(t)) and bool(_ACAO.search(t))


def catalogo(chat_id: str, n: int = 30) -> list:
    try:
        linhas = db.executar(
            """
            SELECT imagem_id, origem, descricao, chat_id, criada_em
            FROM galeria ORDER BY criada_em DESC LIMIT %s
            """,
            (n,),
        ) or []
    except Exception as e:
        print(f"[galeria] catálogo: {e}")
        return []
    for l in linhas:
        l["neste_chat"] = (l.get("chat_id") == chat_id)
    return linhas


def escolher(mensagem: str, itens: list) -> list:
    """Pede ao roteador (modelo pequeno) quais imagens do catálogo o pedido quer ver."""
    try:
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:
        fuso = None

    linhas = []
    for i, it in enumerate(itens, 1):
        quando = it["criada_em"]
        quando = (quando.astimezone(fuso) if fuso else quando).strftime("%d/%m %H:%M")
        local = "neste chat" if it["neste_chat"] else "outro chat"
        linhas.append(
            f"[{i}] {it['origem']} | {quando} | {local} | {it['descricao'] or 'sem descrição'}"
        )

    instrucao = (
        "Tarefa técnica. Abaixo há o catálogo de imagens que o usuário já enviou ou que "
        "foram geradas, da MAIS RECENTE para a mais antiga. Escolha as imagens que o pedido "
        f"quer ver, comparar ou rever (de 1 a {MAX_ESCOLHIDAS}).\n"
        'Responda SOMENTE com JSON: {"indices": [1, 2]}\n'
        "- 'as duas imagens' ou 'compare as imagens', sem outras pistas: as 2 mais recentes "
        "DESTE chat.\n"
        "- Use a descrição e a data para achar imagens antigas ('a foto do gato', 'a de ontem').\n"
        '- Se o pedido for uma pergunta geral sobre imagens, sem se referir a nenhuma do '
        'catálogo, responda {"indices": []}.\n\n'
        "CATÁLOGO:\n" + "\n".join(linhas) + f"\n\nPedido: {mensagem}"
    )

    try:
        texto = perguntar_llm(
            instrucao, "(tarefa técnica, sem cumprimentos)", leve=True, tarefa="roteador"
        )
    except ErroLLM as e:
        print(f"[galeria] escolher: {e}")
        return []

    achado = re.search(r"\{.*\}", texto or "", re.DOTALL)
    if not achado:
        return []
    try:
        indices = json.loads(achado.group(0)).get("indices", [])
    except (ValueError, AttributeError):
        return []

    escolhidas, vistos = [], set()
    for i in indices if isinstance(indices, list) else []:
        if isinstance(i, int) and 1 <= i <= len(itens) and i not in vistos:
            vistos.add(i)
            escolhidas.append(itens[i - 1])
    return escolhidas[:MAX_ESCOLHIDAS]


def como_data_url(imagem_id: str, lado: int = LADO_ANALISE):
    """JPEG reduzido em data URL, pronto para o modelo de visão."""
    try:
        dados = _bytes(imagem_id)
        if not dados:
            return None
        img = Image.open(io.BytesIO(dados))
        img.load()
        img = img.convert("RGB")
        img.thumbnail((lado, lado))
        saida = io.BytesIO()
        img.save(saida, "JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(saida.getvalue()).decode()
    except Exception as e:
        print(f"[galeria] data URL de {imagem_id}: {e}")
        return None