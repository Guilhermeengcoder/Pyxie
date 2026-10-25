-- Registro de cada geração de imagem
CREATE TABLE IF NOT EXISTS geracoes_imagem (
    id               BIGSERIAL PRIMARY KEY,
    imagem_id        CHAR(32) UNIQUE NOT NULL,
    chat_id          TEXT,
    projeto_id       BIGINT,
    criada_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
    servico          TEXT NOT NULL DEFAULT 'cloudflare',
    modelo           TEXT NOT NULL,
    operacao         TEXT NOT NULL DEFAULT 'texto_para_imagem',
    prompt_original  TEXT,
    prompt_enviado   TEXT,
    resultado        TEXT NOT NULL,          -- 'ok' ou 'erro'
    erro             TEXT,
    etapas           INT,                    -- num_steps
    largura          INT,
    altura           INT,
    neuronios        NUMERIC,                -- NULL quando não confirmado
    custo_usd        NUMERIC,                -- NULL quando não confirmado
    arquivo_chave    TEXT                    -- chave no R2
);

CREATE INDEX IF NOT EXISTS idx_geracoes_criada ON geracoes_imagem (criada_em DESC);

-- Projetos (abas permanentes com memória contínua)
CREATE TABLE IF NOT EXISTS projetos (
    id           BIGSERIAL PRIMARY KEY,
    nome         TEXT NOT NULL,
    instrucoes   TEXT NOT NULL DEFAULT '',
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projeto_mensagens (
    id          BIGSERIAL PRIMARY KEY,
    projeto_id  BIGINT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    papel       TEXT NOT NULL CHECK (papel IN ('user','assistant')),
    conteudo    TEXT NOT NULL,
    criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_msgs_projeto ON projeto_mensagens (projeto_id, id);


CREATE TABLE IF NOT EXISTS projeto_arquivos (
    id           BIGSERIAL PRIMARY KEY,
    projeto_id   BIGINT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    nome         TEXT NOT NULL,
    conteudo     TEXT NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_projeto_arquivo_nome UNIQUE (projeto_id, nome)
);
