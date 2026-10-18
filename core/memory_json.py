# =============================================================
# core/memory_json.py — Edição segura da memória fixa
# PYXIE AI
#
# - Armazenamento REMOTO (Upstash Redis) quando as variáveis
#   UPSTASH_REDIS_REST_URL e UPSTASH_REDIS_REST_TOKEN existem.
#   Terminal e API passam a enxergar a MESMA memória.
# - Sem as variáveis, cai no arquivo local memory.json (como antes).
# - Backup da versão anterior antes de cada alteração (desfazer)
# - Seções protegidas (schema_version, description, memory_rules)
# - Bloqueia senhas, tokens e chaves
# - NUNCA sobrescreve memória ilegível: se a leitura falhar,
#   a edição é recusada
# - Confere a gravação lendo de volta
# =============================================================

import json
import os
import re
import tempfile
import threading
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

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
# ARMAZENAMENTO REMOTO (Upstash Redis via REST/HTTPS)
# =============================================================

UPSTASH_URL = (os.getenv("UPSTASH_REDIS_REST_URL") or "").strip()
UPSTASH_TOKEN = (os.getenv("UPSTASH_REDIS_REST_TOKEN") or "").strip()

CHAVE = "pyxie:memory"
CHAVE_BAK = "pyxie:memory:bak"


def _remoto() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


def _cmd(*args):
    """Executa um comando Redis (ex.: _cmd("GET", "chave")) e devolve o resultado."""
    r = requests.post(
        UPSTASH_URL,
        headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        json=list(args),
        timeout=5,
    )
    r.raise_for_status()
    corpo = r.json()
    if "error" in corpo:
        raise requests.RequestException(corpo["error"])
    return corpo.get("result")


# =============================================================
# DETECÇÃO DE PEDIDOS (recebe a mensagem já normalizada:
# minúscula, sem acento e sem pontuação — "memory.json" chega
# como "memoryjson")
# =============================================================

# "no json", "do json", "na memoria fixa", "no memory json"...
_LOCAIS = re.compile(
    r"\b(?:no|na|do|da|ao|em|nos|dos)\s+"
    r"(?:memory\s*json|json|memoria\s+fixa)\b"
)

_VERBOS = re.compile(
    r"\b(salv|anot|regist|adicion|atualiz|alter|apag|remov|exclu|delet|retir|"
    r"tir[ae]|limp|esquec|corrij|guard|coloc|inclu|troc|mud)\w*"
)


# "na memória", "da minha memória", "em sua memória"
_LOCAL_MEMORIA = re.compile(
    r"\b(?:na|da|em|de)\s+(?:sua\s+|minha\s+)?memoria\b"
)

# A frase precisa COMEÇAR com um verbo de comando (após palavras de apoio).
_INICIO_IMPERATIVO = re.compile(
    r"^(?:(?:certo|ok|entao|agora|e|por favor|pode|poderia|pyxie)\s+)*"
    r"(?:salve|salva|salvar|anote|anota|anotar|registre|registra|registrar|"
    r"adicione|adiciona|adicionar|atualize|atualiza|atualizar|altere|altera|alterar|"
    r"apague|apaga|apagar|remova|remove|remover|exclua|exclui|excluir|"
    r"delete|deleta|deletar|retire|tire|limpe|esqueca|corrija|guarde|guarda|"
    r"coloque|inclua|troque|mude)\b"
)


# "se lembre que ...", "lembre que ...", "memorize que ...", "esqueça que ..."
_COMANDO_QUE = re.compile(
    r"^(?:(?:ok|entao|agora|por favor|pyxie)\s+)*"
    r"(?:se\s+lembre|lembre|memorize|guarde|anote|se\s+esqueca|esqueca|recorde)\s+que\b"
)


def eh_pedido_de_edicao(msg_norm: str) -> bool:
    # "se lembre que X", "esqueça que X": comando direto sobre a memória.
    if _COMANDO_QUE.match(msg_norm.strip()):
        return True

    # Citou o JSON ou a memória fixa: basta ter um verbo de escrita.
    if _LOCAIS.search(msg_norm) and _VERBOS.search(msg_norm):
        return True

    # Citou só "memória": a frase precisa começar com o comando.
    return bool(_LOCAL_MEMORIA.search(msg_norm)) and bool(
        _INICIO_IMPERATIVO.match(msg_norm.strip())
    )

def eh_pedido_de_desfazer(msg_norm: str) -> bool:
    return bool(re.search(r"\bdesfa[cz]\w*", msg_norm)) and (
        "json" in msg_norm or "memoria fixa" in msg_norm
    )


# =============================================================
# LEITURA
# =============================================================


def _carregar_estrito_remoto() -> dict:
    try:
        bruto = _cmd("GET", CHAVE)
    except (requests.RequestException, ValueError) as e:
        raise ValueError(f"memória remota indisponível: {e}")

    if bruto is None:
        raise ValueError("memória não encontrada no Redis (rode seed_memory.py)")

    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as e:
        raise ValueError(f"memória remota ilegível: {e}")

    if not isinstance(dados, dict):
        raise ValueError("a memória precisa ser um objeto JSON")

    return dados


def _carregar_estrito_local() -> dict:
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


def carregar_estrito() -> dict:
    """Lê a memória ou levanta ValueError. Usada antes de editar."""
    if _remoto():
        return _carregar_estrito_remoto()
    return _carregar_estrito_local()


def carregar() -> dict:
    """Lê a memória; em caso de erro devolve {} (só para leitura)."""
    try:
        return carregar_estrito()
    except ValueError as e:
        print(f"[memory_json] {e}")
        return {}


# =============================================================
# ESCRITA
# =============================================================


def _gravar_remoto(dados: dict):
    try:
        atual = _cmd("GET", CHAVE)
        if atual:
            _cmd("SET", CHAVE_BAK, atual)  # backup da versão anterior
        _cmd("SET", CHAVE, json.dumps(dados, ensure_ascii=False))
    except (requests.RequestException, ValueError) as e:
        raise ValueError(f"falha ao gravar na memória remota: {e}")


def _gravar_local(dados: dict):
    if ARQUIVO.exists():
        with ARQUIVO.open("rb") as origem, BACKUP.open("wb") as destino:
            destino.write(origem.read())

    fd, tmp = tempfile.mkstemp(dir=str(ARQUIVO.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        os.replace(tmp, ARQUIVO)  # troca atômica
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _gravar(dados: dict):
    if _remoto():
        _gravar_remoto(dados)
    else:
        _gravar_local(dados)

    # Confirma de verdade: lê de volta e compara
    if carregar_estrito() != dados:
        raise ValueError("a gravação não foi confirmada na memória")


def desfazer() -> bool:
    """Restaura a versão anterior ao último salvamento."""
    with _lock:
        if _remoto():
            try:
                bak = _cmd("GET", CHAVE_BAK)
                if not bak:
                    return False
                _cmd("SET", CHAVE, bak)
                _cmd("DEL", CHAVE_BAK)
                return True
            except (requests.RequestException, ValueError) as e:
                print(f"[memory_json] erro ao desfazer: {e}")
                return False

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
            raise ValueError(
                "não guardo senhas, tokens ou chaves (regra da memory_rules)"
            )

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
            descricao = (
                f'"{caminho}" definido como {json.dumps(valor, ensure_ascii=False)}'
            )

        elif acao == "add":
            atual = pai.get(ultimo)
            if atual is None:
                pai[ultimo] = [valor]
            elif isinstance(atual, list):
                if valor not in atual:
                    atual.append(valor)
            elif isinstance(atual, dict):
                raise ValueError(
                    "esse campo é um objeto; use definir em vez de acrescentar"
                )
            else:
                pai[ultimo] = [atual, valor]
            descricao = (
                f'adicionado {json.dumps(valor, ensure_ascii=False)} em "{caminho}"'
            )

        else:  # remove
            if ultimo not in pai:
                raise ValueError("esse caminho não existe")
            if valor is not None and isinstance(pai[ultimo], list):
                if valor not in pai[ultimo]:
                    raise ValueError("esse item não está na lista")
                pai[ultimo].remove(valor)
                descricao = (
                    f'removido {json.dumps(valor, ensure_ascii=False)} de "{caminho}"'
                )
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

def confirmacao_natural(op: dict) -> str:
    """Mensagem amigável para o usuário depois de editar a memória."""
    acao = op.get("op")
    valor = op.get("value")
    texto = valor if isinstance(valor, str) and len(valor) <= 120 else None

    if acao == "remove":
        if texto:
            return f'Pronto, tirei "{texto}" da minha memória.'
        return "Pronto, apaguei essa informação da minha memória."

    if texto:
        return f'Anotado! Vou me lembrar disso: "{texto}".'
    return "Anotado! Guardei isso na minha memória."