INTENTS = {

    "pesquisa": [
        "quem é",
        "quem foi",
        "o que é",
        "o que foi",
        "me fale sobre",
        "fale sobre",
        "pesquise",
        "procure"
    ],

    "idade": [
        "quantos anos",
        "idade"
    ]

}


def detectar_intencao(msg):

    msg = msg.lower()

    for intent, patterns in INTENTS.items():
        for p in patterns:
            if p in msg:
                return intent

    return None