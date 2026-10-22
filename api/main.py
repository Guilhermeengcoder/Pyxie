import os
import secrets
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException


from fastapi.responses import FileResponse
from core import cloudflare_imagem
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.brain import brain
from core import usage
from core import usage_gemini
from core import llm
from core import llm_config
from core import usage_servicos

# Sem /docs nem /openapi.json públicos: não mostram o mapa da API a estranhos.
app = FastAPI(
    title="PYXIE API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def exigir_token(x_pyxie_token: Optional[str] = Header(default=None)):
    """Exige o header X-Pyxie-Token igual a PYXIE_TOKEN.

    O token é lido a cada chamada (não no import). Sem PYXIE_TOKEN no
    servidor, tudo é recusado: melhor travado do que aberto por esquecimento.
    """
    esperado = (os.getenv("PYXIE_TOKEN") or "").strip()

    if not esperado:
        raise HTTPException(
            status_code=503,
            detail="PYXIE_TOKEN não configurado no servidor.",
        )

    enviado = (x_pyxie_token or "").strip()

    # compare_digest evita vazar o token por tempo de resposta;
    # encode() evita erro com caracteres não ASCII.
    if not secrets.compare_digest(enviado.encode(), esperado.encode()):
        raise HTTPException(status_code=401, detail="Token inválido ou ausente.")

# ~4,5 MB de imagem em base64. O front-end já reduz a foto antes de enviar
# (lado máximo de 1280px), então isso só protege contra abuso.
MAX_IMAGEM_CHARS = 6_000_000


class MensagemHistorico(BaseModel):
    role: str       # "user" ou "assistant"
    content: str


class Pergunta(BaseModel):
    mensagem: str = ""
    chat_id: str = "default"
    # O front-end ainda envia isso; por enquanto o brain não usa.
    historico: Optional[List[MensagemHistorico]] = None
    imagem: Optional[str] = None


class NovoModo(BaseModel):
    modo: Literal["groq", "gemini", "auto"]


def _uso_atual() -> dict:
    """Uso do provedor que o painel deve mostrar (com 'provedor' e 'modo')."""
    provedor = llm.provedor_do_painel()

    if provedor == "gemini":
        dados = usage_gemini.obter()
    else:
        dados = usage.ultimo()

    dados["provedor"] = provedor
    dados["modo"] = llm_config.obter_modo()
    return dados


# IMPORTANTE: estes endpoints são "def" (não "async def") de propósito.
# O rastreio do provedor é por thread; a requisição inteira precisa
# rodar na mesma thread.
@app.post("/perguntar", dependencies=[Depends(exigir_token)])
def perguntar(pergunta: Pergunta):

    llm.iniciar_rastreio()
    
    sessao = brain.sessions.get(pergunta.chat_id)
    sessao.imagem_pendente = None

    if pergunta.imagem:
        if (
            not pergunta.imagem.startswith("data:image/")
            or len(pergunta.imagem) > MAX_IMAGEM_CHARS
        ):
            raise HTTPException(status_code=400, detail="Imagem inválida ou grande demais.")

    if not pergunta.mensagem.strip() and not pergunta.imagem:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    if pergunta.imagem:
        resposta = brain.processar_imagem(
            pergunta.mensagem,
            pergunta.imagem,
            chat_id=pergunta.chat_id,
        )
    else:
        resposta = brain.process(pergunta.mensagem, chat_id=pergunta.chat_id)

    imagem_id = sessao.imagem_pendente
    sessao.imagem_pendente = None

    return {
        "resposta": resposta,
        "imagem_id": imagem_id,
        "uso": _uso_atual(),
        "aviso": llm.aviso_da_requisicao(),
    }



@app.post("/regenerar/{chat_id}", dependencies=[Depends(exigir_token)])
def regenerar_resposta(chat_id: str):
    llm.iniciar_rastreio()

    resultado = brain.regenerar(chat_id=chat_id)

    if not resultado["ok"]:
        raise HTTPException(
            status_code=400,
            detail=resultado["erro"]
        )

    return {
        "resposta": resultado["resposta"],
        "uso": _uso_atual(),
        "aviso": llm.aviso_da_requisicao(),
    }



@app.delete("/chat/{chat_id}", dependencies=[Depends(exigir_token)])
def encerrar_chat(chat_id: str):
    brain.sessions.delete(chat_id)
    return {"ok": True}


@app.get("/uso", dependencies=[Depends(exigir_token)])
def uso():
    return _uso_atual()


# ATENÇÃO: sem autenticação por enquanto (item 4 do roadmap de segurança).
# Quem tiver a URL consegue trocar o modo. Trocar para o Gemini não vaza
# memória (a trava do llm.py continua valendo), mas muda o comportamento.
@app.get("/modo", dependencies=[Depends(exigir_token)])
def ler_modo():
    return {"modo": llm_config.obter_modo(), "modos": list(llm_config.MODOS)}


@app.post("/modo", dependencies=[Depends(exigir_token)])
def trocar_modo(novo: NovoModo):
    llm_config.definir_modo(novo.modo)
    return {"modo": llm_config.obter_modo(), "modos": list(llm_config.MODOS)}


@app.get("/uso/servicos", dependencies=[Depends(exigir_token)])
def uso_servicos():
    return usage_servicos.obter_todos()

@app.get("/imagens/{imagem_id}", dependencies=[Depends(exigir_token)])
def ver_imagem(imagem_id: str):
    caminho = cloudflare_imagem.caminho_da_imagem(imagem_id)
    if not caminho:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    return FileResponse(caminho)

app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)