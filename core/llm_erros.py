# =============================================================
# core/llm_erros.py — Erros dos provedores de IA
#
# Todo provedor (Groq, Gemini, e futuramente Cerebras) traduz as
# falhas dele para estas exceções. Assim o resto do código não
# precisa conhecer o SDK de cada um, e o modo Auto sabe quando
# vale a pena tentar outro provedor.
# =============================================================


class ErroLLM(Exception):
    """Falha genérica de um provedor (chave inválida, modelo inexistente...)."""

    def __init__(self, provedor: str, detalhe: str = "", espera_s=None):
        super().__init__(f"[{provedor}] {detalhe}")
        self.provedor = provedor
        self.detalhe = detalhe
        # Segundos até poder tentar de novo, quando o provedor informa.
        self.espera_s = espera_s


class ErroCota(ErroLLM):
    """Limite de uso atingido (HTTP 429)."""


class ErroIndisponivel(ErroLLM):
    """Provedor fora do ar: timeout, sem conexão ou erro 5xx."""


class ErroEntradaGrande(ErroLLM):
    """Pedido maior que o limite do provedor (HTTP 413).

    Não é cota: esperar não resolve, então o provedor NÃO é pausado.
    """


class ErroSegredo(ErroLLM):
    """O conteúdo parece ter senha ou chave e não pode ir a este provedor."""


def mensagem_de_erro_llm(erro) -> str:
    """Texto curto e honesto para mostrar ao usuário."""
    if isinstance(erro, ErroSegredo):
        return (
            "Encontrei algo que parece uma senha ou chave de acesso no conteúdo "
            "e não o enviei ao modelo reserva. Remova esse trecho e tente de novo."
        )
    if isinstance(erro, ErroEntradaGrande):
        return (
            "Esse conteúdo é grande demais para o modelo agora. "
            "Tente enviar uma parte menor."
        )
    if isinstance(erro, ErroCota):
        return "Atingi o limite de uso do modelo agora. Tente de novo em alguns instantes."
    if isinstance(erro, ErroIndisponivel):
        return "O modelo não está respondendo agora. Tente de novo em alguns instantes."
    return "Não consegui processar isso agora."