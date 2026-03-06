import requests

def buscar_web(pergunta):

    url = "https://api.duckduckgo.com/"

    params = {
        "q": pergunta,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        # resposta principal
        if data.get("AbstractText"):
            return data["AbstractText"]

        # respostas relacionadas
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"]:
                if isinstance(topic, dict) and topic.get("Text"):
                    return topic["Text"]

    except Exception as e:
        print("Erro na busca:", e)
        return None

    return None