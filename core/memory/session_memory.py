# =============================================================
# core/memory/short_term.py — Memória de Curto Prazo (STM)
# PYXIE AI — Módulo de Memória Avançada
#
# Responsabilidades:
#   - Armazenar turnos da conversa (usuário + PYXIE)
#   - Rastrear entidades mencionadas (pessoa, lugar, objeto, etc.)
#   - Registrar intenções detectadas por turno
#   - Registrar sentimento/tom por turno
#
# Expiração Híbrida:
#   - Por tempo  → TTL de 30 min sem interação (configurável)
#   - Por volume → máximo de 20 turnos por sessão (configurável)
#
# Sessão:
#   - Cada conversa gera um session_id único (UUID4)
#   - Sessões expiradas são limpas automaticamente via _gc()
# =============================================================

import sqlite3
import uuid
import os
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


# =============================================================
# CONFIGURAÇÃO
# =============================================================

STM_DB_PATH     = os.path.join("data", "stm.db")
STM_TTL_MINUTES = 30     # sessão expira após X min sem interação
STM_MAX_TURNS   = 20     # máximo de turnos mantidos por sessão


# =============================================================
# ENUMS — categorias fixas para consistência
# =============================================================

class EntityType(str, Enum):
    PERSON  = "person"
    PLACE   = "place"
    OBJECT  = "object"
    CONCEPT = "concept"
    TIME    = "time"
    OTHER   = "other"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL  = "neutral"
    CURIOUS  = "curious"
    CONFUSED = "confused"


class IntentCategory(str, Enum):
    QUESTION    = "question"
    COMMAND     = "command"
    GREETING    = "greeting"
    FAREWELL    = "farewell"
    INFORMATION = "information"
    MEMORY_OP   = "memory_op"
    SEARCH      = "search"
    CALCULATION = "calculation"
    UNKNOWN     = "unknown"


# =============================================================
# DATACLASSES — estruturas de dados tipadas
# =============================================================

@dataclass
class Turn:
    session_id:  str
    user_input:  str
    pyxie_response: str
    intent:      IntentCategory
    sentiment:   Sentiment
    created_at:  datetime = field(default_factory=datetime.now)
    turn_id:     Optional[int] = None


@dataclass
class Entity:
    session_id:   str
    name:         str
    entity_type:  EntityType
    source_turn:  int           # ID do turno onde foi mencionada
    confidence:   float = 1.0   # 0.0 → 1.0
    created_at:   datetime = field(default_factory=datetime.now)
    entity_id:    Optional[int] = None


@dataclass
class Session:
    session_id:  str
    started_at:  datetime
    last_seen:   datetime
    turn_count:  int = 0
    is_active:   bool = True


# =============================================================
# REPOSITÓRIO — acesso ao banco de dados
# =============================================================

class _STMRepository:
    """Camada de acesso ao banco. Não usar diretamente — use ShortTermMemory."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialize()

    # ----------------------------------------------------------
    # CONEXÃO
    # ----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # mais rápido para leitura concorrente
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ----------------------------------------------------------
    # INICIALIZAÇÃO DO SCHEMA
    # ----------------------------------------------------------

    def _initialize(self):
        conn = self._connect()

        conn.executescript("""
            -- Sessões de conversa
            CREATE TABLE IF NOT EXISTS stm_sessions (
                session_id  TEXT PRIMARY KEY,
                started_at  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                turn_count  INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1
            );

            -- Turnos da conversa
            CREATE TABLE IF NOT EXISTS stm_turns (
                turn_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT    NOT NULL REFERENCES stm_sessions(session_id),
                user_input      TEXT    NOT NULL,
                pyxie_response  TEXT    NOT NULL,
                intent          TEXT    NOT NULL,
                sentiment       TEXT    NOT NULL,
                created_at      TEXT    NOT NULL
            );

            -- Entidades detectadas
            CREATE TABLE IF NOT EXISTS stm_entities (
                entity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL REFERENCES stm_sessions(session_id),
                name        TEXT    NOT NULL,
                entity_type TEXT    NOT NULL,
                source_turn INTEGER NOT NULL REFERENCES stm_turns(turn_id),
                confidence  REAL    DEFAULT 1.0,
                created_at  TEXT    NOT NULL
            );

            -- Índices para consultas rápidas
            CREATE INDEX IF NOT EXISTS idx_turns_session
                ON stm_turns(session_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_entities_session
                ON stm_entities(session_id, entity_type);

            CREATE INDEX IF NOT EXISTS idx_sessions_active
                ON stm_sessions(is_active, last_seen);
        """)

        conn.commit()
        conn.close()

    # ----------------------------------------------------------
    # SESSÕES
    # ----------------------------------------------------------

    def create_session(self, session_id: str) -> Session:
        now = datetime.now().isoformat()
        conn = self._connect()

        conn.execute("""
            INSERT INTO stm_sessions (session_id, started_at, last_seen, turn_count, is_active)
            VALUES (?, ?, ?, 0, 1)
        """, (session_id, now, now))

        conn.commit()
        conn.close()

        return Session(
            session_id=session_id,
            started_at=datetime.fromisoformat(now),
            last_seen=datetime.fromisoformat(now),
        )

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM stm_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        return Session(
            session_id=row["session_id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            turn_count=row["turn_count"],
            is_active=bool(row["is_active"]),
        )

    def touch_session(self, session_id: str, turn_count: int):
        """Atualiza last_seen e turn_count da sessão."""
        conn = self._connect()
        conn.execute("""
            UPDATE stm_sessions
            SET last_seen = ?, turn_count = ?
            WHERE session_id = ?
        """, (datetime.now().isoformat(), turn_count, session_id))
        conn.commit()
        conn.close()

    def deactivate_session(self, session_id: str):
        conn = self._connect()
        conn.execute(
            "UPDATE stm_sessions SET is_active = 0 WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()
        conn.close()

    # ----------------------------------------------------------
    # TURNOS
    # ----------------------------------------------------------

    def insert_turn(self, turn: Turn) -> int:
        conn = self._connect()
        cursor = conn.execute("""
            INSERT INTO stm_turns
                (session_id, user_input, pyxie_response, intent, sentiment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            turn.session_id,
            turn.user_input,
            turn.pyxie_response,
            turn.intent.value,
            turn.sentiment.value,
            turn.created_at.isoformat(),
        ))
        conn.commit()
        turn_id = cursor.lastrowid
        conn.close()
        return turn_id

    def get_turns(self, session_id: str, limit: int = STM_MAX_TURNS) -> list[Turn]:
        conn = self._connect()
        rows = conn.execute("""
            SELECT * FROM stm_turns
            WHERE session_id = ?
            ORDER BY turn_id DESC
            LIMIT ?
        """, (session_id, limit)).fetchall()
        conn.close()

        return [
            Turn(
                turn_id=r["turn_id"],
                session_id=r["session_id"],
                user_input=r["user_input"],
                pyxie_response=r["pyxie_response"],
                intent=IntentCategory(r["intent"]),
                sentiment=Sentiment(r["sentiment"]),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in reversed(rows)   # retorna em ordem cronológica
        ]

    def count_turns(self, session_id: str) -> int:
        conn = self._connect()
        row = conn.execute(
            "SELECT COUNT(*) as c FROM stm_turns WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()
        return row["c"]

    def delete_oldest_turn(self, session_id: str):
        """Remove o turno mais antigo para manter o limite de volume."""
        conn = self._connect()
        conn.execute("""
            DELETE FROM stm_turns
            WHERE turn_id = (
                SELECT turn_id FROM stm_turns
                WHERE session_id = ?
                ORDER BY turn_id ASC
                LIMIT 1
            )
        """, (session_id,))
        conn.commit()
        conn.close()

    # ----------------------------------------------------------
    # ENTIDADES
    # ----------------------------------------------------------

    def insert_entity(self, entity: Entity) -> int:
        conn = self._connect()
        cursor = conn.execute("""
            INSERT INTO stm_entities
                (session_id, name, entity_type, source_turn, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entity.session_id,
            entity.name.lower(),
            entity.entity_type.value,
            entity.source_turn,
            entity.confidence,
            entity.created_at.isoformat(),
        ))
        conn.commit()
        entity_id = cursor.lastrowid
        conn.close()
        return entity_id

    def get_entities(
        self,
        session_id: str,
        entity_type: Optional[EntityType] = None,
    ) -> list[Entity]:
        conn = self._connect()

        if entity_type:
            rows = conn.execute("""
                SELECT * FROM stm_entities
                WHERE session_id = ? AND entity_type = ?
                ORDER BY confidence DESC, created_at DESC
            """, (session_id, entity_type.value)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM stm_entities
                WHERE session_id = ?
                ORDER BY confidence DESC, created_at DESC
            """, (session_id,)).fetchall()

        conn.close()

        return [
            Entity(
                entity_id=r["entity_id"],
                session_id=r["session_id"],
                name=r["name"],
                entity_type=EntityType(r["entity_type"]),
                source_turn=r["source_turn"],
                confidence=r["confidence"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def get_last_entity(
        self,
        session_id: str,
        entity_type: Optional[EntityType] = None,
    ) -> Optional[Entity]:
        entities = self.get_entities(session_id, entity_type)
        return entities[-1] if entities else None

    # ----------------------------------------------------------
    # GARBAGE COLLECTOR
    # ----------------------------------------------------------

    def gc_expired_sessions(self, ttl_minutes: int):
        """Remove sessões expiradas (sem interação após TTL)."""
        cutoff = (datetime.now() - timedelta(minutes=ttl_minutes)).isoformat()
        conn = self._connect()

        expired = conn.execute("""
            SELECT session_id FROM stm_sessions
            WHERE is_active = 1 AND last_seen < ?
        """, (cutoff,)).fetchall()

        for row in expired:
            sid = row["session_id"]
            conn.execute("DELETE FROM stm_entities WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM stm_turns    WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM stm_sessions WHERE session_id = ?", (sid,))

        conn.commit()
        conn.close()
        return len(expired)


# =============================================================
# INTERFACE PÚBLICA — ShortTermMemory
# =============================================================

class SeassonMemory:
    """
    Interface principal da Memória de Curto Prazo da PYXIE.

    Uso básico:
        session_memory = SessionMemory()
        stm.start_session()

        stm.add_turn(
            user_input="Quem é Elon Musk?",
            pyxie_response="Elon Musk é...",
            intent=IntentCategory.QUESTION,
            sentiment=Sentiment.CURIOUS,
        )

        stm.add_entity("Elon Musk", EntityType.PERSON, confidence=0.98)

        contexto = stm.build_context_prompt()
    """

    def __init__(
        self,
        db_path: str = STM_DB_PATH,
        ttl_minutes: int = STM_TTL_MINUTES,
        max_turns: int = STM_MAX_TURNS,
    ):
        self._repo       = _STMRepository(db_path)
        self._ttl        = ttl_minutes
        self._max_turns  = max_turns
        self._session_id: Optional[str] = None

    # ----------------------------------------------------------
    # GERENCIAMENTO DE SESSÃO
    # ----------------------------------------------------------

    def start_session(self) -> str:
        """Inicia uma nova sessão e retorna o session_id."""
        self._gc()   # limpa sessões expiradas antes de criar uma nova
        self._session_id = str(uuid.uuid4())
        self._repo.create_session(self._session_id)
        return self._session_id

    def resume_session(self, session_id: str) -> bool:
        """
        Retoma uma sessão existente se ainda estiver ativa.
        Retorna True se bem-sucedido, False se expirada/inexistente.
        """
        session = self._repo.get_session(session_id)

        if not session or not session.is_active:
            return False

        # verifica TTL
        elapsed = datetime.now() - session.last_seen
        if elapsed > timedelta(minutes=self._ttl):
            self._repo.deactivate_session(session_id)
            return False

        self._session_id = session_id
        return True

    def end_session(self):
        """Encerra a sessão atual."""
        if self._session_id:
            self._repo.deactivate_session(self._session_id)
            self._session_id = None

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    def _require_session(self):
        if not self._session_id:
            raise RuntimeError(
                "Nenhuma sessão ativa. Chame start_session() ou resume_session() primeiro."
            )

    # ----------------------------------------------------------
    # ESCRITA
    # ----------------------------------------------------------

    def add_turn(
        self,
        user_input: str,
        pyxie_response: str,
        intent: IntentCategory = IntentCategory.UNKNOWN,
        sentiment: Sentiment = Sentiment.NEUTRAL,
    ) -> int:
        """
        Registra um turno de conversa.
        Aplica a expiração híbrida automaticamente.
        Retorna o turn_id gerado.
        """
        self._require_session()

        # --- expiração por volume ---
        count = self._repo.count_turns(self._session_id)
        if count >= self._max_turns:
            self._repo.delete_oldest_turn(self._session_id)

        turn = Turn(
            session_id=self._session_id,
            user_input=user_input,
            pyxie_response=pyxie_response,
            intent=intent,
            sentiment=sentiment,
        )

        turn_id = self._repo.insert_turn(turn)

        # atualiza last_seen (reset do TTL)
        new_count = min(count + 1, self._max_turns)
        self._repo.touch_session(self._session_id, new_count)

        return turn_id

    def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        source_turn: int,
        confidence: float = 1.0,
    ) -> int:
        """
        Registra uma entidade detectada no contexto atual.
        Retorna o entity_id gerado.
        """
        self._require_session()

        entity = Entity(
            session_id=self._session_id,
            name=name,
            entity_type=entity_type,
            source_turn=source_turn,
            confidence=confidence,
        )

        return self._repo.insert_entity(entity)

    # ----------------------------------------------------------
    # LEITURA
    # ----------------------------------------------------------

    def get_turns(self, limit: Optional[int] = None) -> list[Turn]:
        """Retorna os turnos da sessão atual em ordem cronológica."""
        self._require_session()
        return self._repo.get_turns(self._session_id, limit or self._max_turns)

    def get_entities(self, entity_type: Optional[EntityType] = None) -> list[Entity]:
        """Retorna entidades da sessão, opcionalmente filtradas por tipo."""
        self._require_session()
        return self._repo.get_entities(self._session_id, entity_type)

    def get_last_entity(self, entity_type: Optional[EntityType] = None) -> Optional[Entity]:
        """Retorna a última entidade registrada (útil para resolução de pronomes)."""
        self._require_session()
        return self._repo.get_last_entity(self._session_id, entity_type)

    def get_session_info(self) -> Optional[Session]:
        """Retorna metadados da sessão atual."""
        self._require_session()
        return self._repo.get_session(self._session_id)

    # ----------------------------------------------------------
    # GERAÇÃO DE CONTEXTO PARA PROMPT
    # ----------------------------------------------------------

    def build_context_prompt(self, max_turns: int = 5) -> str:
        """
        Gera um bloco de contexto formatado para ser injetado
        no prompt do Ollama/LLM.

        Exemplo de saída:
            === Contexto da Conversa Atual ===
            [Turno 1]
            Usuário: Quem é Elon Musk?
            PYXIE: Elon Musk é...

            Entidades em foco: elon musk (person), tesla (object)
            ===================================
        """
        self._require_session()

        turns    = self.get_turns(limit=max_turns)
        entities = self.get_entities()

        if not turns and not entities:
            return ""

        linhas = ["=== Contexto da Conversa Atual ==="]

        for i, t in enumerate(turns, 1):
            linhas.append(f"\n[Turno {i}]")
            linhas.append(f"Usuário : {t.user_input}")
            linhas.append(f"PYXIE   : {t.pyxie_response}")
            linhas.append(f"Intenção: {t.intent.value} | Tom: {t.sentiment.value}")

        if entities:
            nomes = ", ".join(
                f"{e.name} ({e.entity_type.value})" for e in entities[-5:]
            )
            linhas.append(f"\nEntidades em foco: {nomes}")

        linhas.append("===================================")
        return "\n".join(linhas)

    # ----------------------------------------------------------
    # GARBAGE COLLECTOR
    # ----------------------------------------------------------

    def _gc(self):
        """Executa coleta de sessões expiradas pelo TTL."""
        removed = self._repo.gc_expired_sessions(self._ttl)
        if removed:
            print(f"[STM] GC: {removed} sessão(ões) expirada(s) removida(s).")


# =============================================================
# INSTÂNCIA GLOBAL
# Importar assim em outros módulos:
#   from core.memory.short_term import stm, IntentCategory, Sentiment, EntityType
# =============================================================

# Instância global
session_memory = SeassonMemory()