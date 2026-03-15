import difflib


class SpellCorrector:

    def __init__(self):

        # dicionário básico inicial
        self.dictionary = [

            "quem",
            "quando",
            "onde",
            "como",
            "por",
            "que",
            "porque",
            "o",
            "que",
            "qual",
            "quantos",
            "quantas",
            "anos",
            "idade",
            "altura",
            "peso",
            "nasceu",
            "nascer",
            "capital",
            "pais",
            "cidade",
            "historia",

            "oi",
            "ola",
            "opa",
            "eai",
            "fala",

            "bom",
            "dia",
            "boa",
            "tarde",
            "noite",

            "pesquise",
            "procure",
            "internet",

            "calcule",
            "quanto",
            "hora",
            "horas",

            "pyxie"
        ]

    def corrigir_palavra(self, palavra):

        if palavra in self.dictionary:
            return palavra

        sugestoes = difflib.get_close_matches(
            palavra,
            self.dictionary,
            n=1,
            cutoff=0.75
        )

        if sugestoes:
            return sugestoes[0]

        return palavra

    def corrigir_frase(self, frase):

        palavras = frase.split()

        corrigidas = []

        for palavra in palavras:
            corrigidas.append(self.corrigir_palavra(palavra))

        return " ".join(corrigidas)