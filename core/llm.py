import importlib
import threading

from core import llm_config
from core.filtro_segredos import detectar_segredos
from core.llm_erros import (
    ErroLLM,
    ErroCota,
    ErroIndisponivel,
    ErroEntradaGrande,
    ErroSegredo,
)


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

AVISO_GEMINI_MANUAL = (
    "Respondi pelo Gemini: sem acesso à minha memória fixa."
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
        "sem_busca": True,
    },
    "gemini": {
        "modulo": "modules.gemini_ai",
        "texto": "perguntar_gemini",
        "modulo_imagem": "modules.gemini_ai",
        "imagem": "perguntar_gemini_imagem",
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
    """Texto de aviso quando a resposta veio de um provedor sem confiança.

    No Auto é o modo reserva; no modo manual a escolha foi sua,
    então a frase é neutra.
    """
    if nome in PROVEDORES_CONFIAVEIS:
        return None

    if llm_config.obter_modo() == "auto":
        return AVISO_RESERVA

    return AVISO_GEMINI_MANUAL

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
    pergunta, contexto, memoria_fixa="", sensivel=False, leve=False
):
    """
    Devolve (texto, provedor_usado).

    contexto     -> histórico da conversa (vai a qualquer provedor)
    memoria_fixa -> memória do Redis (só vai a provedor de confiança)
    sensivel     -> a pergunta contém dados da memória (edição);
                    só provedores de confiança são candidatos
    leve         -> pedido grande: desliga a busca na web nos
                    provedores que têm essa opção (hoje, o Groq)

    Antes de enviar a um provedor sem confiança, o texto passa pelo
    filtro de segredos; se achar algo, levanta ErroSegredo.
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

        # Provedor sem confiança: nada que pareça senha ou chave sai daqui.
        if nome not in PROVEDORES_CONFIAVEIS:
            achados = detectar_segredos(f"{pergunta}\n{contexto}")
            if achados:
                raise ErroSegredo(
                    nome, "possível segredo: " + ", ".join(achados)
                )

        extras = {}
        if leve and _PROVEDORES.get(nome, {}).get("sem_busca"):
            extras["busca"] = False

        try:
            funcao = _carregar(nome, "modulo", "texto")
            texto = funcao(pergunta, ctx, **extras)
            _registrar_uso(nome)
            return texto, nome

        except (ErroCota, ErroIndisponivel) as erro:
            llm_config.pausar(nome, erro)
            primeiro_erro = primeiro_erro or erro

        except ErroEntradaGrande as erro:
            # Pedido maior que o limite deste provedor: não é cota,
            # então não pausa. No Auto, segue para o próximo.
            primeiro_erro = primeiro_erro or erro

        except ErroLLM:
            if primeiro_erro is not None:
                break  # o erro útil é o primeiro
            raise

    raise primeiro_erro


def perguntar_llm(
    pergunta, contexto, memoria_fixa="", sensivel=False, leve=False
):
    texto, _ = perguntar_llm_detalhado(
        pergunta,
        contexto,
        memoria_fixa=memoria_fixa,
        sensivel=sensivel,
        leve=leve,
    )
    return texto


def perguntar_llm_imagem(pergunta, imagem, contexto):
    """
    Respeita o seletor de modo, como o texto (groq / gemini / auto).

    Privacidade (opção A): um provedor SEM confiança recebe só a imagem
    e a pergunta; o histórico não vai, e a pergunta passa pelo filtro
    de segredos antes. A memória fixa nunca vai em imagem.

    Pausas: imagem não lê nem grava pausas. Os limites do Groq são por
    modelo, e o 429 do modelo de visão não quer dizer que o modelo de
    texto esgotou; pausar o Groq inteiro desviaria o texto para o Gemini.
    """
    modo = llm_config.obter_modo()
    tentativas = [
        p for p in _ordem(modo) if "imagem" in _PROVEDORES.get(p, {})
    ]

    if not tentativas:
        raise ErroLLM(modo, "nenhum provedor deste modo aceita imagem")

    primeiro_erro = None

    for nome in tentativas:
        ctx = contexto

        if nome not in PROVEDORES_CONFIAVEIS:
            ctx = ""  # sem histórico fora dos provedores de confiança

            achados = detectar_segredos(str(pergunta or ""))
            if achados:
                raise ErroSegredo(
                    nome, "possível segredo: " + ", ".join(achados)
                )

        try:
            funcao = _carregar(nome, "modulo_imagem", "imagem")
            texto = funcao(pergunta, imagem, ctx)
            _registrar_uso(nome)
            return texto

        except (ErroCota, ErroIndisponivel, ErroEntradaGrande) as erro:
            primeiro_erro = primeiro_erro or erro

        except ErroLLM:
            if primeiro_erro is not None:
                break  # o erro útil é o primeiro
            raise

    raise primeiro_erro