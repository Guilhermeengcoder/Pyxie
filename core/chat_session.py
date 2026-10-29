import time
import threading

from core.context import Context
from core.memory.short_term import ShortTermMemory, apagar_historico


class ChatSession:
    """Tudo que pertence a UM chat: STM + contexto. Nada é compartilhado."""

    def __init__(self, chat_id: str):
        self.stm = ShortTermMemory(chat_id=chat_id)
        self.chat_id   = chat_id
        self.context   = Context()
        self.context_anterior = None
        self.ultima_pergunta = None
        self.last_used = time.time()
        self.imagem_pendente = None   # id da imagem gerada nesta resposta
        self.restrito = False   # canal de voz: sem memória fixa

        # Última descrição usada para gerar imagem (permite refinar:
        # "deixa as asas mais claras" reaproveita o pedido anterior).
        self.ultima_descricao_imagem = None

        # Dados necessários para regenerar uma resposta da IA.
        self.regeneracao_pergunta = None
        self.regeneracao_contexto = None
        self.regeneracao_memoria_fixa = ""
        self.regeneracao_leve = False

    def touch(self):
        self.last_used = time.time()


class SessionManager:

    def __init__(self, ttl_minutes: int = 30, max_sessions: int = 100):
        self._sessions: dict[str, ChatSession] = {}
        self._lock         = threading.Lock()
        self._ttl_seconds  = ttl_minutes * 60
        self._max_sessions = max_sessions

    def get(self, chat_id: str) -> ChatSession:
        chat_id = (chat_id or "default").strip()

        with self._lock:
            self._purge()

            sessao = self._sessions.get(chat_id)
            if sessao is None:
                sessao = ChatSession(chat_id)
                self._sessions[chat_id] = sessao

            sessao.touch()
            return sessao

    def delete(self, chat_id: str) -> bool:
        with self._lock:
            existia = self._sessions.pop(chat_id, None) is not None
        apagar_historico(chat_id)
        return existia

    def _purge(self):
        agora = time.time()

        # remove sessões inativas
        expiradas = [
            cid for cid, s in self._sessions.items()
            if agora - s.last_used > self._ttl_seconds
        ]
        for cid in expiradas:
            del self._sessions[cid]

        # limite de segurança: remove as mais antigas
        while len(self._sessions) > self._max_sessions:
            mais_antiga = min(self._sessions, key=lambda c: self._sessions[c].last_used)
            del self._sessions[mais_antiga]