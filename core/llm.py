import importlib
import threading

from core import llm_config
from core.llm_erros import ErroLLM, ErroCota, ErroIndisponivel


# Só estes provedores podem receber a memória fixa (JSON do Redis)
# e pedidos de edição de memória. O Gemini (plano gratuito) pode
# usar e revisar prompts, então fica de fora.
PROVEDORES_CONFIAVEIS = {"groq"}

# Ordem de tentativa no modo Auto.
ORDEM_AUTO = ["groq", "gemini"]

AVISO_RESERVA = (
    "Respondi pelo modo reserva (Gemini): "
    "sem acesso à minha memória fixa."
)

# Registro, por requisição, de quais provedores responderam.
# A API chama iniciar_rastreio() no começo de cada pedido e lê
# aviso_da_requisicao() no fim. Sem iniciar_rastreio() (ex.: um
# teste), nada é registrado e nada quebra.
_req = threading.local()


def iniciar_rastreio():
    _req.usados = []


_ultimo_provedor = None  # último que respondeu neste processo (painel no Auto)


def _registrar_uso(nome: str):
    global _ultimo_provedor
    _ultimo_provedor = nome

    usados = getattr(_req, "usados", None)
    if usados is not None:
        usados.append(nome)


def provedor_do_painel() -> str:
    """Qual provedor o painel de uso deve mostrar agora."""
    modo = llm_config.obter_modo()
    if modo == "auto":
        return _ultimo_provedor or ORDEM_AUTO[0]
    return modo


def aviso_da_requisicao():
    """Aviso se algum provedor sem confiança respondeu neste pedido."""
    for nome in getattr(_req, "usados", []):
        aviso = aviso_do_provedor(nome)
        if aviso:
            return aviso
    return None

# Cada provedor: módulo e função de texto; imagem é opcional.
# Os módulos só são importados quando o provedor é usado, então
# a falta de uma chave (ex.: GEMINI_API_KEY) não derruba o app.
# Para um novo provedor, acrescente uma entrada aqui.
_PROVEDORES = {
    "groq": {
        "modulo": "modules.groq_ai",
        "texto": "perguntar_groq",
        "modulo_imagem": "modules.groq_vision",
        "imagem": "perguntar_groq_imagem",
    },
    "gemini": {
        "modulo": "modules.gemini_ai",
        "texto": "perguntar_gemini",
    },
    "ollama": {
        "modulo": "modules.ollama_ai",
        "texto": "perguntar_ollama",
    },
}


def _ordem(modo: str) -> list:
    if modo == "auto":
        return list(ORDEM_AUTO)
    return [modo]


def provedor_ativo() -> str:
    """Modo atual: 'groq', 'gemini' ou 'auto'."""
    return llm_config.obter_modo()


def provedor_confiavel() -> bool:
    """O modo atual pode usar algum provedor de confiança?"""
    return any(
        p in PROVEDORES_CONFIAVEIS
        for p in _ordem(llm_config.obter_modo())
    )


def aviso_do_provedor(nome: str):
    """Texto de aviso quando a resposta veio de um provedor sem confiança."""
    return None if nome in PROVEDORES_CONFIAVEIS else AVISO_RESERVA


def _carregar(nome: str, modulo_chave: str, funcao_chave: str):
    """Importa o módulo do provedor só agora e devolve a função."""
    config = _PROVEDORES.get(nome)

    if config is None:
        raise ErroLLM(nome, "provedor desconhecido")

    if funcao_chave not in config:
        raise ErroLLM(nome, "este provedor não suporta essa operação")

    try:
        modulo = importlib.import_module(config[modulo_chave])
        return getattr(modulo, config[funcao_chave])
    except ErroLLM:
        raise
    except Exception as e:
        # Ex.: RuntimeError por falta de chave no .env.
        raise ErroLLM(nome, f"não foi possível carregar: {e}") from e


def perguntar_llm_detalhado(
    pergunta, contexto, memoria_fixa="", sensivel=False
):
    """
    Devolve (texto, provedor_usado).

    contexto     -> histórico da conversa (vai a qualquer provedor)
    memoria_fixa -> memória do Redis (só vai a provedor de confiança)
    sensivel     -> a pergunta contém dados da memória (edição);
                    só provedores de confiança são candidatos
    """
    modo = llm_config.obter_modo()
    ordem = _ordem(modo)

    if sensivel:
        ordem = [p for p in ordem if p in PROVEDORES_CONFIAVEIS]
        if not ordem:
            raise ErroLLM(
                modo, "provedor não confiável para conteúdo sensível"
            )

    if modo == "auto":
        livres = [p for p in ordem if not llm_config.em_pausa(p)]
        tentativas = livres or ordem
    else:
        tentativas = ordem

    primeiro_erro = None

    for nome in tentativas:
        ctx = contexto
        if nome in PROVEDORES_CONFIAVEIS and memoria_fixa:
            ctx = (memoria_fixa + "\n\n" + contexto).strip()

        try:
            funcao = _carregar(nome, "modulo", "texto")
            texto = funcao(pergunta, ctx)
            _registrar_uso(nome)
            return texto, nome

        except (ErroCota, ErroIndisponivel) as erro:
            llm_config.pausar(nome, erro)
            primeiro_erro = primeiro_erro or erro

        except ErroLLM:
            if primeiro_erro is not None:
                break  # o erro útil é o primeiro
            raise

    raise primeiro_erro


def perguntar_llm(pergunta, contexto, memoria_fixa="", sensivel=False):
    texto, _ = perguntar_llm_detalhado(
        pergunta, contexto, memoria_fixa=memoria_fixa, sensivel=sensivel
    )
    return texto


def perguntar_llm_imagem(pergunta, imagem, contexto):
    # Hoje só o Groq tem visão; o passo 7 acrescenta o Gemini.
    funcao = _carregar("groq", "modulo_imagem", "imagem")
    return funcao(pergunta, imagem, contexto)