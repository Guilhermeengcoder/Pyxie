# =============================================================
# core/memory/LTM.py — Long Term Memory unificada da PYXIE
#
# Fusão de memory_manager.py + LTM original.
# Banco único: data/pyxie_memory.db
#
# Tabelas:
#   fatos       → informações diretas sobre o usuário, sem expiração
#   permanente  → ativada por "se lembre que", nunca expira
#   episodica   → conversas relevantes, expiram por inatividade
#   respostas   → pares pergunta/resposta aprendidos
#
# Regras:
#   - Episódios expiram após EXPIRACAO_DIAS sem serem acessados
#   - Cada acesso reseta o timer de expiração
#   - "se lembre que X" salva em permanente — nunca expira
#   - "se esqueça que X" apaga de qualquer tabela
#   - Respostas da própria PYXIE não são salvas como episódio
# =============================================================

import re
import sqlite3
import os
from datetime import datetime, timedelta


# =============================================================
# CONFIG
# =============================================================

DB_PATH        = "data/pyxie_memory.db"
EXPIRACAO_DIAS = 7
SCORE_MINIMO   = 2
MAX_CONTEXTO   = 800


# =============================================================
# CONEXÃO
# =============================================================

def _conectar() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# =============================================================
# INICIALIZAÇÃO
# =============================================================

def _migrar_coluna(conn, tabela: str, coluna: str, definicao: str):
    """Adiciona coluna se não existir — compatibilidade com bancos antigos."""
    colunas = [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in colunas:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
        conn.commit()
        print(f"[LTM] Migração: coluna '{coluna}' adicionada em '{tabela}'.")

def inicializar():
    conn = _conectar()
    agora = datetime.now().isoformat()

    # Cria tabelas base (estrutura mínima compatível com banco existente)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fatos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chave       TEXT    NOT NULL UNIQUE,
            valor       TEXT    NOT NULL,
            importancia INTEGER DEFAULT 3,
            criado_em   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS permanente (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            conteudo  TEXT NOT NULL UNIQUE,
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS episodica (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            topico      TEXT    NOT NULL,
            conteudo    TEXT    NOT NULL,
            importancia INTEGER DEFAULT 2,
            criado_em   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS respostas (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta  TEXT NOT NULL,
            resposta  TEXT NOT NULL,
            criado_em TEXT NOT NULL
        );
    """)

    # Migração: adiciona colunas novas se não existirem
    _migrar_coluna(conn, "fatos",     "acessado_em", f"TEXT NOT NULL DEFAULT '{agora}'")
    _migrar_coluna(conn, "episodica", "acessado_em", f"TEXT NOT NULL DEFAULT '{agora}'")

    # Migração: banco antigo usa 'resumo', novo usa 'conteudo'
    colunas_ep = [r[1] for r in conn.execute("PRAGMA table_info(episodica)").fetchall()]
    if "conteudo" not in colunas_ep and "resumo" in colunas_ep:
        conn.execute("ALTER TABLE episodica ADD COLUMN conteudo TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE episodica SET conteudo = resumo")
        conn.commit()
        print("[LTM] Migração: 'resumo' copiado para 'conteudo' em 'episodica'.")
    elif "conteudo" not in colunas_ep:
        conn.execute("ALTER TABLE episodica ADD COLUMN conteudo TEXT NOT NULL DEFAULT ''")
        conn.commit()
        print("[LTM] Migração: coluna 'conteudo' adicionada em 'episodica'.")

    # Índices
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_fatos_chave
            ON fatos(chave);

        CREATE INDEX IF NOT EXISTS idx_fatos_importancia
            ON fatos(importancia DESC);

        CREATE INDEX IF NOT EXISTS idx_episodica_importancia
            ON episodica(importancia DESC, acessado_em DESC);
    """)

    conn.commit()
    conn.close()


# =============================================================
# PONTUAÇÃO DE RELEVÂNCIA
# =============================================================

def _pontuar(msg: str) -> int:
    msg   = msg.lower()
    score = 0

    if any(p in msg for p in ["meu", "minha", "eu", "sou", "tenho", "moro", "trabalho"]):
        score += 2

    if any(p in msg for p in ["gosto", "prefiro", "odeio", "adoro", "quero"]):
        score += 2

    if re.search(r"\d+", msg):
        score += 1

    if any(p in msg for p in ["projeto", "planejo", "vou", "pretendo", "sonho"]):
        score += 2

    if len(msg) > 20:
        score += 1

    # penalidades
    if msg.endswith("?"):
        score -= 3

    if len(msg) < 20:
        score -= 2

    if any(p in msg for p in ["oi", "olá", "ok", "entendi", "obrigado", "tudo bem", "bom dia", "boa tarde", "boa noite"]):
        score -= 3

    return score


def deve_salvar(msg: str) -> bool:
    return _pontuar(msg) >= SCORE_MINIMO


# =============================================================
# DETECÇÃO DE COMANDOS DE MEMÓRIA
# =============================================================

def detectar_comando_memoria(msg: str):
    """
    Retorna ("salvar", conteudo) ou ("apagar", conteudo) ou None.
    """
    msg_lower = msg.lower().strip()

    for trigger in ["se lembre que", "lembre que", "memorize que", "guarde que", "anota que"]:
        if trigger in msg_lower:
            conteudo = msg_lower.split(trigger, 1)[-1].strip()
            if conteudo:
                return ("salvar", conteudo)

    for trigger in ["se esqueça que", "esqueça que", "esqueca que", "apague que"]:
        if trigger in msg_lower:
            conteudo = msg_lower.split(trigger, 1)[-1].strip()
            if conteudo:
                return ("apagar", conteudo)

    return None


# =============================================================
# ESCRITA
# =============================================================

def salvar_fato(chave: str, valor: str, importancia: int = 3):
    """Salva fato direto sobre o usuário. Nunca expira."""
    agora = datetime.now().isoformat()
    conn  = _conectar()
    conn.execute("""
        INSERT INTO fatos (chave, valor, importancia, criado_em, acessado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            valor       = excluded.valor,
            importancia = excluded.importancia,
            acessado_em = excluded.acessado_em
    """, (chave.lower().strip(), valor.strip(), importancia, agora, agora))
    conn.commit()
    conn.close()


def salvar_permanente(conteudo: str) -> bool:
    """
    Salva memória permanente ativada por 'se lembre que'.
    Retorna True se salvou, False se já existia.
    """
    agora = datetime.now().isoformat()
    conn  = _conectar()

    existente = conn.execute(
        "SELECT 1 FROM permanente WHERE conteudo = ?", (conteudo,)
    ).fetchone()

    if existente:
        conn.close()
        return False

    conn.execute(
        "INSERT INTO permanente (conteudo, criado_em) VALUES (?, ?)",
        (conteudo.strip(), agora)
    )
    conn.commit()
    conn.close()
    return True


def salvar_episodio(topico: str, conteudo: str, importancia: int = 2):
    """
    Salva episódio se tiver pontuação suficiente.
    Ignora duplicatas.
    """
    if not deve_salvar(conteudo):
        return

    agora = datetime.now().isoformat()
    conn  = _conectar()

    existente = conn.execute(
        "SELECT 1 FROM episodica WHERE conteudo = ?", (conteudo,)
    ).fetchone()

    if not existente:
        conn.execute("""
            INSERT INTO episodica (topico, conteudo, importancia, criado_em, acessado_em)
            VALUES (?, ?, ?, ?, ?)
        """, (topico.strip(), conteudo.strip()[:300], importancia, agora, agora))
        conn.commit()

    conn.close()


def salvar_resposta(pergunta: str, resposta: str):
    """Salva par pergunta/resposta aprendido."""
    agora = datetime.now().isoformat()
    conn  = _conectar()
    conn.execute(
        "INSERT INTO respostas (pergunta, resposta, criado_em) VALUES (?, ?, ?)",
        (pergunta.strip(), resposta.strip(), agora)
    )
    conn.commit()
    conn.close()


def apagar_memoria(conteudo: str) -> bool:
    """
    Apaga memória de qualquer tabela que contenha o conteúdo.
    Retorna True se apagou algo.
    """
    termo  = f"%{conteudo.lower()}%"
    conn   = _conectar()
    apagou = False

    cursors = [
        conn.execute("DELETE FROM permanente WHERE lower(conteudo) LIKE ?", (termo,)),
        conn.execute("DELETE FROM episodica  WHERE lower(conteudo) LIKE ?", (termo,)),
        conn.execute("DELETE FROM fatos      WHERE lower(valor)    LIKE ?", (termo,)),
    ]

    for c in cursors:
        if c.rowcount > 0:
            apagou = True

    conn.commit()
    conn.close()
    return apagou


# =============================================================
# EXTRAÇÃO AUTOMÁTICA DE FATOS
# Analisa mensagens do USUÁRIO — nunca respostas da PYXIE.
# =============================================================

_PADROES_FATOS = [
    (r"meu nome [eé] ([a-záàâãéèêíïóôõöúçñ\s]+)",               "nome"),
    (r"pode me chamar de ([a-záàâãéèêíïóôõöúçñ\s]+)",             "nome"),
    (r"tenho (\d{1,3}) anos",                                      "idade"),
    (r"trabalho como ([a-záàâãéèêíïóôõöúçñ\s]+)",                 "profissao"),
    (r"(?:moro em|sou de|vivo em) ([a-záàâãéèêíïóôõöúçñ\s]+)",   "cidade"),
    (r"(?:gosto de|adoro|prefiro) ([a-záàâãéèêíïóôõöúçñ\s,]+)",  "preferencia"),
    (r"(?:não gosto de|detesto|odeio) ([a-záàâãéèêíïóôõöúçñ\s,]+)", "nao_gosta"),
    (r"(?:estudo|curso) ([a-záàâãéèêíïóôõöúçñ\s]+)",              "curso"),
    (r"(?:acordo|durmo|almoço|janto) (?:às|as) (\d{1,2}(?::\d{2})?)", "rotina"),
]

_FRASES_BLOQUEADAS = [
    "o que voce", "voce lembra", "me diga", "me fala",
    "me explique", "voce sabe", "se lembre", "se esqueça",
    "esqueca", "lembre que", "memorize", "guarde que",
]


def extrair_e_salvar(mensagem: str, topico: str = None):
    """
    Extrai fatos e episódios da mensagem do USUÁRIO.
    Nunca chamar com respostas da PYXIE.
    """
    msg = mensagem.lower().strip()

    # ignora perguntas
    if msg.endswith("?"):
        return

    # ignora comandos de memória (já tratados pelo brain)
    if any(f in msg for f in _FRASES_BLOQUEADAS):
        return

    # extrai fatos estruturados
    for padrao, chave in _PADROES_FATOS:
        match = re.search(padrao, msg)
        if match:
            valor = match.group(1).strip().rstrip(".,!?")

            if len(valor) < 2:
                continue

            palavras_invalidas = ["feliz", "triste", "cansado", "ocupado", "bem", "mal"]
            if chave == "profissao" and any(p in valor for p in palavras_invalidas):
                continue

            salvar_fato(chave, valor)

    # salva como episódio se houver tópico e pontuação suficiente
    if topico and len(topico) > 3:
        salvar_episodio(topico, mensagem[:300])


# =============================================================
# LEITURA
# =============================================================

def buscar_fato(chave: str):
    conn = _conectar()
    row  = conn.execute(
        "SELECT valor FROM fatos WHERE chave = ?", (chave.lower().strip(),)
    ).fetchone()
    conn.close()
    return row["valor"] if row else None


def buscar_todos_fatos() -> dict:
    conn = _conectar()
    rows = conn.execute(
        "SELECT chave, valor FROM fatos ORDER BY importancia DESC"
    ).fetchall()
    conn.close()

    # atualiza acesso
    _atualizar_acesso("fatos", [r["chave"] for r in rows], por_chave=True)

    return {r["chave"]: r["valor"] for r in rows}


def buscar_por_palavra(palavra: str) -> list:
    """
    Busca em todas as tabelas e retorna lista com tipo identificado.
    Retorna: [{"tipo": "fato"|"episodio"|"permanente"|"resposta", "ref": ..., "conteudo": ...}]
    """
    termo = f"%{palavra.lower()}%"
    conn  = _conectar()
    resultados = []

    rows = conn.execute("""
        SELECT 'fato' as tipo, chave as ref, valor as conteudo
        FROM fatos WHERE lower(valor) LIKE ?
    """, (termo,)).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute("""
        SELECT 'episodio' as tipo, topico as ref, conteudo
        FROM episodica WHERE lower(conteudo) LIKE ? OR lower(topico) LIKE ?
    """, (termo, termo)).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute("""
        SELECT 'permanente' as tipo, '' as ref, conteudo
        FROM permanente WHERE lower(conteudo) LIKE ?
    """, (termo,)).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute("""
        SELECT 'resposta' as tipo, pergunta as ref, resposta as conteudo
        FROM respostas WHERE lower(resposta) LIKE ? OR lower(pergunta) LIKE ?
    """, (termo, termo)).fetchall()
    resultados += [dict(r) for r in rows]

    conn.close()
    return resultados


def buscar_episodios_recentes(limite: int = 5) -> list:
    conn = _conectar()
    rows = conn.execute("""
        SELECT id, topico, conteudo
        FROM episodica
        ORDER BY importancia DESC, acessado_em DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()

    ids = [r["id"] for r in rows]
    _atualizar_acesso("episodica", ids)

    return [{"topico": r["topico"], "conteudo": r["conteudo"]} for r in rows]


# =============================================================
# ATUALIZAÇÃO DE ACESSO (reseta timer de expiração)
# =============================================================

def _atualizar_acesso(tabela: str, ids: list, por_chave: bool = False):
    if not ids or tabela == "permanente":
        return

    agora = datetime.now().isoformat()
    conn  = _conectar()

    if por_chave:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE {tabela} SET acessado_em = ? WHERE chave IN ({placeholders})",
            [agora] + ids
        )
    else:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE {tabela} SET acessado_em = ? WHERE id IN ({placeholders})",
            [agora] + ids
        )

    conn.commit()
    conn.close()


# =============================================================
# RECUPERAÇÃO INTELIGENTE PARA PROMPT
# =============================================================

def buscar_relevantes(mensagem: str) -> dict:
    """
    Busca memórias relevantes para a mensagem atual.
    Retorna dict com fatos, permanente e episodios.
    """
    palavras  = [p for p in mensagem.lower().split() if len(p) > 3]
    conn      = _conectar()
    resultado = {"fatos": {}, "permanente": [], "episodios": []}

    # fatos — sempre carrega (são poucos e sempre relevantes)
    rows = conn.execute(
        "SELECT chave, valor FROM fatos ORDER BY importancia DESC"
    ).fetchall()
    resultado["fatos"] = {r["chave"]: r["valor"] for r in rows}
    _atualizar_acesso("fatos", [r["chave"] for r in rows], por_chave=True)

    # permanentes — sempre carrega
    rows = conn.execute(
        "SELECT conteudo FROM permanente ORDER BY criado_em DESC LIMIT 10"
    ).fetchall()
    resultado["permanente"] = [r["conteudo"] for r in rows]

    # episódios — só os relevantes para a mensagem
    ids_ep = []
    vistos = set()

    for palavra in palavras[:4]:
        rows = conn.execute("""
            SELECT id, topico, conteudo FROM episodica
            WHERE lower(conteudo) LIKE ? OR lower(topico) LIKE ?
            ORDER BY importancia DESC, acessado_em DESC
            LIMIT 3
        """, (f"%{palavra}%", f"%{palavra}%")).fetchall()

        for r in rows:
            chave = r["conteudo"][:60]
            if chave not in vistos:
                vistos.add(chave)
                resultado["episodios"].append(r["conteudo"])
                ids_ep.append(r["id"])

    conn.close()
    _atualizar_acesso("episodica", ids_ep)

    return resultado


def gerar_contexto_para_prompt(mensagem: str) -> str:
    """
    Gera bloco de contexto para injetar no prompt do Ollama.
    Inclui fatos, permanentes, episódios relevantes e buscas por palavra.
    """
    memoria = buscar_relevantes(mensagem)
    partes  = []
    total   = 0

    # fatos
    if memoria["fatos"]:
        linhas = [f"- {k}: {v}" for k, v in memoria["fatos"].items()]
        bloco  = "Fatos sobre o usuário:\n" + "\n".join(linhas)
        if total + len(bloco) <= MAX_CONTEXTO:
            partes.append(bloco)
            total += len(bloco)

    # permanentes
    if memoria["permanente"]:
        bloco = "Lembre sempre:\n" + "\n".join(f"- {p}" for p in memoria["permanente"])
        if total + len(bloco) <= MAX_CONTEXTO:
            partes.append(bloco)
            total += len(bloco)

    # episódios relevantes
    if memoria["episodios"]:
        bloco = "Contexto relevante:\n" + "\n".join(
            f"- {e[:100]}" for e in memoria["episodios"][:3]
        )
        if total + len(bloco) <= MAX_CONTEXTO:
            partes.append(bloco)
            total += len(bloco)

    # busca por palavras-chave na tabela de respostas
    palavras = [p for p in mensagem.lower().split() if len(p) > 3]
    vistos   = set()
    relevantes = []

    for palavra in palavras[:3]:
        for r in buscar_por_palavra(palavra):
            chave = r["conteudo"][:60]
            if chave not in vistos:
                vistos.add(chave)
                relevantes.append(r["conteudo"])

    if relevantes:
        bloco = "Memórias relacionadas:\n" + "\n".join(f"- {r[:100]}" for r in relevantes[:4])
        if total + len(bloco) <= MAX_CONTEXTO:
            partes.append(bloco)

    if not partes:
        return ""

    return "=== Memória ===\n" + "\n\n".join(partes) + "\n==============="


# =============================================================
# LIMPEZA AUTOMÁTICA
# =============================================================

def limpar_expirados():
    """Remove episódios não acessados há mais de EXPIRACAO_DIAS dias."""
    limite = (datetime.now() - timedelta(days=EXPIRACAO_DIAS)).isoformat()
    conn   = _conectar()

    cursor = conn.execute(
        "DELETE FROM episodica WHERE acessado_em < ?", (limite,)
    )
    removidos = cursor.rowcount

    conn.commit()
    conn.close()

    if removidos:
        print(f"[LTM] {removidos} episódio(s) expirado(s) removido(s).")


# =============================================================
# INICIALIZA AO IMPORTAR
# =============================================================

inicializar()
limpar_expirados()