import requests
import urllib.parse
from core.language_pipeline import pipeline
from core.language import traduzir_para_ingles, traduzir_para_portugues


def buscar_duckduckgo(query):

    try:
        url = "https://api.duckduckgo.com/"

        params = {
            "q": query,
            "format": "json",
            "lang": "en"
        }

        r = requests.get(url, params=params, timeout=5)

        if r.status_code != 200:
            return None

        data = r.json()

        if data.get("AbstractText"):
            return data["AbstractText"]

        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"]:
                if isinstance(topic, dict) and topic.get("Text"):
                    return topic["Text"]

    except:
        return None

    return None


def buscar_wikipedia(pergunta_en, headers):

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
            return None

        data = r.json()

        if data.get("query") and data["query"].get("search"):

            titulo = data["query"]["search"][0]["title"]
            titulo_url = urllib.parse.quote(titulo)

            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{titulo_url}"

            r2 = requests.get(summary_url, headers=headers, timeout=5)

            if r2.status_code != 200:
                return None

            data2 = r2.json()

            if data2.get("extract"):
                return data2["extract"]

    except Exception as e:
        print("Erro Wikipedia:", e)

    return None


def buscar_wikipedia_opensearch(pergunta_en, headers):

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
            return None

        data = r.json()

        if len(data) >= 2 and data[1]:

            titulo = data[1][0]
            titulo_url = urllib.parse.quote(titulo)

            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{titulo_url}"

            r2 = requests.get(summary_url, headers=headers, timeout=5)

            if r2.status_code != 200:
                return None

            data2 = r2.json()

            if data2.get("extract"):
                return data2["extract"]

    except Exception as e:
        print("Erro Wikipedia OpenSearch:", e)

    return None


# 🔥 FUNÇÃO PRINCIPAL MELHORADA
def buscar_web(pergunta):

    headers = {
        "User-Agent": "PYXIE-AI/3.0"
    }

    # =========================
    # PIPELINE
    # =========================
    resultado_pipeline = pipeline.processar(pergunta)
    pergunta = resultado_pipeline["corrigido"]  # ✅ pega a string corrigido 

    pergunta_en = traduzir_para_ingles(pergunta)

    # =========================
    # 1. WIKIPEDIA (PRINCIPAL)
    # =========================
    resultado = buscar_wikipedia(pergunta_en, headers)

    if resultado:
        return traduzir_para_portugues(resultado)

    # =========================
    # 2. WIKIPEDIA OPENSEARCH
    # =========================
    resultado = buscar_wikipedia_opensearch(pergunta_en, headers)

    if resultado:
        return traduzir_para_portugues(resultado)

    # =========================
    # 3. DUCKDUCKGO (FALLBACK)
    # =========================
    resultado = buscar_duckduckgo(pergunta_en)

    if resultado:
        return traduzir_para_portugues(resultado)

    # =========================
    # 4. TENTATIVA FINAL (SEM TRADUÇÃO)
    # =========================
    resultado = buscar_duckduckgo(pergunta)

    if resultado:
        return resultado

    return None