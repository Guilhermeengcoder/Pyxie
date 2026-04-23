import re
from core.memory_manager import salvar_fato, salvar_episodio, salvar_explicita


# =========================
# PADRÕES DE FATOS DO USUÁRIO
# =========================

PADROES_FATOS = [
    (r"meu nome [eé] ([a-záàâãéèêíïóôõöúçñ\s]+)", "nome"),
    (r"pode me chamar de ([a-záàâãéèêíïóôõöúçñ\s]+)", "nome"),

    # ⚠️ profissão mais segura
    (r"trabalho como ([a-záàâãéèêíïóôõöúçñ\s]+)", "profissao"),

    (r"(?:gosto de|adoro|prefiro) ([a-záàâãéèêíïóôõöúçñ\s,]+)", "preferencia"),
    (r"(?:não gosto de|detesto|odeio) ([a-záàâãéèêíïóôõöúçñ\s,]+)", "nao_gosta"),

    (r"(?:moro em|sou de|vivo em) ([a-záàâãéèêíïóôõöúçñ\s]+)", "localizacao"),
    (r"tenho (\d{1,3}) anos", "idade"),

    (r"(?:acordo|durmo|almoço|janto) (?:às|as) (\d{1,2}(?::\d{2})?)", "rotina"),
]


# =========================
# FRASES DE MEMÓRIA EXPLÍCITA
# =========================

TRIGGERS_EXPLICITA = [
    "lembre que",
    "lembrar que",
    "não esqueça que",
    "nao esqueca que",
    "guarde que",
    "memorize que",
    "anota que",
]


# =========================
# BLOQUEIOS IMPORTANTES
# =========================

FRASES_BLOQUEADAS = [
    "o que voce",
    "voce lembra",
    "se lembra",
    "voce sabe",
    "me diga",
    "me fala",
    "me explique",
]


def extrair_e_salvar(mensagem: str, resposta: str = None, topico: str = None):
    msg = mensagem.lower().strip()

    # 🚫 1. IGNORAR PERGUNTAS
    if msg.endswith("?"):
        return

    # 🚫 2. IGNORAR FRASES GENÉRICAS
    if any(frase in msg for frase in FRASES_BLOQUEADAS):
        return

    # =========================
    # 3. MEMÓRIA EXPLÍCITA
    # =========================
    for trigger in TRIGGERS_EXPLICITA:
        if trigger in msg:
            conteudo = msg.split(trigger, 1)[-1].strip()
            if conteudo and len(conteudo) > 3:
                salvar_explicita(conteudo)
            return

    # =========================
    # 4. FATOS DO USUÁRIO
    # =========================
    for padrao, chave in PADROES_FATOS:
        match = re.search(padrao, msg)
        if match:
            valor = match.group(1).strip().rstrip(".,!?")

            # 🚫 filtro extra
            if len(valor) < 2:
                continue

            # 🚫 evita coisas tipo "sou feliz", "sou cansado"
            if chave == "profissao":
                palavras_invalidas = ["feliz", "triste", "cansado", "ocupado"]
                if any(p in valor for p in palavras_invalidas):
                    continue

            salvar_fato(chave, valor)

    # =========================
    # 5. EPISÓDIO (COM CONTROLE)
    # =========================
    if topico and len(topico) > 3:
        if resposta:
            resumo = resposta[:120]
        else:
            resumo = mensagem[:120]

        # 🚫 evita salvar coisa inútil
        if len(resumo.strip()) > 10:
            salvar_episodio(topico, resumo)