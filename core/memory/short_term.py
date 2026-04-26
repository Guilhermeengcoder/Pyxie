# =============================================================
# core/memory/short_term.py — Memória de Curto Prazo (STM)
# PYXIE AI
#
# Responsabilidades:
#   - Janela deslizante das últimas N mensagens
#   - Summarização das mensagens antigas (hook para IA)
#   - Expiração por TTL em RAM (sem banco)
#   - Contexto formatado pronto para injetar no LLM
# =============================================================

import time
from typing import Optional
from dataclasses import dataclass, field


# =============================================================
# ROLES VÁLIDOS — evita contexto corrompido no LLM
# =============================================================

VALID_ROLES = {"user", "assistant", "system"}


# =============================================================
# ESTRUTURA DE MENSAGEM
# =============================================================

@dataclass
class Message:
    role:      str
    content:   str
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
        summarizer=None,        # hook: callable(...)
        max_summary_chars: int = 1200,  # 🔥 limite do resumo
    ):
        self.max_messages  = max_messages
        self.ttl_seconds   = ttl_minutes * 60
        self._summarizer   = summarizer
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

        self._messages.append(Message(role=role, content=content.strip()))
        self._last_interaction = time.time()
        self._manage_window()

    # ----------------------------------------------------------
    # GERENCIAMENTO DA JANELA
    # ----------------------------------------------------------

    def _manage_window(self):
        if len(self._messages) > self.max_messages:
            self._compress()

    def _compress(self):
        # 🔥 compressão dinâmica
        keep = max(3, int(self.max_messages * 0.5))

        old    = self._messages[:-keep]
        recent = self._messages[-keep:]

        if not old:
            return

        old_dicts = [m.to_dict() for m in old]

        if self._summarizer:
            try:
                # 🔥 resumo incremental (se suportado)
                new_summary = self._summarizer(
                    previous_summary=self._summary,
                    new_messages=old_dicts
                )
            except TypeError:
                # fallback para summarizer simples
                new_summary = self._summarizer(old_dicts)
        else:
            new_summary = self._basic_summary(old)

        # 🔥 aplica limite de tamanho
        self._summary = self._trim_summary(new_summary)

        self._messages = recent

    # ----------------------------------------------------------
    # RESUMO BASE
    # ----------------------------------------------------------

    @staticmethod
    def _basic_summary(messages: list[Message]) -> str:
        lines = []
        for m in messages:
            prefix = "Usuário" if m.role == "user" else "PYXIE"
            snippet = m.content[:120]
            if len(m.content) > 120:
                snippet += "..."
            lines.append(f"{prefix}: {snippet}")

        return "Resumo do início da conversa: " + " | ".join(lines)

    # ----------------------------------------------------------
    # CONTROLE DE TAMANHO DO SUMMARY
    # ----------------------------------------------------------

    def _trim_summary(self, summary: str) -> str:
        if len(summary) <= self._max_summary_chars:
            return summary

        # mantém o final (mais recente)
        return "..." + summary[-self._max_summary_chars:]

    # ----------------------------------------------------------
    # LEITURA
    # ----------------------------------------------------------

    def get_context(self) -> list[dict]:
        context = []

        if self._summary:
            context.append({
                "role": "system",
                "content": self._summary,
            })

        context.extend(m.to_dict() for m in self._messages)
        return context

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

    def __repr__(self) -> str:
        mins_idle = (time.time() - self._last_interaction) / 60
        return (
            f"ShortTermMemory("
            f"messages={len(self._messages)}/{self.max_messages}, "
            f"has_summary={bool(self._summary)}, "
            f"idle={mins_idle:.1f}min)"
        )