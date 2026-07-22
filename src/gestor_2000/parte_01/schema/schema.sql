-- ============================================================================
-- SCHEMA: Migração Gestor2000 → Postgres 16
--
-- Estratégia:
-- 1. Validação e normalização já no banco (constraints)
-- 2. Rejeições vão para arquivos de quarentena
-- 3. Idempotência: CREATE TABLE IF NOT EXISTS, DELETE depois carrega tudo
-- ============================================================================

-- ============================================================================
-- 1. TABELA: CLIENTES
-- ============================================================================
CREATE TABLE IF NOT EXISTS clientes (
    -- ID legado do Gestor2000 (chave natural)
    id_legado INT PRIMARY KEY,

    -- CPF normalizado (11 dígitos, sem pontuação)
    -- UNIQUE para evitar duplicatas
    cpf VARCHAR(11) NOT NULL UNIQUE,

    -- Nome em title case (padronizado no pipeline)
    nome VARCHAR(255) NOT NULL,

    -- Email validado (não aceita NULL ou formato inválido)
    -- Decisão: Apenas emails válidos entram. Ausência ou inválidos → quarentena
    -- Validação: deve ter @ e .
    email VARCHAR(255) NOT NULL,

    -- Cidade normalizada (title case + trim)
    cidade VARCHAR(100) NOT NULL,

    -- Data de cadastro padronizada (ISO 8601)
    dt_cadastro DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clientes_cpf ON clientes(cpf);
CREATE INDEX IF NOT EXISTS idx_clientes_dt_cadastro ON clientes(dt_cadastro);


-- ============================================================================
-- 2. TABELA: PEDIDOS
-- ============================================================================
CREATE TABLE IF NOT EXISTS pedidos (
    -- Número do pedido é chave natural (vem do legado)
    num_pedido BIGINT PRIMARY KEY,

    -- FK para clientes (CPF normalizado)
    -- Pedidos órfãos (sem cliente) vão para quarentena
    cpf_cliente VARCHAR(11) NOT NULL,
    CONSTRAINT fk_pedidos_cliente
        FOREIGN KEY (cpf_cliente)
        REFERENCES clientes(cpf)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    -- Status normalizado para 4 estados (PAGO, PENDENTE, CANCELADO, ENVIADO)
    -- 12 variações nos dados originais → mapeadas para esses 4
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('PAGO', 'PENDENTE', 'CANCELADO', 'ENVIADO')),

    -- Valor total em reais (precisão monetária: 2 casas)
    -- Dados originais: misturado (vírgula vs ponto como separador decimal)
    -- NUMERIC(18,2) garante precisão, sem problemas de arredondamento
    valor_total NUMERIC(18,2) NOT NULL CHECK (valor_total > 0),

    -- Data do pedido (ISO 8601)
    dt_pedido DATE NOT NULL,

    -- Canal de origem normalizado (site, app, marketplace)
    -- Dados originais: 5 variações de case
    canal VARCHAR(20) NOT NULL
        CHECK (canal IN ('site', 'app', 'marketplace'))
);

CREATE INDEX IF NOT EXISTS idx_pedidos_cpf_cliente ON pedidos(cpf_cliente);
CREATE INDEX IF NOT EXISTS idx_pedidos_dt_pedido ON pedidos(dt_pedido);
CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_pedidos_canal ON pedidos(canal);


-- ============================================================================
-- 3. TABELA: PAGAMENTOS
-- ============================================================================
CREATE TABLE IF NOT EXISTS pagamentos (
    -- ID único do pagamento
    id_pagto BIGINT PRIMARY KEY,

    -- FK para pedido (num_pedido)
    -- Pagamentos órfãos (pedido inexistente) vão para quarentena
    num_pedido BIGINT NOT NULL,
    CONSTRAINT fk_pagamentos_pedido
        FOREIGN KEY (num_pedido)
        REFERENCES pedidos(num_pedido)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    -- Valor pago em reais (apenas positivos)
    -- NUMERIC(18,2) para precisão monetária
    -- Rejeita valores negativos (reembolsos → quarentena)
    valor_pago NUMERIC(18,2) NOT NULL CHECK (valor_pago > 0),

    -- Método de pagamento normalizado (cartao, pix, boleto)
    -- Dados originais: 6 variações de case
    metodo VARCHAR(20) NOT NULL
        CHECK (metodo IN ('cartao', 'pix', 'boleto')),

    -- Data de pagamento (ISO 8601)
    dt_pagto DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pagamentos_num_pedido ON pagamentos(num_pedido);
CREATE INDEX IF NOT EXISTS idx_pagamentos_dt_pagto ON pagamentos(dt_pagto);
CREATE INDEX IF NOT EXISTS idx_pagamentos_metodo ON pagamentos(metodo);


-- ============================================================================
-- 4. COMENTÁRIOS SOBRE DECISÕES DE DESIGN
-- ============================================================================

COMMENT ON TABLE clientes IS
    'Clientes do legado Gestor2000. CPF normalizado (11 dígitos).
     Email: obrigatório e validado (@ e . presentes).
     Clientes com email ausente ou inválido → quarentena.
     Decisão: Só dados válidos e completos no banco principal.';

COMMENT ON TABLE pedidos IS
    'Pedidos legado. Status normalizado para 4 valores.
     Valor_total tem precisão monetária (dados originais tinham vírgula vs ponto).
     Decisão: Rejeitar pedidos sem cliente referenciado (integridade de negócio).';

COMMENT ON TABLE pagamentos IS
    'Pagamentos legado. Apenas valores positivos (valor_pago > 0).
     Decisão: Rejeitar valores negativos (reembolsos/ajustes → quarentena).
     Pagamentos órfãos (pedido inexistente) vão para quarentena.';
