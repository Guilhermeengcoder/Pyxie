# =============================================================
# agente_local.py — roda NO SEU PC, não no Render.
#   python agente_local.py      (na raiz do projeto, com o .env)
#
# Busca pedidos na fila do Redis e abre só programas da lista
# permitida (core/acoes.py). Ctrl+C para parar.
# =============================================================

import json
import os
import sys
import time

from core import memory_json
from core import acoes
from modules.launcher import Module

INTERVALO_S = max(2.0, float(os.getenv("AGENTE_INTERVALO_S", "5")))
BATIDA_S = 30          # de quanto em quanto tempo diz "estou vivo"

launcher = Module()


def processar(bruto: str):
    try:
        item = json.loads(bruto)
        acao_id = str(item["id"])[:16]
    except (ValueError, KeyError, TypeError):
        print(f"[agente] item inválido ignorado: {str(bruto)[:80]!r}")
        return

    def responder(texto):
        memory_json._cmd("SET", acoes.PREFIXO_RESULTADO + acao_id, texto, "EX", 60)

    if item.get("acao") != "abrir":
        responder("erro: ação não permitida")
        return

    alvo = item.get("alvo")
    if alvo not in acoes.PROGRAMAS:           # confere de novo, mesmo vindo do servidor
        responder("erro: programa não permitido")
        return

    if time.time() - float(item.get("criado", 0)) > acoes.VALIDADE_S:
        print(f"[agente] pedido velho descartado: {alvo}")
        responder("erro: o pedido expirou")
        return

    resposta = launcher._abrir(alvo)
    print(f"[agente] {alvo}: {resposta}")
    responder("ok" if str(resposta).startswith("Abrindo") else f"erro: {resposta}")


def main():
    if sys.platform != "win32":
        print("[agente] aviso: testado só pensando em Windows.")
    if not memory_json._remoto():
        raise SystemExit("Defina UPSTASH_REDIS_REST_URL e UPSTASH_REDIS_REST_TOKEN no .env.")

    print(f"[agente] ligado. Consultando a cada {INTERVALO_S:g}s. Ctrl+C para parar.")
    ultima_batida = 0.0

    while True:
        try:
            if time.time() - ultima_batida >= BATIDA_S:
                memory_json._cmd("SET", acoes.CHAVE_AGENTE, "1", "EX", 90)
                ultima_batida = time.time()

            while True:
                bruto = memory_json._cmd("RPOP", acoes.FILA)
                if bruto is None:
                    break
                processar(bruto)
        except Exception as e:
            print(f"[agente] erro: {e!r}")
        time.sleep(INTERVALO_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[agente] encerrado.")