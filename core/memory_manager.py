import sqlite3
import os
import re
from datetime import datetime

DB_PATH = "data/pyxie_memory.db"


def _conectar():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar():
    """Cria as tabelas se não existirem."""
    conn = _conectar()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fatos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chave     TEXT NOT NULL UNIQUE,
            valor     TEXT NOT NULL,
            criado_em TEXT,
            atualizado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS episodica (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            topico    TEXT NOT NULL,
            resumo    TEXT NOT NULL,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS explicita (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            conteudo  TEXT NOT NULL,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS respostas (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta  TEXT NOT NULL,
            resposta  TEXT NOT NULL,
            criado_em TEXT
        );
    """)
    conn.commit()
    conn.close()


# =========================
# ESCRITA
# =========================

def salvar_fato(chave: str, valor: str):
    agora = datetime.now().isoformat()
    conn = _conectar()
    conn.execute("""
        INSERT INTO fatos (chave, valor, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            valor = excluded.valor,
            atualizado_em = excluded.atualizado_em
    """, (chave.lower().strip(), valor.strip(), agora, agora))
    conn.commit()
    conn.close()


def salvar_episodio(topico: str, resumo: str):
    agora = datetime.now().isoformat()
    conn = _conectar()
    conn.execute(
        "INSERT INTO episodica (topico, resumo, criado_em) VALUES (?, ?, ?)",
        (topico.strip(), resumo.strip(), agora)
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
    """Salva uma resposta que funcionou bem para reutilizar no futuro."""
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
        "SELECT valor FROM fatos WHERE chave = ?", (chave.lower().strip(),)
    ).fetchone()
    conn.close()
    return row["valor"] if row else None


def buscar_todos_fatos() -> dict:
    conn = _conectar()
    rows = conn.execute("SELECT chave, valor FROM fatos").fetchall()
    conn.close()
    return {r["chave"]: r["valor"] for r in rows}


def buscar_episodios_recentes(limite: int = 5) -> list:
    conn = _conectar()
    rows = conn.execute(
        "SELECT topico, resumo FROM episodica ORDER BY id DESC LIMIT ?", (limite,)
    ).fetchall()
    conn.close()
    return [{"topico": r["topico"], "resumo": r["resumo"]} for r in rows]


def buscar_explicitas() -> list:
    conn = _conectar()
    rows = conn.execute(
        "SELECT conteudo FROM explicita ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [r["conteudo"] for r in rows]


def buscar_por_palavra(palavra: str) -> list:
    """Busca em todas as tabelas por uma palavra-chave."""
    palavra = f"%{palavra.lower()}%"
    conn = _conectar()
    resultados = []

    rows = conn.execute(
        "SELECT 'fato' as tipo, chave as ref, valor as conteudo FROM fatos WHERE lower(valor) LIKE ?",
        (palavra,)
    ).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute(
        "SELECT 'episodio' as tipo, topico as ref, resumo as conteudo FROM episodica WHERE lower(resumo) LIKE ? OR lower(topico) LIKE ?",
        (palavra, palavra)
    ).fetchall()
    resultados += [dict(r) for r in rows]

    rows = conn.execute(
        "SELECT 'explicita' as tipo, '' as ref, conteudo FROM explicita WHERE lower(conteudo) LIKE ?",
        (palavra,)
    ).fetchall()
    resultados += [dict(r) for r in rows]

    conn.close()
    return resultados


# =========================
# GERAÇÃO DE CONTEXTO
# Para injetar no prompt do Ollama
# =========================

def gerar_contexto_para_prompt(mensagem: str) -> str:
    """
    Monta um bloco de contexto com memórias relevantes
    para ser injetado no prompt do Ollama.
    """
    partes = []

    # 1. Fatos do usuário (sempre incluídos)
    fatos = buscar_todos_fatos()
    if fatos:
        linhas = [f"- {k}: {v}" for k, v in fatos.items()]
        partes.append("Fatos sobre o usuário:\n" + "\n".join(linhas))

    # 2. Memórias explícitas
    explicitas = buscar_explicitas()
    if explicitas:
        partes.append("O usuário pediu para lembrar:\n" + "\n".join(f"- {e}" for e in explicitas))

    # 3. Episódios recentes
    episodios = buscar_episodios_recentes(limite=3)
    if episodios:
        linhas = [f"- {e['topico']}: {e['resumo']}" for e in episodios]
        partes.append("Conversas recentes:\n" + "\n".join(linhas))

    # 4. Busca por relevância com palavras da mensagem
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
        partes.append("Memórias relacionadas ao assunto:\n" + "\n".join(f"- {r}" for r in relevantes[:4]))

    if not partes:
        return ""

    return "=== Memória da PYXIE ===\n" + "\n\n".join(partes) + "\n========================"


# Inicializa o banco ao importar
inicializar()