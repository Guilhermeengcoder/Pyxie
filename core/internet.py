import requests
from core.language import traduzir_para_ingles, traduzir_para_portugues

def buscar_web(pergunta):
    # Traduzir pergunta para inglês
    pergunta_en = traduzir_para_ingles(pergunta)

    url = "https://api.duckduckgo.com/"
    params = {
        "q": pergunta_en,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        resposta = None

        if data.get("Answer"):
            resposta = data["Answer"]
        elif data.get("Definition"):
            resposta = data["Definition"]
        elif data.get("AbstractText"):
            resposta = data["AbstractText"]
        elif data.get("RelatedTopics"):
            for topic in data["RelatedTopics"]:
                if isinstance(topic, dict) and topic.get("Text"):
                    resposta = topic["Text"]
                    break

        if resposta:
            return traduzir_para_portugues(resposta)

    except Exception as e:
        print("Erro na busca DuckDuckGo:", e)

    # Fallback: Wikipedia
    try:
        wiki_url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{pergunta_en}"
        r = requests.get(wiki_url)
        wdata = r.json()

        if wdata.get("extract"):
            return traduzir_para_portugues(wdata["extract"])

    except Exception as e:
        print("Erro na busca Wikipedia:", e)

    return None