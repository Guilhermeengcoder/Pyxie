# =============================================================
# core/db.py — Acesso ao Postgres (Neon)
# Sem DATABASE_URL, tudo devolve vazio/None e o app segue normal.
# =============================================================

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pip install "psycopg[binary]"
    psycopg = None

_iniciado = False


def disponivel() -> bool:
    return bool(psycopg and (os.getenv("DATABASE_URL") or "").strip())


@contextmanager
def conexao():
    with psycopg.connect(
        os.environ["DATABASE_URL"].strip(), row_factory=dict_row, connect_timeout=10
    ) as con:
        yield con


def iniciar():
    """Cria as tabelas se não existirem. Seguro chamar várias vezes."""
    global _iniciado
    if _iniciado or not disponivel():
        return
    sql = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    with conexao() as con:
        con.execute(sql)
    _iniciado = True


def executar(sql, params=()):
    if not disponivel():
        return None
    iniciar()
    with conexao() as con:
        return con.execute(sql, params).fetchall() if sql.lstrip().upper().startswith(
            ("SELECT", "WITH")
        ) or "RETURNING" in sql.upper() else con.execute(sql, params) and None


def registrar_geracao(**campos) -> None:
    """Grava uma geração de imagem. Nunca levanta erro (não derruba o chat)."""
    try:
        if not disponivel():
            return
        colunas = ", ".join(campos)
        marcas = ", ".join(["%s"] * len(campos))
        executar(
            f"INSERT INTO geracoes_imagem ({colunas}) VALUES ({marcas})",
            tuple(campos.values()),
        )
    except Exception as e:
        print(f"[db] não consegui registrar a geração: {e}")