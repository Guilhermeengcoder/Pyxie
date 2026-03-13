from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class NLPIntent:

    def __init__(self):

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.intents = {

            "hora": [
                "que horas são",
                "qual é o horário",
                "me diga a hora"
            ],

            "saudacao": [
                "oi",
                "olá",
                "bom dia",
                "boa tarde"
            ],

            "identidade": [
                "quem é você",
                "qual seu nome",
                "quem te criou"
            ],

            "calculo": [
                "quanto é",
                "calcule",
                "faça essa conta"
            ],

            "pesquisa": [
                "pesquise",
                "procure na internet",
                "busque informação"
            ],

            "memoria": [
                "lembre se que",
                "lembra de",
                "recorde que",
                "guarde na memoria que",
                "memorize que"
            ]
        }

        self.intent_vectors = {}

        for intent, frases in self.intents.items():
            self.intent_vectors[intent] = self.model.encode(frases)

    def detectar(self, pergunta):

        pergunta_vec = self.model.encode(pergunta)

        melhor_intent = None
        melhor_score = 0

        for intent, vectors in self.intent_vectors.items():

            score = cosine_similarity([pergunta_vec], vectors).max()

            if score > melhor_score:
                melhor_score = score
                melhor_intent = intent

        if melhor_score > 0.7:
            return melhor_intent

        return "desconhecido"