import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = "data/pyxie_memory.db"


# =========================
# CONEXÃO
# =========================

def _conectar():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# INICIALIZAÇÃO
# =========================

def inicializar():
    conn = _conectar()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT NOT NULL UNIQUE,
            valor TEXT NOT NULL,
            importancia INTEGER DEFAULT 3,
            criado_em TEXT,
            atualizado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS episodica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topico TEXT NOT NULL,
            resumo TEXT NOT NULL,
            importancia INTEGER DEFAULT 2,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS explicita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conteudo TEXT NOT NULL,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL,
            criado_em TEXT
        );
    """)

    conn.commit()
    conn.close()


# =========================
# FILTRO DE IMPORTÂNCIA
# =========================

def pontuar_importancia(msg: str) -> int:
    score = 0
    msg = msg.lower()

    if any(p in msg for p in ["meu", "minha", "eu", "sou", "estou"]):
        score += 2

    if any(p in msg for p in ["gosto", "odeio", "prefiro"]):
        score += 2

    if any(p in msg for p in ["vou", "quero", "pretendo", "planejo"]):
        score += 2

    if len(msg) > 20:
        score += 1

    if msg.endswith("?"):
        score -= 2

    if any(p in msg for p in ["oi", "ola", "bom dia"]):
        score -= 2

    return score


def deve_salvar(msg: str) -> bool:
    return pontuar_importancia(msg) >= 2


# =========================
# ESCRITA
# =========================

def salvar_fato(chave: str, valor: str, importancia: int = 3):
    agora = datetime.now().isoformat()
    conn = _conectar()

    conn.execute("""
        INSERT INTO fatos (chave, valor, importancia, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            valor = excluded.valor,
            importancia = excluded.importancia,
            atualizado_em = excluded.atualizado_em
    """, (chave.lower().strip(), valor.strip(), importancia, agora, agora))

    conn.commit()
    conn.close()


def salvar_episodio(topico: str, resumo: str, importancia: int = 2):
    if not deve_salvar(resumo):
        return

    conn = _conectar()

    # Evita duplicação
    existente = conn.execute(
        "SELECT 1 FROM episodica WHERE resumo = ?",
        (resumo,)
    ).fetchone()

    if existente:
        conn.close()
        return

    agora = datetime.now().isoformat()

    conn.execute(
        "INSERT INTO episodica (topico, resumo, importancia, criado_em) VALUES (?, ?, ?, ?)",
        (topico.strip(), resumo.strip(), importancia, agora)
    )

    conn.commit()
    conn.close()


def salvar_explicita(conteudo: str):
    agora = datetime.now().isoformat()
    conn = _conectar()

    conn.execute(
        "INSERT INTO explicita (conteudo, criado_em) VALUES (?, ?)",
        (conteudo.strip(), agora)
    )

    conn.commit()
    conn.close()


def salvar_resposta(pergunta: str, resposta: str):
    agora = datetime.now().isoformat()
    conn = _conectar()

    conn.execute(
        "INSERT INTO respostas (pergunta, resposta, criado_em) VALUES (?, ?, ?)",
        (pergunta.strip(), resposta.strip(), agora)
    )

    conn.commit()
    conn.close()


# =========================
# LEITURA
# =========================

def buscar_fato(chave: str):
    conn = _conectar()
    row = conn.execute(
        "SELECT valor FROM fatos WHERE chave = ?",
        (chave.lower().strip(),)
    ).fetchone()
    conn.close()
    return row["valor"] if row else None


def buscar_todos_fatos():
    conn = _conectar()
    rows = conn.execute(
        "SELECT chave, valor FROM fatos ORDER BY importancia DESC"
    ).fetchall()
    conn.close()
    return {r["chave"]: r["valor"] for r in rows}


def buscar_episodios_recentes(limite: int = 5):
    conn = _conectar()
    rows = conn.execute("""
        SELECT topico, resumo 
        FROM episodica 
        ORDER BY importancia DESC, id DESC 
        LIMIT ?
    """, (limite,)).fetchall()

    conn.close()
    return [{"topico": r["topico"], "resumo": r["resumo"]} for r in rows]


def buscar_explicitas():
    conn = _conectar()
    rows = conn.execute(
        "SELECT conteudo FROM explicita ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [r["conteudo"] for r in rows]


def buscar_por_palavra(palavra: str):
    palavra = f"%{palavra.lower()}%"
    conn = _conectar()
    resultados = []

    # fatos têm mais peso
    rows = conn.execute("""
        SELECT 'fato' as tipo, chave as ref, valor as conteudo 
        FROM fatos 
        WHERE lower(valor) LIKE ?
    """, (palavra,)).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute("""
        SELECT 'episodio' as tipo, topico as ref, resumo as conteudo 
        FROM episodica 
        WHERE lower(resumo) LIKE ? OR lower(topico) LIKE ?
    """, (palavra, palavra)).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute("""
        SELECT 'explicita' as tipo, '' as ref, conteudo 
        FROM explicita 
        WHERE lower(conteudo) LIKE ?
    """, (palavra,)).fetchall()
    resultados += [dict(r) for r in rows]

    conn.close()
    return resultados


# =========================
# LIMPEZA (ESQUECIMENTO)
# =========================

def limpar_memoria():
    conn = _conectar()
    agora = datetime.now()

    rows = conn.execute(
        "SELECT id, criado_em, importancia FROM episodica"
    ).fetchall()

    for r in rows:
        tempo = agora - datetime.fromisoformat(r["criado_em"])
        limite = timedelta(days=1 + r["importancia"] * 2)

        if tempo > limite:
            conn.execute("DELETE FROM episodica WHERE id = ?", (r["id"],))

    conn.commit()
    conn.close()


# =========================
# CONTEXTO PARA OLLAMA
# =========================

def gerar_contexto_para_prompt(mensagem: str) -> str:
    partes = []

    # fatos
    fatos = buscar_todos_fatos()
    if fatos:
        linhas = [f"- {k}: {v}" for k, v in fatos.items()]
        partes.append("Fatos sobre o usuário:\n" + "\n".join(linhas))

    # explícitas
    explicitas = buscar_explicitas()
    if explicitas:
        partes.append("O usuário pediu para lembrar:\n" + "\n".join(f"- {e}" for e in explicitas))

    # episódios relevantes
    episodios = buscar_episodios_recentes(limite=3)
    if episodios:
        linhas = [f"- {e['topico']}: {e['resumo']}" for e in episodios]
        partes.append("Conversas relevantes:\n" + "\n".join(linhas))

    # busca por palavras
    palavras = [p for p in mensagem.lower().split() if len(p) > 3]
    relevantes = []
    vistos = set()

    for palavra in palavras[:3]:
        for r in buscar_por_palavra(palavra):
            chave = r["conteudo"][:60]
            if chave not in vistos:
                vistos.add(chave)
                relevantes.append(r["conteudo"])

    if relevantes:
        partes.append("Memórias relacionadas:\n" + "\n".join(f"- {r}" for r in relevantes[:4]))

    if not partes:
        return ""

    return "=== Memória da PYXIE ===\n" + "\n\n".join(partes) + "\n========================"


# Inicializa automaticamente
inicializar()