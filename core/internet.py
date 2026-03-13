import requests
from core.language import traduzir_para_ingles, traduzir_para_portugues


def buscar_web(pergunta):

    pergunta_en = traduzir_para_ingles(pergunta)

    # =========================
    # BUSCA WIKIPEDIA
    # =========================

    try:

        search_url = "https://pt.wikipedia.org/w/api.php"

        params = {
            "action": "query",
            "list": "search",
            "srsearch": pergunta_en,
            "format": "json"
        }

        r = requests.get(search_url, params=params)

        data = r.json()

        if data["query"]["search"]:

            titulo = data["query"]["search"][0]["title"]

            summary_url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{titulo}"

            r2 = requests.get(summary_url)

            data2 = r2.json()

            if data2.get("extract"):
                return traduzir_para_portugues(data2["extract"])

    except Exception as e:
        print("Erro Wikipedia:", e)

    # =========================
    # DUCKDUCKGO (fallback)
    # =========================

    try:

        url = "https://api.duckduckgo.com/"

        params = {
            "q": pergunta_en,
            "format": "json",
            "no_html": 1
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            return None

        data = response.json()

        if data.get("AbstractText"):
            return traduzir_para_portugues(data["AbstractText"])

        if data.get("Definition"):
            return traduzir_para_portugues(data["Definition"])

    except Exception as e:
        print("Erro DuckDuckGo:", e)

    return None