import re

def extrair_info(pergunta, texto):

    pergunta = pergunta.lower()
    texto = texto.lower()

    # idade
    if "quantos anos" in pergunta:

        match = re.search(r'(\d{1,3})\s+years', texto)

        if match:
            return f"Tem aproximadamente {match.group(1)} anos."

    # nascimento
    if "quando nasceu" in pergunta:

        match = re.search(r'born\s+(.*?\d{4})', texto)

        if match:
            return f"Nasceu em {match.group(1)}."

    return None