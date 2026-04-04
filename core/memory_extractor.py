import re
from core.memory_manager import salvar_fato, salvar_episodio, salvar_explicita


# =========================
# PADRÕES DE FATOS DO USUÁRIO
# Adicione ou edite à vontade
# =========================

PADROES_FATOS = [
    # nome
    (r"meu nome [eé] ([a-záàâãéèêíïóôõöúçñ\s]+)", "nome"),
    (r"pode me chamar de ([a-záàâãéèêíïóôõöúçñ\s]+)", "nome"),

    # profissão
    (r"(?:sou|trabalho como) ([a-záàâãéèêíïóôõöúçñ\s]+)", "profissao"),

    # preferências
    (r"(?:gosto de|adoro|prefiro) ([a-záàâãéèêíïóôõöúçñ\s,]+)", "preferencia"),
    (r"(?:não gosto de|detesto|odeio) ([a-záàâãéèêíïóôõöúçñ\s,]+)", "nao_gosta"),

    # localização
    (r"(?:moro em|sou de|vivo em) ([a-záàâãéèêíïóôõöúçñ\s]+)", "localizacao"),

    # idade
    (r"tenho (\d{1,3}) anos", "idade"),

    # rotina
    (r"(?:acordo|durmo|almoço|janto) (?:às|as) (\d{1,2}(?::\d{2})?)", "rotina"),
]


# =========================
# FRASES DE MEMÓRIA EXPLÍCITA
# =========================

TRIGGERS_EXPLICITA = [
    "lembre que",
    "lembrar que",
    "não esqueça que",
    "guarde que",
    "memorize que",
    "anota que",
]


def extrair_e_salvar(mensagem: str, resposta: str = None, topico: str = None):
    """
    Analisa a mensagem (e opcionalmente a resposta) e salva
    automaticamente o que for relevante na memória.
    """
    msg = mensagem.lower().strip()

    # 1. Memória explícita (pedido direto do usuário)
    for trigger in TRIGGERS_EXPLICITA:
        if trigger in msg:
            conteudo = msg.split(trigger, 1)[-1].strip()
            if conteudo:
                salvar_explicita(conteudo)
            return  # se foi explícita, não precisa continuar

    # 2. Fatos sobre o usuário (detecção automática)
    for padrao, chave in PADROES_FATOS:
        match = re.search(padrao, msg)
        if match:
            valor = match.group(1).strip().rstrip(".,!?")
            if len(valor) > 1:
                salvar_fato(chave, valor)

    # 3. Episódio da conversa (salva o tópico se houve pesquisa)
    if topico and len(topico) > 3:
        resumo = resposta[:120] if resposta else mensagem[:120]
        salvar_episodio(topico, resumo)