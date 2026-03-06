import requests

def buscar_web(pergunta):

    url = "https://api.duckduckgo.com/"

    params = {
        "q": pergunta,
        "format": "json"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("Abstract"):
            return data["Abstract"]

        if data.get("RelatedTopics"):
            return data["RelatedTopics"][0]["Text"]

    except:
        return None

    return None