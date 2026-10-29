# api/voz.py — Modo conversa: ponte navegador <-> Gemini Live
import asyncio
import json
import os
import secrets

from fastapi import APIRouter, WebSocket
from google import genai
from google.genai import types

from core import live, llm
from core.brain import brain
from core.filtro_segredos import detectar_segredos

router = APIRouter()

MAX_SESSOES = 1              # protege a cota gratuita
MAX_CHUNK_BYTES = 64_000
MAX_HISTORICO_CHARS = 3000
_ativas = 0


def _token_ok(enviado) -> bool:
    esperado = (os.getenv("PYXIE_TOKEN") or "").strip()
    if not esperado:
        return False
    return secrets.compare_digest(str(enviado or "").strip().encode(), esperado.encode())


def _historico(sessao) -> str:
    """Conversa recente da STM, no formato que vai na instrução da Live."""
    linhas = []
    for m in sessao.stm.get_context_seletivo(excluir_ultima=False):
        if m["role"] == "user":
            linhas.append(f"Usuário: {m['content']}\n")
        elif m["role"] == "assistant":
            linhas.append(f"PYXIE: {m['content']}\n")

    escolhidas, total = [], 0
    for linha in reversed(linhas):
        total += len(linha)
        if total > MAX_HISTORICO_CHARS:
            break
        escolhidas.append(linha)
    texto = "".join(reversed(escolhidas))

    # Mesmo filtro dos provedores sem confiança: nada de senha ou chave.
    return "" if detectar_segredos(texto) else texto


def _chamar_brain(pedido: str, chat_id: str) -> str:
    llm.iniciar_rastreio()          # o rastreio é por thread
    return brain.process_voz(pedido, chat_id=chat_id)

def _chamar_brain(pedido: str, chat_id: str) -> str:
    print(f"[voz] ferramenta chamada: {pedido!r}")
    llm.iniciar_rastreio()          # o rastreio é por thread
    return brain.process_voz(pedido, chat_id=chat_id)


def _gravar_turno(sessao, fala_usuario: str, fala_pyxie: str):
    """Grava na STM um turno que a Live respondeu sozinha."""
    u, p = fala_usuario.strip(), fala_pyxie.strip()
    if not u or not p:
        return
    sessao.stm.add_message("user", u)
    sessao.stm.add_message("assistant", p)
    sessao.ultima_pergunta = u
    sessao.regeneracao_pergunta = None   # o botão "regenerar" não mexe em fala


async def _do_navegador(ws: WebSocket, sessao_live):
    """Navegador -> Live: áudio (binário) e comandos (JSON)."""
    while True:
        msg = await ws.receive()
        if msg["type"] == "websocket.disconnect":
            return

        dados = msg.get("bytes")
        if dados:
            if len(dados) <= MAX_CHUNK_BYTES:
                await sessao_live.send_realtime_input(
                    audio=types.Blob(data=dados, mime_type="audio/pcm;rate=16000")
                )
            continue

        try:
            cmd = json.loads(msg.get("text") or "{}")
        except ValueError:
            continue

        if cmd.get("acao") == "fim_audio":
            await sessao_live.send_realtime_input(audio_stream_end=True)
        elif cmd.get("texto"):
            await sessao_live.send_realtime_input(text=str(cmd["texto"])[:2000])


async def _da_live(ws: WebSocket, sessao_live, sessao, chat_id: str):
    """Live -> navegador: áudio, legendas, ferramenta e gravação na STM."""
    fala_usuario, fala_pyxie = "", ""
    usou_ferramenta = False

    while True:                              # receive() para a cada turno
        async for msg in sessao_live.receive():
            if msg.data:
                await ws.send_bytes(msg.data)

            if msg.tool_call:
                usou_ferramenta = True
                await ws.send_json({"tipo": "pensando"})
                respostas = []
                
                respostas = []
                for fc in msg.tool_call.function_calls:
                    pedido = str((fc.args or {}).get("texto", "")).strip()
                    try:
                        resultado = (
                            await asyncio.to_thread(_chamar_brain, pedido, chat_id)
                            if pedido else "Não entendi o pedido."
                        )
                    except Exception as e:
                        print(f"[voz] erro no brain: {e}")
                        resultado = "Não consegui processar isso agora."
                    respostas.append(types.FunctionResponse(
                        id=fc.id, name=fc.name, response={"resultado": resultado}
                    ))
                await sessao_live.send_tool_response(function_responses=respostas)
                continue

            sc = msg.server_content
            if not sc:
                continue

            if sc.input_transcription and sc.input_transcription.text:
                fala_usuario += sc.input_transcription.text
                await ws.send_json(
                    {"tipo": "legenda", "quem": "voce", "texto": fala_usuario}
                )

            if sc.output_transcription and sc.output_transcription.text:
                fala_pyxie += sc.output_transcription.text
                await ws.send_json(
                    {"tipo": "legenda", "quem": "pyxie", "texto": fala_pyxie}
                )

            if sc.interrupted:               # o usuário falou por cima
                fala_pyxie = ""
                await ws.send_json({"tipo": "interrompido"})

            if sc.turn_complete:
                if not usou_ferramenta:
                    _gravar_turno(sessao, fala_usuario, fala_pyxie)
                fala_usuario, fala_pyxie, usou_ferramenta = "", "", False
                await ws.send_json({"tipo": "fim_turno"})


@router.websocket("/ws/voz")
async def voz(ws: WebSocket):
    global _ativas
    await ws.accept()

    # 1) Autenticação: primeira mensagem {"token": "...", "chat_id": "..."}
    try:
        inicio = json.loads(await asyncio.wait_for(ws.receive_text(), 10))
    except Exception:
        await ws.close(code=1008)
        return

    if not _token_ok(inicio.get("token")):
        await ws.close(code=1008, reason="Token inválido.")
        return
    if not live.LIVE_ATIVO:
        await ws.close(code=1008, reason="Modo conversa desativado.")
        return

    chave = os.getenv("GEMINI_API_KEY")
    if not chave:
        await ws.close(code=1011, reason="Chave do Gemini ausente.")
        return
    if _ativas >= MAX_SESSOES:
        await ws.close(code=1013, reason="Já existe uma conversa por voz ativa.")
        return

    chat_id = str(inicio.get("chat_id") or "default")
    sessao = brain.sessions.get(chat_id)

    _ativas += 1
    try:
        client = genai.Client(api_key=chave)
        config = live.montar_config(historico=_historico(sessao), com_ferramenta=True)

        async with client.aio.live.connect(
            model=live.LIVE_MODEL, config=config
        ) as sessao_live:
            await ws.send_json({"tipo": "pronto"})

            tarefas = [
                asyncio.create_task(_do_navegador(ws, sessao_live)),
                asyncio.create_task(_da_live(ws, sessao_live, sessao, chat_id)),
            ]
            _, pendentes = await asyncio.wait(
                tarefas, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pendentes:
                t.cancel()
            await asyncio.gather(*pendentes, return_exceptions=True)

            for t in tarefas:
                if t.done() and not t.cancelled() and t.exception():
                    print(f"[voz] encerrada: {t.exception()!r}")
    except Exception as e:
        print(f"[voz] erro: {e!r}")
    finally:
        _ativas -= 1
        try:
            # O front reabre a conexão; o histórico volta da STM.
            await ws.send_json({"tipo": "encerrada"})
            await ws.close()
        except Exception:
            pass
        
def _chamar_brain(pedido: str, chat_id: str) -> str:
    print(f"[voz] ferramenta chamada: {pedido!r}")
    llm.iniciar_rastreio()
    return brain.process_voz(pedido, chat_id=chat_id)

