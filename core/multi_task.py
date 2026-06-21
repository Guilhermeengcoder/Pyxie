# =============================================================
# core/multi_task.py — Divisor de Múltiplas Tarefas
# PYXIE AI
#
# Responsabilidade:
#   - Detectar se uma mensagem contém mais de uma tarefa
#   - Dividir a mensagem em subtarefas independentes
#   - Retornar lista ordenada para o brain processar em sequência
#
# Exemplos de mensagens compostas:
#   "abre o chrome e pesquise o que é IA"
#   "abre o spotify e o chrome"
#   "que horas são e abre o notepad"
# =============================================================

import re

# Conjunções e conectivos que separam tarefas
SEPARADORES = [
    r"\s+e\s+depois\s+",   # "...e depois..."
    r"\s+depois\s+",        # "...depois..."
    r"\s+e\s+também\s+",   # "...e também..."
    r"\s+também\s+",        # "...também..."
    r"\s+e\s+",             # "...e..."  (mais genérico, vai por último)
    r",\s*",                # "..., ..."
]

# Palavras que indicam início de uma nova tarefa
# (se aparecerem após um separador, confirma que é nova tarefa)
VERBOS_ACAO = [
    "abre", "abra", "abrir",
    "pesquise", "procure", "busque",
    "calcule", "calcula",
    "me diga", "me fale", "me diz",
    "qual", "quem", "quando", "onde", "como", "o que",
    "inicia", "inicie", "lança",
    "mostra", "mostre",
]


def _e_nova_tarefa(trecho: str) -> bool:
    """Verifica se um trecho parece ser o início de uma tarefa independente."""
    trecho = trecho.strip().lower()
    if not trecho:
        return False

    # Se começa com verbo de ação → é nova tarefa
    for verbo in VERBOS_ACAO:
        if trecho.startswith(verbo):
            return True

    # Se tem pelo menos 3 palavras e não é só complemento → provavelmente tarefa
    if len(trecho.split()) >= 3:
        return True

    return False


def dividir_tarefas(mensagem: str) -> list[str]:
    """
    Divide uma mensagem em lista de subtarefas.
    Retorna lista com 1 item se não encontrar múltiplas tarefas.

    Exemplos:
        "abre o chrome e pesquise IA"
        → ["abre o chrome", "pesquise IA"]

        "abre o spotify e o chrome"
        → ["abre o spotify", "abre o chrome"]

        "que horas são?"
        → ["que horas são?"]
    """
    msg = mensagem.strip()

    # Tenta cada separador em ordem de especificidade
    for sep in SEPARADORES:
        partes = re.split(sep, msg, flags=re.IGNORECASE)

        if len(partes) < 2:
            continue

        partes = [p.strip() for p in partes if p.strip()]

        # Verifica se as partes fazem sentido como tarefas separadas
        tarefas_validas = []
        ultimo_verbo = None

        for i, parte in enumerate(partes):
            if i == 0:
                tarefas_validas.append(parte)
                # Extrai o verbo principal da primeira tarefa (ex: "abre")
                palavras = parte.lower().split()
                for verbo in VERBOS_ACAO:
                    v_palavras = verbo.split()
                    if palavras[:len(v_palavras)] == v_palavras:
                        ultimo_verbo = verbo
                        break
            else:
                if _e_nova_tarefa(parte):
                    tarefas_validas.append(parte)
                    palavras = parte.lower().split()
                    for verbo in VERBOS_ACAO:
                        v_palavras = verbo.split()
                        if palavras[:len(v_palavras)] == v_palavras:
                            ultimo_verbo = verbo
                            break
                else:
                    # Pode ser complemento do mesmo verbo (ex: "abre o spotify e o chrome")
                    # Tenta reutilizar o verbo anterior
                    if ultimo_verbo and len(parte.split()) <= 4:
                        tarefas_validas.append(f"{ultimo_verbo} {parte}")
                    else:
                        tarefas_validas.append(parte)

        if len(tarefas_validas) >= 2:
            return tarefas_validas

    # Nenhum separador funcionou → mensagem única
    return [msg]


def tem_multiplas_tarefas(mensagem: str) -> bool:
    """Retorna True se a mensagem contiver mais de uma tarefa."""
    return len(dividir_tarefas(mensagem)) > 1