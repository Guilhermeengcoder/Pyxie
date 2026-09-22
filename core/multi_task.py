# =============================================================
# core/multi_task.py — Divisor de Múltiplas Tarefas
# PYXIE AI
#
# Regra principal:
#   Só divide a mensagem quando CADA pedaço for, de fato, uma
#   tarefa (começa com verbo de comando). Vírgulas e "e" dentro
#   de frases normais NÃO dividem nada.
#
# Divide:
#   "abre o chrome e pesquise o que é IA"   -> 2 tarefas
#   "abre o spotify e o chrome"             -> 2 tarefas
#   "que horas são e abre o notepad"        -> 2 tarefas
#
# NÃO divide:
#   "oi, tudo bem?"                         -> 1 tarefa
#   "eu gosto de gatos, cachorros e pássaros" -> 1 tarefa
#   "pesquise sobre gatos e cachorros"      -> 1 tarefa
# =============================================================

import re

# Separadores, do mais específico para o mais genérico
SEPARADORES = [
    r"\s+e\s+depois\s+",
    r"\s+depois\s+",
    r"\s+e\s+também\s+",
    r"\s+também\s+",
    r"\s+e\s+",
    r",\s*",
]

# Verbos de abrir — permitem reaproveitar o verbo no pedaço seguinte:
# "abre o spotify e o chrome" -> "abre o spotify", "abre o chrome"
VERBOS_ABRIR = [
    "abre", "abra", "abrir",
    "inicia", "inicie",
    "lança", "lance",
]

# Verbos que iniciam uma tarefa independente.
# (Palavras interrogativas como "como", "qual", "quem" ficam de FORA
#  de propósito: "oi, como vai?" não é duas tarefas.)
VERBOS_ACAO = VERBOS_ABRIR + [
    "pesquise", "procure", "busque",
    "calcule", "calcula",
    "me diga", "me fale", "me diz",
    "me explique", "explique",
    "mostra", "mostre",
]

# Pedidos curtos que também contam como tarefa
COMANDOS_CURTOS = [
    "que horas", "que dia", "que data",
    "qual a hora", "qual o horário", "qual a data",
]


def _comeca_com(trecho: str, frases: list[str]) -> str | None:
    """Retorna a frase (palavra inteira) com que o trecho começa, ou None."""
    trecho = trecho.strip().lower()
    for frase in frases:
        if trecho == frase or trecho.startswith(frase + " "):
            return frase
    return None


def _e_tarefa(trecho: str) -> bool:
    """Um trecho só é tarefa se começar com verbo de ação ou comando curto."""
    return _comeca_com(trecho, VERBOS_ACAO + COMANDOS_CURTOS) is not None


def dividir_tarefas(mensagem: str) -> list[str]:
    """
    Divide uma mensagem em subtarefas.
    Retorna lista com 1 item se a mensagem não for composta.
    """
    msg = mensagem.strip()

    for sep in SEPARADORES:
        partes = [
            p.strip()
            for p in re.split(sep, msg, flags=re.IGNORECASE)
            if p.strip()
        ]

        if len(partes) < 2:
            continue

        tarefas = []
        verbo_abrir = None   # último verbo de "abrir" visto
        valido = True

        for i, parte in enumerate(partes):
            if _e_tarefa(parte):
                tarefas.append(parte)
                verbo_abrir = _comeca_com(parte, VERBOS_ABRIR)

            elif i > 0 and verbo_abrir and len(parte.split()) <= 4:
                # complemento curto: "abre o spotify e [o chrome]"
                tarefas.append(f"{verbo_abrir} {parte}")

            else:
                # pedaço que não é tarefa -> a vírgula/"e" era da frase
                valido = False
                break

        if valido:
            # Divide de novo cada tarefa (ex.: "abre A, B e C")
            resultado = []
            for t in tarefas:
                resultado.extend(dividir_tarefas(t))
            return resultado

    return [msg]


def tem_multiplas_tarefas(mensagem: str) -> bool:
    """Retorna True se a mensagem contiver mais de uma tarefa."""
    return len(dividir_tarefas(mensagem)) > 1