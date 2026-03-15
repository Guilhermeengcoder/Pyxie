import requests
import urllib.parse
from core.language_pipeline import pipeline
from core.language import traduzir_para_ingles, traduzir_para_portugues


def buscar_web(pergunta):

    headers = {
        "User-Agent": "PYXIE-AI/1.0"
    }

    tokens = pipeline.processar(pergunta)
    pergunta = " ".join(tokens)

    pergunta_en = traduzir_para_ingles(pergunta)

    # =========================
    # BUSCA WIKIPEDIA (API)
    # =========================

    try:

        search_url = "https://en.wikipedia.org/w/api.php"

        params = {
            "action": "query",
            "list": "search",
            "srsearch": pergunta_en,
            "format": "json"
        }

        r = requests.get(search_url, params=params, headers=headers, timeout=5)

        if r.status_code != 200:
            raise Exception(f"Status {r.status_code}")

        data = r.json()

        if data.get("query") and data["query"].get("search"):

            titulo = data["query"]["search"][0]["title"]

            titulo_url = urllib.parse.quote(titulo)

            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{titulo_url}"

            r2 = requests.get(summary_url, headers=headers, timeout=5)

            if r2.status_code != 200:
                raise Exception(f"Resumo status {r2.status_code}")

            data2 = r2.json()

            if data2.get("extract"):

                resposta = data2["extract"]

                return traduzir_para_portugues(resposta)

    except Exception as e:
        print("Erro Wikipedia:", e)

    # =========================
    # WIKIPEDIA OPENSEARCH (fallback)
    # =========================

    try:

        opensearch_url = "https://en.wikipedia.org/w/api.php"

        params = {
            "action": "opensearch",
            "search": pergunta_en,
            "limit": 1,
            "namespace": 0,
            "format": "json"
        }

        r = requests.get(opensearch_url, params=params, headers=headers, timeout=5)

        if r.status_code != 200:
            raise Exception(f"Status {r.status_code}")

        data = r.json()

        if len(data) >= 2 and data[1]:

            titulo = data[1][0]

            titulo_url = urllib.parse.quote(titulo)

            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{titulo_url}"

            r2 = requests.get(summary_url, headers=headers, timeout=5)

            if r2.status_code != 200:
                raise Exception(f"Resumo status {r2.status_code}")

            data2 = r2.json()

            if data2.get("extract"):

                resposta = data2["extract"]

                return traduzir_para_portugues(resposta)

    except Exception as e:
        print("Erro Wikipedia OpenSearch:", e)

    return None