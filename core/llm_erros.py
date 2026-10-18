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


def mensagem_de_erro_llm(erro) -> str:
    """Texto curto e honesto para mostrar ao usuário."""
    if isinstance(erro, ErroCota):
        return "Atingi o limite de uso do modelo agora. Tente de novo em alguns instantes."
    if isinstance(erro, ErroIndisponivel):
        return "O modelo não está respondendo agora. Tente de novo em alguns instantes."
    return "Não consegui processar isso agora."