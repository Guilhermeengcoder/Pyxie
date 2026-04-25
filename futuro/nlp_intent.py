from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class NLPIntent:

    def __init__(self):

        # 🔥 Modelo leve e eficiente
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.intents = {

            "hora": [
                "que horas são",
                "qual é o horário",
                "me diga a hora",
                "pode me informar o horário atual"
            ],

            "saudacao": [
                "oi",
                "olá",
                "bom dia",
                "boa tarde",
                "boa noite",
                "eai",
                "fala"
            ],

            "identidade": [
                "quem é você",
                "qual seu nome",
                "quem te criou",
                "o que você é",
                "se apresente"
            ],

            "calculo": [
                "quanto é",
                "calcule",
                "faça essa conta",
                "resolve essa conta",
                "me diga o resultado"
            ],

            "pesquisa": [
                "pesquise",
                "procure na internet",
                "busque informação",
                "quero saber sobre",
                "me fale sobre",
                "oque é",
                "oq é",
                "o que significa",
                "me explica",
                "explique",
                "defina"
            ],

            "memoria": [
                "lembre se que",
                "lembra de",
                "recorde que",
                "guarde na memoria que",
                "memorize que"
            ]
        }

        # 🔥 Pré-cálculo otimizado
        self.intent_vectors = {
            intent: self.model.encode(frases)
            for intent, frases in self.intents.items()
        }

    def detectar(self, pergunta):

        pergunta_vec = self.model.encode(pergunta)

        melhor_intent = None
        melhor_score = 0

        for intent, vectors in self.intent_vectors.items():

            scores = cosine_similarity([pergunta_vec], vectors)[0]
            score = np.max(scores)

            if score > melhor_score:
                melhor_score = score
                melhor_intent = intent

    # 🔥 Threshold inteligente
        if melhor_score >= 0.65:
            return melhor_intent

    # 🔥 fallback manual
        pergunta_lower = pergunta.lower()

        if "hora" in pergunta_lower or "dia" in pergunta_lower or "data" in pergunta_lower:
            return "hora"

        return None