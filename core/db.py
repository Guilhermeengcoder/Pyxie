
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
    """Roda um comando. Devolve lista de dicts se ele retornar linhas
    (SELECT, WITH ou RETURNING); senão, None. Sem banco, devolve None."""
    if not disponivel():
        return None
    iniciar()
    with conexao() as con:
        cursor = con.execute(sql, params)
        if cursor.description is not None:
            return cursor.fetchall()
        return None


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


# =============================================================
# PROJETOS
# =============================================================

def criar_projeto(nome: str, instrucoes: str = ""):
    """Cria um projeto e devolve seus dados, ou None se o banco estiver indisponível."""
    nome = str(nome or "").strip()
    instrucoes = str(instrucoes or "")

    if not nome:
        raise ValueError("O nome do projeto não pode ficar vazio.")

    resultado = executar(
        """
        INSERT INTO projetos (nome, instrucoes)
        VALUES (%s, %s)
        RETURNING *
        """,
        (nome, instrucoes),
    )

    return resultado[0] if resultado else None


def listar_projetos():
    """Lista os projetos do mais recentemente atualizado para o mais antigo."""
    resultado = executar(
        """
        SELECT *
        FROM projetos
        ORDER BY atualizado_em DESC, id DESC
        """
    )
    return resultado or []


def buscar_projeto(projeto_id: int):
    """Busca um projeto pelo ID. Devolve um dicionário ou None."""
    resultado = executar(
        """
        SELECT *
        FROM projetos
        WHERE id = %s
        """,
        (projeto_id,),
    )

    return resultado[0] if resultado else None


def atualizar_projeto(
    projeto_id: int,
    nome: str | None = None,
    instrucoes: str | None = None,
):
    """Atualiza os campos fornecidos e devolve o projeto atualizado."""
    projeto = buscar_projeto(projeto_id)

    if projeto is None:
        return None

    novo_nome = projeto["nome"] if nome is None else str(nome).strip()
    novas_instrucoes = (
        projeto["instrucoes"] if instrucoes is None else str(instrucoes)
    )

    if not novo_nome:
        raise ValueError("O nome do projeto não pode ficar vazio.")

    resultado = executar(
        """
        UPDATE projetos
        SET nome = %s,
            instrucoes = %s,
            atualizado_em = now()
        WHERE id = %s
        RETURNING *
        """,
        (novo_nome, novas_instrucoes, projeto_id),
    )

    return resultado[0] if resultado else None


def excluir_projeto(projeto_id: int) -> bool:
    """Exclui um projeto. Mensagens e arquivos vinculados são removidos em cascata."""
    resultado = executar(
        """
        DELETE FROM projetos
        WHERE id = %s
        RETURNING id
        """,
        (projeto_id,),
    )

    return bool(resultado)


# =============================================================
# ARQUIVOS DOS PROJETOS
# =============================================================

def salvar_arquivo_projeto(
    projeto_id: int,
    nome: str,
    conteudo: str,
):
    """
    Cria um arquivo ou atualiza seu conteúdo se já existir no projeto.
    A data de criação é preservada e a data de atualização é renovada.
    """
    nome = str(nome or "").strip()
    conteudo = str(conteudo)

    if not nome:
        raise ValueError("O nome do arquivo não pode ficar vazio.")

    if not disponivel():
        return None

    resultado = executar(
        """
        INSERT INTO projeto_arquivos (
            projeto_id,
            nome,
            conteudo
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (projeto_id, nome)
        DO UPDATE SET
            conteudo = EXCLUDED.conteudo,
            atualizado_em = now()
        RETURNING *
        """,
        (projeto_id, nome, conteudo),
    )

    return resultado[0] if resultado else None


def buscar_arquivo_projeto(projeto_id: int, nome: str):
    """Busca um arquivo específico dentro de um projeto."""
    resultado = executar(
        """
        SELECT *
        FROM projeto_arquivos
        WHERE projeto_id = %s
          AND nome = %s
        """,
        (projeto_id, nome),
    )

    return resultado[0] if resultado else None


def listar_arquivos_projeto(projeto_id: int):
    """Lista os arquivos de um projeto, sem retornar seus conteúdos completos."""
    resultado = executar(
        """
        SELECT
            id,
            projeto_id,
            nome,
            criado_em,
            atualizado_em
        FROM projeto_arquivos
        WHERE projeto_id = %s
        ORDER BY nome
        """,
        (projeto_id,),
    )

    return resultado or []


def excluir_arquivo_projeto(projeto_id: int, nome: str) -> bool:
    """Exclui um arquivo específico de um projeto."""
    resultado = executar(
        """
        DELETE FROM projeto_arquivos
        WHERE projeto_id = %s
          AND nome = %s
        RETURNING id
        """,
        (projeto_id, nome),
    )

    return bool(resultado)


# =============================================================
# MENSAGENS DOS PROJETOS
# =============================================================

def registrar_mensagem_projeto(
    projeto_id: int,
    papel: str,
    conteudo: str,
):
    """Registra uma mensagem no histórico permanente de um projeto."""
    if papel not in ("user", "assistant"):
        raise ValueError("O papel deve ser 'user' ou 'assistant'.")

    resultado = executar(
        """
        INSERT INTO projeto_mensagens (
            projeto_id,
            papel,
            conteudo
        )
        VALUES (%s, %s, %s)
        RETURNING *
        """,
        (projeto_id, papel, str(conteudo)),
    )

    return resultado[0] if resultado else None


def listar_mensagens_projeto(
    projeto_id: int,
    limite: int = 50,
):
    """Retorna as mensagens mais recentes em ordem cronológica."""
    limite = max(1, min(int(limite), 500))

    resultado = executar(
        """
        SELECT *
        FROM (
            SELECT *
            FROM projeto_mensagens
            WHERE projeto_id = %s
            ORDER BY id DESC
            LIMIT %s
        ) AS recentes
        ORDER BY id ASC
        """,
        (projeto_id, limite),
    )

    return resultado or []

def listar_arquivos_com_conteudo(projeto_id: int):
    """Nome e conteúdo de todos os arquivos do projeto (para montar o contexto da IA)."""
    resultado = executar(
        """
        SELECT nome, conteudo
        FROM projeto_arquivos
        WHERE projeto_id = %s
        ORDER BY nome
        """,
        (projeto_id,),
    )
    return resultado or []