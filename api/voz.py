# api/voz.py — Modo conversa: ponte navegador <-> Gemini Live
import asyncio
import json
import os
import re
import secrets
import unicodedata

from fastapi import APIRouter, WebSocket
from google import genai
from google.genai import types

from core import live, llm
from core.brain import brain
from core.filtro_segredos import detectar_segredos
from core import usage_servicos

router = APIRouter()

MAX_SESSOES = 1              # protege a cota gratuita
MAX_CHUNK_BYTES = 64_000
MAX_HISTORICO_CHARS = 3000

# Timers: só vivem enquanto esta conversa por voz estiver aberta.
MAX_TIMERS = 5
TIMER_MIN_S = 1
TIMER_MAX_S = 7200           # 2 horas
MAX_ROTULO_CHARS = 60

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


def _limpar_rotulo(valor) -> str:
    """O rótulo vai dentro de um texto enviado ao modelo: sem quebras nem colchetes."""
    texto = re.sub(r"[\r\n\[\]]+", " ", str(valor or "")).strip()
    return texto[:MAX_ROTULO_CHARS] or "timer"


def _norm(texto) -> str:
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    texto = texto.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _frase_dono() -> str:
    return _norm(os.getenv("PYXIE_FRASE_DONO"))


def _eh_dono(sessao) -> bool:
    return not _frase_dono() or getattr(sessao, "dono", False)


def _tempo_falado(segundos: int) -> str:
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    partes = []
    if h:
        partes.append(f"{h} hora" + ("s" if h > 1 else ""))
    if m:
        partes.append(f"{m} minuto" + ("s" if m > 1 else ""))
    if s:
        partes.append(f"{s} segundo" + ("s" if s > 1 else ""))
    return " e ".join(partes) or "0 segundo"


async def _timer(ws: WebSocket, estado: dict, segundos: int, rotulo: str):
    """Espera e avisa. Se a conversa já tiver fechado, falha em silêncio."""
    await asyncio.sleep(segundos)
    print(f"[voz] timer terminou: {rotulo!r}")
    try:
        await ws.send_json({"tipo": "timer", "rotulo": rotulo})
        await estado["live"].send_realtime_input(
            text=(
                f"[sistema] O timer '{rotulo}' terminou. "
                "Avise o usuário agora, em uma frase curta."
            )
        )
    except Exception as e:
        print(f"[voz] não consegui avisar do timer: {e!r}")


def _criar_timer(ws, estado: dict, timers: set, args: dict) -> str:
    """Valida os argumentos e agenda. Devolve o texto que vai ao modelo."""
    try:
        segundos = int(float(args.get("segundos", 0)))
    except (TypeError, ValueError):
        return "Não entendi a duração do timer."

    if segundos < TIMER_MIN_S or segundos > TIMER_MAX_S:
        return "Só consigo timers entre 1 segundo e 2 horas."

    timers.difference_update({t for t in timers if t.done()})
    if len(timers) >= MAX_TIMERS:
        return "Já existem timers demais ativos."

    rotulo = _limpar_rotulo(args.get("rotulo"))
    tarefa = asyncio.create_task(_timer(ws, estado, segundos, rotulo))
    timers.add(tarefa)

    print(f"[voz] timer definido: {segundos}s ({rotulo!r})")
    return f"Timer '{rotulo}' definido para {_tempo_falado(segundos)}."


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


async def _executar_ferramenta(fc, ws, estado: dict, chat_id: str, timers: set):
    """Roda UMA chamada de ferramenta. Devolve (texto, passou_pelo_brain)."""
    args = fc.args or {}

    if fc.name == "hora_atual":
        return live.hora_atual_texto(), False

    if fc.name == "definir_timer":
        return _criar_timer(ws, estado, timers, args), False

    if fc.name == "perguntar_pyxie":
        pedido = str(args.get("texto", "")).strip()
        if not pedido:
            return "Não entendi o pedido.", False
        try:
            resultado = await asyncio.to_thread(_chamar_brain, pedido, chat_id)
        except Exception as e:
            print(f"[voz] erro no brain: {e}")
            resultado = "Não consegui processar isso agora."
        return resultado, True

    print(f"[voz] ferramenta desconhecida: {fc.name!r}")
    return "Essa ferramenta não existe.", False


async def _da_live(ws: WebSocket, estado: dict, sessao, chat_id: str, timers: set):
    """Live -> navegador. Devolve "promover" quando a frase do dono for dita."""
    sessao_live = estado["live"]
    frase = _frase_dono()
    fala_usuario, fala_pyxie = "", ""
    usou_brain = False   # o brain já grava o turno na STM; nos outros casos gravamos aqui
    ultimo_total = 0     # acumulado da sessão; zera sozinho quando a Live reconecta

    while True:                              # receive() para a cada turno
        async for msg in sessao_live.receive():
            
            um = getattr(msg, "usage_metadata", None)
            if um:
                total = getattr(um, "total_token_count", None)
                if isinstance(total, int) and total > 0:
                    delta = total - ultimo_total
                    ultimo_total = total   # se o total cair (janela deslizante), só vira a nova base
                    if delta > 0:
                        try:
                            await asyncio.to_thread(
                                usage_servicos.registrar, "gemini_live", delta
                            )
                        except Exception as e:
                            print(f"[voz] não consegui registrar o uso: {e!r}")
                    f"total={getattr(um, 'total_token_count', None)} "
                    f"entrada={getattr(um, 'prompt_token_count', None)} "
                    f"saida={getattr(um, 'response_token_count', None)}"
            
            if msg.data:
                await ws.send_bytes(msg.data)

            if msg.tool_call:
                await ws.send_json({"tipo": "pensando"})
                respostas = []

                for fc in msg.tool_call.function_calls:
                    resultado, do_brain = await _executar_ferramenta(
                        fc, ws, estado, chat_id, timers
                    )
                    usou_brain = usou_brain or do_brain
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

                if frase and not _eh_dono(sessao) and frase in _norm(fala_usuario):
                    sessao.dono = True
                    print("[voz] dono reconhecido pela frase")
                    await ws.send_json(
                        {"tipo": "legenda", "quem": "voce", "texto": ""}
                    )
                    await ws.send_json({"tipo": "interrompido"})
                    return "promover"

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
                if not usou_brain:
                    _gravar_turno(sessao, fala_usuario, fala_pyxie)
                fala_usuario, fala_pyxie, usou_brain = "", "", False
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

    timers: set = set()
    estado = {"live": None}
    saudar = False

    _ativas += 1
    try:
        client = genai.Client(api_key=chave)

        while True:
            config = live.montar_config(
                historico=_historico(sessao),
                com_ferramenta=True,
                dono=_eh_dono(sessao),
            )
            reconectar = False

            async with client.aio.live.connect(
                model=live.LIVE_MODEL, config=config
            ) as sessao_live:
                estado["live"] = sessao_live
                await ws.send_json({"tipo": "pronto"})

                if saudar:
                    saudar = False
                    await sessao_live.send_realtime_input(
                        text=(
                            "[sistema] O usuário foi reconhecido como o Guilherme. "
                            "Cumprimente-o em uma frase curta."
                        )
                    )

                t_nav = asyncio.create_task(_do_navegador(ws, sessao_live))
                t_live = asyncio.create_task(
                    _da_live(ws, estado, sessao, chat_id, timers)
                )
                _, pendentes = await asyncio.wait(
                    [t_nav, t_live], return_when=asyncio.FIRST_COMPLETED
                )
                for t in pendentes:
                    t.cancel()
                await asyncio.gather(*pendentes, return_exceptions=True)

                for t in (t_nav, t_live):
                    if t.done() and not t.cancelled() and t.exception():
                        print(f"[voz] encerrada: {t.exception()!r}")

                if (
                    t_live.done()
                    and not t_live.cancelled()
                    and t_live.exception() is None
                    and t_live.result() == "promover"
                ):
                    reconectar = True
                    saudar = True

            if not reconectar:
                break
    except Exception as e:
        print(f"[voz] erro: {e!r}")
    finally:
        _ativas -= 1

        # Timers não sobrevivem à conversa.
        for t in timers:
            t.cancel()
        if timers:
            await asyncio.gather(*timers, return_exceptions=True)

        try:
            # O front reabre a conexão; o histórico volta da STM.
            await ws.send_json({"tipo": "encerrada"})
            await ws.close()
        except Exception:
            pass