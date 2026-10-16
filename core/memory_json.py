# =============================================================
# core/memory_json.py — Edição segura do memory.json
# PYXIE AI
#
# - Lock + escrita atômica (nunca deixa o arquivo pela metade)
# - Backup automático antes de cada alteração (memory.json.bak)
# - Seções protegidas (schema_version, description, memory_rules)
# - Bloqueia senhas, tokens e chaves
# - NUNCA sobrescreve um arquivo ilegível: se o JSON estiver
#   quebrado, a edição é recusada
# =============================================================

import json
import os
import re
import tempfile
import threading
from pathlib import Path

# core/memory_json.py -> raiz do projeto -> memory.json
ARQUIVO = Path(__file__).resolve().parent.parent / "memory.json"
BACKUP = ARQUIVO.with_name("memory.json.bak")

PROTEGIDAS = {"schema_version", "description", "memory_rules"}
MAX_VALOR_CHARS = 1500
MAX_PROFUNDIDADE = 5

_SENSIVEL = re.compile(
    r"senha|password|token|api[_ -]?key|secret|segredo|gsk_|sk-[a-z0-9]",
    re.I,
)

_lock = threading.RLock()


# =============================================================
# DETECÇÃO DE PEDIDOS (recebe a mensagem já normalizada)
# =============================================================

_LOCAIS = ("no json", "na memoria fixa", "no memory json", "no memoryjson")

_VERBOS = re.compile(
    r"\b(salv|anot|regist|adicion|atualiz|alter|apag|remov|corrij|guard|coloc|inclu)\w*"
)


def eh_pedido_de_edicao(msg_norm: str) -> bool:
    """Precisa citar o JSON/memória fixa E ter um verbo de escrita."""
    return any(l in msg_norm for l in _LOCAIS) and bool(_VERBOS.search(msg_norm))


def eh_pedido_de_desfazer(msg_norm: str) -> bool:
    return bool(re.search(r"\bdesfa[cz]\w*", msg_norm)) and (
        "json" in msg_norm or "memoria fixa" in msg_norm
    )


# =============================================================
# LEITURA
# =============================================================

def carregar_estrito() -> dict:
    """Lê o arquivo ou levanta ValueError. Usada antes de editar."""
    try:
        with ARQUIVO.open("r", encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        raise ValueError("memory.json não encontrado")
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"memory.json ilegível: {e}")

    if not isinstance(dados, dict):
        raise ValueError("o memory.json precisa ser um objeto JSON")

    return dados


def carregar() -> dict:
    """Lê o arquivo; em caso de erro devolve {} (só para leitura)."""
    try:
        return carregar_estrito()
    except ValueError as e:
        print(f"[memory_json] {e}")
        return {}


# =============================================================
# ESCRITA
# =============================================================

def _gravar(dados: dict):
    if ARQUIVO.exists():
        # backup simples da versão anterior (permite "desfazer")
        with ARQUIVO.open("rb") as origem, BACKUP.open("wb") as destino:
            destino.write(origem.read())

    fd, tmp = tempfile.mkstemp(dir=str(ARQUIVO.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        os.replace(tmp, ARQUIVO)   # troca atômica
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def desfazer() -> bool:
    """Restaura a versão anterior ao último salvamento."""
    with _lock:
        if not BACKUP.exists():
            return False
        os.replace(BACKUP, ARQUIVO)
        return True


def aplicar_operacao(op: dict) -> str:
    """
    Aplica UMA operação: {"op": "set|add|remove", "path": "a.b.c", "value": ...}
    Retorna uma descrição curta do que foi feito, ou levanta ValueError.
    """
    acao = op.get("op")
    caminho = op.get("path")
    valor = op.get("value")

    if acao not in ("set", "add", "remove"):
        raise ValueError("operação desconhecida")

    if not isinstance(caminho, str) or not caminho.strip():
        raise ValueError("caminho vazio")

    partes = [p.strip() for p in caminho.split(".") if p.strip()]

    if not partes or len(partes) > MAX_PROFUNDIDADE:
        raise ValueError("caminho inválido")

    if partes[0] in PROTEGIDAS:
        raise ValueError(f"a seção '{partes[0]}' é protegida")

    if acao in ("set", "add"):
        if valor is None:
            raise ValueError("faltou o valor")
        if len(json.dumps(valor, ensure_ascii=False)) > MAX_VALOR_CHARS:
            raise ValueError("valor grande demais")
        if _SENSIVEL.search(json.dumps(valor, ensure_ascii=False)):
            raise ValueError("não guardo senhas, tokens ou chaves (regra da memory_rules)")

    with _lock:
        dados = carregar_estrito()

        pai = dados
        for p in partes[:-1]:
            if not isinstance(pai, dict):
                raise ValueError("o caminho passa por algo que não é um objeto")
            if p not in pai:
                if acao == "remove":
                    raise ValueError("esse caminho não existe")
                pai[p] = {}
            pai = pai[p]

        if not isinstance(pai, dict):
            raise ValueError("o caminho passa por algo que não é um objeto")

        ultimo = partes[-1]

        if acao == "set":
            pai[ultimo] = valor
            descricao = f'"{caminho}" definido como {json.dumps(valor, ensure_ascii=False)}'

        elif acao == "add":
            atual = pai.get(ultimo)
            if atual is None:
                pai[ultimo] = [valor]
            elif isinstance(atual, list):
                if valor not in atual:
                    atual.append(valor)
            elif isinstance(atual, dict):
                raise ValueError("esse campo é um objeto; use definir em vez de acrescentar")
            else:
                pai[ultimo] = [atual, valor]
            descricao = f'adicionado {json.dumps(valor, ensure_ascii=False)} em "{caminho}"'

        else:  # remove
            if ultimo not in pai:
                raise ValueError("esse caminho não existe")
            if valor is not None and isinstance(pai[ultimo], list):
                if valor not in pai[ultimo]:
                    raise ValueError("esse item não está na lista")
                pai[ultimo].remove(valor)
                descricao = f'removido {json.dumps(valor, ensure_ascii=False)} de "{caminho}"'
            else:
                del pai[ultimo]
                descricao = f'"{caminho}" removido'

        _gravar(dados)

    return descricao


# =============================================================
# PROMPT PARA O LLM TRADUZIR O PEDIDO EM UMA OPERAÇÃO
# =============================================================

def montar_prompt_edicao(mensagem: str, dados: dict) -> str:
    atual = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))

    return (
        "Tarefa técnica: converter o pedido do usuário em UMA operação sobre o "
        "JSON de memória abaixo.\n"
        "Responda SOMENTE com um objeto JSON, sem texto extra, neste formato:\n"
        '{"op": "set", "path": "secao.chave", "value": "texto"}\n'
        "- op: set (define ou substitui), add (acrescenta item a uma lista) "
        "ou remove (apaga uma chave; se value for informado, apaga só esse item da lista).\n"
        "- Reutilize caminhos que já existem no JSON e siga o estilo das chaves "
        "existentes (snake_case, sem acentos).\n"
        "- Listas de objetos (ex.: family_and_companion_names): para incluir use add com o "
        "objeto inteiro; para alterar um item, use set no caminho da lista com a lista completa corrigida.\n"
        '- Se o pedido não for salvar, alterar ou apagar uma informação, responda {"op": "none"}.\n\n'
        f"JSON atual:\n{atual}\n\n"
        f"Pedido do usuário: {mensagem}"
    )


def extrair_operacao(texto: str):
    """Pega o primeiro objeto JSON da resposta do LLM. None se inválido."""
    if not texto:
        return None

    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    if not achado:
        return None

    try:
        op = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None

    if not isinstance(op, dict) or op.get("op") in (None, "none"):
        return None

    return op