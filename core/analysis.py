import re
from datetime import datetime

def extrair_idade(texto):

    padroes = [
        r"nasceu em (\d{4})",
        r"nascido em (\d{4})"
    ]

    for p in padroes:

        match = re.search(p, texto.lower())

        if match:

            ano = int(match.group(1))

            idade = datetime.now().year - ano

            return idade

    return None