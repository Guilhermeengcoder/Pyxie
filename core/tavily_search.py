# =============================================================
# core/tavily_search.py — Busca na web via Tavily
#
# Falhas viram ErroCota / ErroIndisponivel / ErroLLM, como nos
# outros provedores. O brain trata qualquer uma delas caindo no
# fluxo normal, então a busca nunca derruba a conversa.
# =============================================================

import os

import requests
from dotenv import load_dotenv

from core import usage_servicos
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel

load_dotenv()

URL = "https://api.tavily.com/search"
TIMEOUT = 15
MAX_RESULTADOS = 5
MAX_CHARS_TRECHO = 700
MAX_CHARS_CONSULTA = 400


def buscar(consulta: str, profundidade: str = "basic",
           max_resultados: int = MAX_RESULTADOS):
    """
    Devolve {"resultados": [{"titulo","url","trecho"}], "creditos": int}
    ou None se a consulta for vazia.
    """
    chave = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not chave:
        raise ErroLLM("tavily", "TAVILY_API_KEY não configurada")

    consulta = (consulta or "").strip()[:MAX_CHARS_CONSULTA]
    if not consulta:
        return None

    corpo = {
        "query": consulta,
        "search_depth": profundidade,   # "basic" = 1 crédito, "advanced" = 2
        "max_results": max_resultados,
        "include_answer": False,        # quem responde é o LLM
        "include_usage": True,          # devolve os créditos gastos
    }

    try:
        r = requests.post(
            URL,
            headers={"Authorization": f"Bearer {chave}"},
            json=corpo,
            timeout=TIMEOUT,
        )
    except (requests.Timeout, requests.ConnectionError) as e:
        raise ErroIndisponivel("tavily", str(e)[:200]) from e
    except requests.RequestException as e:
        raise ErroLLM("tavily", str(e)[:200]) from e

    if r.status_code in (429, 432, 433):
        raise ErroCota("tavily", f"HTTP {r.status_code}")
    if r.status_code >= 500:
        raise ErroIndisponivel("tavily", f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ErroLLM("tavily", f"HTTP {r.status_code}: {r.text[:150]}")

    try:
        dados = r.json()
    except ValueError as e:
        raise ErroLLM("tavily", "resposta não é JSON") from e

    # Usa o valor real; se a API não informar, estima pelo tipo de busca.
    creditos = (dados.get("usage") or {}).get("credits")
    if creditos is None:
        creditos = 2 if profundidade == "advanced" else 1

    usage_servicos.registrar("tavily", creditos)

    resultados = []
    for item in dados.get("results") or []:
        trecho = (item.get("content") or "").strip()
        if not trecho:
            continue
        resultados.append({
            "titulo": (item.get("title") or "Sem título").strip(),
            "url": item.get("url") or "",
            "trecho": trecho[:MAX_CHARS_TRECHO],
        })

    return {"resultados": resultados, "creditos": creditos}


def formatar_para_prompt(resultados: list) -> str:
    """Bloco de texto numerado para o LLM usar como fonte."""
    return "\n\n".join(
        f"[{i}] {r['titulo']}\n{r['url']}\n{r['trecho']}"
        for i, r in enumerate(resultados, 1)
    )