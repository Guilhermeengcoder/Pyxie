import unicodedata
from deep_translator import GoogleTranslator


def limpar_texto(texto):

    texto = texto.lower()

    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    texto = texto.replace("?", "")
    texto = texto.replace("!", "")
    texto = texto.replace(".", "")

    return texto


def traduzir_para_ingles(texto):

    try:
        if not texto:
            return texto

        texto = limpar_texto(texto)

        resultado = GoogleTranslator(source='pt', target='en').translate(texto)

        if resultado:
            return resultado

        return texto

    except:
        return texto


def traduzir_para_portugues(texto):

    try:
        if not texto:
            return texto

        resultado = GoogleTranslator(source='en', target='pt').translate(texto)

        if resultado:
            return resultado

        return texto

    except:
        return texto