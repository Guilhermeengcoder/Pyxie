# =============================================================
# core/memory/short_term.py — Memória de Curto Prazo (STM)
# PYXIE AI
#
# Responsabilidades:
#   - Janela deslizante das últimas N mensagens
#   - Memória seletiva: descarta mensagens de baixo peso
#   - Expiração por TTL em RAM (sem banco)
#   - Contexto formatado pronto para injetar no LLM
# =============================================================

import time
from typing import Optional
from dataclasses import dataclass, field


# =============================================================
# ROLES VÁLIDOS
# =============================================================

VALID_ROLES = {"user", "assistant", "system"}


# =============================================================
# PESOS POR TIPO DE CONTEÚDO
# Quanto maior o score, mais importante a mensagem é.
# Mensagens abaixo de SCORE_MINIMO são descartadas do contexto
# enviado ao Ollama — mas ainda ficam no histórico interno
# por no mínimo MIN_TURNS_PROTEGIDOS turnos.
# =============================================================

SCORE_MINIMO        = 2   # abaixo disso, descarta do contexto
MIN_TURNS_PROTEGIDOS = 2   # as N últimas mensagens nunca são descartadas


def pontuar_mensagem(role: str, content: str) -> int:
    """
    Pontua a importância de uma mensagem para o contexto.
    Retorna um inteiro — quanto maior, mais importante.
    """
    content = content.lower()
    score = 0

    # Respostas do assistente longas tendem a ter mais informação
    if role == "assistant" and len(content) > 200:
        score += 2

    # Fatos declarados pelo usuário
    if any(p in content for p in ["quero", "preciso", "meu", "minha", "vou", "tenho"]):
        score += 2

    # Preferências e requisitos
    if any(p in content for p in ["gosto", "prefiro", "não quero", "deve", "precisa"]):
        score += 2

    # Informações técnicas ou específicas
    if any(p in content for p in ["cm", "metros", "kg", "watts", "volts", "tamanho", "altura"]):
        score += 3

    # Perguntas de passagem — baixo valor após respondidas
    if content.endswith("?") and len(content) < 80:
        score -= 2

    # Confirmações e respostas curtas sem conteúdo
    if len(content) < 30:
        score -= 1

    # Saudações dentro da conversa
    if any(p in content for p in ["oi", "olá", "tudo bem", "obrigado", "ok", "entendi"]):
        score -= 2

    # Perguntas genéricas do assistente pedindo mais detalhes
    if role == "assistant" and content.count("?") >= 2:
        score -= 1

    return score


# =============================================================
# ESTRUTURA DE MENSAGEM
# =============================================================

@dataclass
class Message:
    role:      str
    content:   str
    score:     int   = 0      # importância calculada na inserção
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# =============================================================
# SHORT TERM MEMORY
# =============================================================

class ShortTermMemory:

    def __init__(
        self,
        max_messages: int = 10,
        ttl_minutes:  int = 30,
        summarizer=None,
        max_summary_chars: int = 1200,
    ):
        self.max_messages      = max_messages
        self.ttl_seconds       = ttl_minutes * 60
        self._summarizer       = summarizer
        self._max_summary_chars = max_summary_chars

        self._messages: list[Message] = []
        self._summary:  str           = ""
        self._last_interaction: float = time.time()

    # ----------------------------------------------------------
    # ESCRITA
    # ----------------------------------------------------------

    def add_message(self, role: str, content: str):
        if role not in VALID_ROLES:
            raise ValueError(f"Role inválido: '{role}'. Use: {VALID_ROLES}")

        if not content or not content.strip():
            return

        score = pontuar_mensagem(role, content)

        self._messages.append(Message(
            role=role,
            content=content.strip(),
            score=score,
        ))

        self._last_interaction = time.time()
        self._manage_window()

    # ----------------------------------------------------------
    # GERENCIAMENTO DA JANELA
    # ----------------------------------------------------------

    def _manage_window(self):
        if len(self._messages) > self.max_messages:
            self._compress()

    def _compress(self):
        keep = max(3, int(self.max_messages * 0.5))
        old    = self._messages[:-keep]
        recent = self._messages[-keep:]

        if not old:
            return

        old_dicts = [m.to_dict() for m in old]

        if self._summarizer:
            try:
                new_summary = self._summarizer(
                    previous_summary=self._summary,
                    new_messages=old_dicts
                )
            except TypeError:
                new_summary = self._summarizer(old_dicts)
        else:
            new_summary = self._basic_summary(old)

        self._summary  = self._trim_summary(new_summary)
        self._messages = recent

    # ----------------------------------------------------------
    # RESUMO BASE
    # ----------------------------------------------------------

    @staticmethod
    def _basic_summary(messages: list[Message]) -> str:
        lines = []
        for m in messages:
            prefix  = "Usuário" if m.role == "user" else "PYXIE"
            snippet = m.content[:120]
            if len(m.content) > 120:
                snippet += "..."
            lines.append(f"{prefix}: {snippet}")

        return "Resumo do início da conversa: " + " | ".join(lines)

    def _trim_summary(self, summary: str) -> str:
        if len(summary) <= self._max_summary_chars:
            return summary
        return "..." + summary[-self._max_summary_chars:]

    # ----------------------------------------------------------
    # CONTEXTO SELETIVO — coração da memória seletiva
    # ----------------------------------------------------------

    def get_context(self) -> list[dict]:
        """
        Retorna o histórico completo sem filtragem.
        Usado internamente e para diagnóstico.
        """
        context = []
        if self._summary:
            context.append({"role": "system", "content": self._summary})
        context.extend(m.to_dict() for m in self._messages)
        return context

    def get_context_seletivo(self, max_chars: int = 1200) -> list[dict]:
        """
        Retorna contexto filtrado para enviar ao Ollama.

        Regras:
        1. As MIN_TURNS_PROTEGIDOS últimas mensagens sempre entram
           (independente do score) — garantem coerência imediata.
        2. Mensagens mais antigas só entram se score >= SCORE_MINIMO.
        3. O total de caracteres não ultrapassa max_chars.
        """
        context   = []
        total_chars = 0

        # Separa mensagens protegidas (recentes) das candidatas (antigas)
        protegidas  = self._messages[-MIN_TURNS_PROTEGIDOS:]
        candidatas  = self._messages[:-MIN_TURNS_PROTEGIDOS]

        # Filtra candidatas por score
        relevantes = [m for m in candidatas if m.score >= SCORE_MINIMO]

        # Monta lista final: relevantes antigas + recentes protegidas
        selecionadas = relevantes + list(protegidas)

        # Adiciona resumo se existir e couber
        if self._summary:
            resumo_chars = len(self._summary)
            if total_chars + resumo_chars <= max_chars:
                context.append({"role": "system", "content": self._summary})
                total_chars += resumo_chars

        # Adiciona mensagens selecionadas respeitando o limite de chars
        for m in selecionadas:
            msg_chars = len(m.content)
            if total_chars + msg_chars > max_chars:
                # Se for uma mensagem protegida, trunca em vez de descartar
                if m in protegidas:
                    truncado = m.content[:max_chars - total_chars - 3] + "..."
                    context.append({"role": m.role, "content": truncado})
                break
            context.append(m.to_dict())
            total_chars += msg_chars

        return context

    # ----------------------------------------------------------
    # LEITURA
    # ----------------------------------------------------------

    def get_last_user_message(self) -> Optional[str]:
        for m in reversed(self._messages):
            if m.role == "user":
                return m.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        for m in reversed(self._messages):
            if m.role == "assistant":
                return m.content
        return None

    # ----------------------------------------------------------
    # CONTROLE DE SESSÃO
    # ----------------------------------------------------------

    def is_expired(self) -> bool:
        return (time.time() - self._last_interaction) > self.ttl_seconds

    def clear(self):
        self._messages         = []
        self._summary          = ""
        self._last_interaction = time.time()

    # ----------------------------------------------------------
    # DIAGNÓSTICO
    # ----------------------------------------------------------

    def debug_scores(self):
        """Imprime o score de cada mensagem no histórico — útil para tunar os pesos."""
        for i, m in enumerate(self._messages):
            prefix = "U" if m.role == "user" else "P"
            print(f"[STM] [{prefix}] score={m.score:+d} | {m.content[:60]}")

    def __repr__(self) -> str:
        mins_idle = (time.time() - self._last_interaction) / 60
        return (
            f"ShortTermMemory("
            f"messages={len(self._messages)}/{self.max_messages}, "
            f"has_summary={bool(self._summary)}, "
            f"idle={mins_idle:.1f}min)"
        )