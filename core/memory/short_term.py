# =============================================================
# core/memory/short_term.py — Memória de Curto Prazo (STM)
# PYXIE AI
#
# Responsabilidades:
#   - Guardar a conversa de UM chat (um arquivo por chat_id)
#   - Persistir em disco (data/stm/<chat_id>.json)
#   - Contexto formatado pronto para injetar no LLM (com teto)
#
# A STM guarda a conversa inteira no arquivo, sem resumo e sem
# expiração. O que vai ao LLM é limitado por LIMITE_CONTEXTO_CHARS.
# =============================================================

import json
import os
import re
import time
from typing import Optional
from dataclasses import dataclass, field


# =============================================================
# PERSISTÊNCIA — UM ARQUIVO POR CHAT
# =============================================================

PASTA_STM = os.getenv("PYXIE_STM_DIR", "data/stm")

# Teto de caracteres do histórico enviado ao LLM (o arquivo guarda tudo).
# Use None para enviar tudo.
LIMITE_CONTEXTO_CHARS = 6000


def _caminho_stm(chat_id):
    if not chat_id:
        return None
    # chat_id vem do navegador: só letras, números, _ e -
    nome = re.sub(r"[^A-Za-z0-9_-]", "_", str(chat_id))[:80]
    return os.path.join(PASTA_STM, f"{nome}.json")


def apagar_historico(chat_id):
    caminho = _caminho_stm(chat_id)
    if caminho and os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError as e:
            print(f"[STM] erro ao apagar histórico: {e}")


# =============================================================
# ROLES VÁLIDOS
# =============================================================

VALID_ROLES = {"user", "assistant", "system"}


# =============================================================
# PESOS POR TIPO DE CONTEÚDO
# Quanto maior o score, mais importante a mensagem é.
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
        chat_id: Optional[str] = None,
        max_messages: int = 10,
        ttl_minutes:  int = 30,
        summarizer=None,
        max_summary_chars: int = 1200,
    ):
        # Sem chat_id, a STM funciona só em RAM (nada é lido nem gravado)
        self._arquivo = _caminho_stm(chat_id)

        self.max_messages       = max_messages
        self.ttl_seconds        = ttl_minutes * 60
        self._summarizer        = summarizer
        self._max_summary_chars = max_summary_chars

        self._messages: list[Message] = []
        self._summary:  str           = ""
        self._last_interaction: float = time.time()

        # Carrega o histórico deste chat (se existir)
        self._carregar()

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
        self._salvar()

    # ----------------------------------------------------------
    # GERENCIAMENTO DA JANELA
    # ----------------------------------------------------------

    def _manage_window(self):
        # DESATIVADO: sem compressão, nada é descartado.
        pass

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
    # CONTEXTO
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

    def get_context_seletivo(self, max_chars=None, excluir_ultima: bool = True) -> list[dict]:
        """
        Retorna o histórico recente da conversa, respeitando o teto
        LIMITE_CONTEXTO_CHARS (max_chars é aceito só por compatibilidade
        e é ignorado).

        excluir_ultima=True deixa de fora a mensagem atual do usuário,
        que já é enviada separadamente ao LLM.
        """
        msgs = self._messages[:-1] if excluir_ultima else self._messages
        limite = LIMITE_CONTEXTO_CHARS

        if limite is None:
            return [m.to_dict() for m in msgs]

        escolhidas, total = [], 0

        for m in reversed(msgs):          # das mais recentes para as antigas
            total += len(m.content)
            if total > limite:
                break
            escolhidas.append(m.to_dict())

        return list(reversed(escolhidas))
    
    # ----------------------------------------------------------
    # PERSISTÊNCIA EM DISCO
    # ----------------------------------------------------------

    def _salvar(self):
        if not self._arquivo:
            return

        try:
            os.makedirs(os.path.dirname(self._arquivo), exist_ok=True)

            with open(self._arquivo, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "role":      m.role,
                            "content":   m.content,
                            "score":     m.score,
                            "timestamp": m.timestamp,
                        }
                        for m in self._messages
                    ],
                    f, ensure_ascii=False, indent=2
                )
        except Exception as e:
            print(f"[STM] erro ao salvar: {e}")

    def _carregar(self):
        if not self._arquivo:
            return

        try:
            with open(self._arquivo, encoding="utf-8") as f:
                self._messages = [Message(**d) for d in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[STM] erro ao carregar: {e}")

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
    
    
    def remover_ultima_interacao(self) -> bool:
        """
        Remove a última resposta do assistente e a pergunta
        imediatamente anterior, se houver.

        Retorna True se encontrou e removeu uma resposta.
        """
        if not self._messages:
            return False

        # A última mensagem precisa ser uma resposta do assistente.
        if self._messages[-1].role != "assistant":
            return False

        self._messages.pop()

        # Remove a pergunta que originou essa resposta,
        # desde que seja a mensagem imediatamente anterior.
        if self._messages and self._messages[-1].role == "user":
            self._messages.pop()

        self._salvar()
        return True


    # ----------------------------------------------------------
    # CONTROLE DE SESSÃO
    # ----------------------------------------------------------

    def is_expired(self) -> bool:
        # A conversa nunca expira.
        return False

    def clear(self):
        self._messages         = []
        self._summary          = ""
        self._last_interaction = time.time()
        self._salvar()

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
            f"messages={len(self._messages)}, "
            f"has_summary={bool(self._summary)}, "
            f"idle={mins_idle:.1f}min)"
        )