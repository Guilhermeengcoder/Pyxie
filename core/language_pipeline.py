import unicodedata


class LanguagePipeline:

    def __init__(self):

        # =========================
        # STOPWORDS (artigos/preposições)
        # =========================

        self.stopwords = {
            "o","a","os","as",
            "um","uma","uns","umas",
            "de","do","da","dos","das",
            "em","no","na","nos","nas",
            "para","por","com",
            "e","ou","mas"
        }

        # =========================
        # ERROS COMUNS
        # =========================

        self.correcoes = {
            "qantos": "quantos",
            "qanto": "quanto",
            "qntos": "quantos",
            "qntas": "quantas",
            "oque": "o que",
            "pq": "por que",
            "tb": "tambem",
            "vc": "voce",
            "vcs": "voces"
        }

    # =========================
    # NORMALIZAÇÃO
    # =========================

    def normalizar(self, texto):

        texto = texto.lower()

        texto = unicodedata.normalize("NFD", texto)
        texto = texto.encode("ascii", "ignore").decode("utf-8")

        return texto

    # =========================
    # CORREÇÃO ORTOGRÁFICA
    # =========================

    def corrigir(self, texto):

        palavras = texto.split()

        palavras_corrigidas = [
            self.correcoes.get(p, p) for p in palavras
        ]

        return " ".join(palavras_corrigidas)

    # =========================
    # TOKENIZAÇÃO
    # =========================

    def tokenizar(self, texto):

        return texto.split()

    # =========================
    # REMOÇÃO DE STOPWORDS
    # =========================

    def remover_stopwords(self, tokens):

        return [
            t for t in tokens
            if t not in self.stopwords
        ]

    # =========================
    # PIPELINE COMPLETO
    # =========================

    def processar(self, texto):

        texto = self.normalizar(texto)

        texto = self.corrigir(texto)

        tokens = self.tokenizar(texto)

        tokens = self.remover_stopwords(tokens)

        return tokens


# =========================
# INSTÂNCIA GLOBAL
# =========================

pipeline = LanguagePipeline()