-- Schema como está em produção hoje (Postgres 16, config ~default, work_mem = 4MB)

CREATE TABLE clientes (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nome        text NOT NULL,
  email       text NOT NULL,
  cidade      text NOT NULL,
  uf          char(2) NOT NULL,
  criado_em   timestamptz NOT NULL
);
-- 200.000 linhas

CREATE TABLE produtos (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nome        text NOT NULL,
  categoria   text NOT NULL,
  preco       numeric(10,2) NOT NULL,
  ativo       boolean NOT NULL DEFAULT true
);
-- 20.000 linhas

CREATE TABLE pedidos (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cliente_id  bigint NOT NULL REFERENCES clientes(id),
  status      text NOT NULL,          -- pago 55% | enviado 20% | cancelado 15% | pendente 10%
  canal       text NOT NULL,          -- site 50% | app 25% | marketplace 25%
  total       numeric(12,2) NOT NULL,
  created_at  timestamptz NOT NULL
);
-- 2.000.000 linhas, ~18 meses de histórico

CREATE TABLE itens_pedido (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pedido_id   bigint NOT NULL REFERENCES pedidos(id),
  produto_id  bigint NOT NULL REFERENCES produtos(id),
  quantidade  int NOT NULL,
  preco_unit  numeric(10,2) NOT NULL,
  criado_em   timestamptz NOT NULL
);
-- 4.000.000 linhas

CREATE TABLE eventos (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pedido_id   bigint,
  tipo        text NOT NULL,
  payload     jsonb,
  criado_em   timestamptz NOT NULL DEFAULT now()
);
-- vazia hoje; ver questão discursiva

-- Índices existentes hoje (além das PKs):
CREATE INDEX idx_pedidos_status     ON pedidos (status);
CREATE INDEX idx_pedidos_created_at ON pedidos (created_at);
CREATE INDEX idx_produtos_nome      ON produtos (nome);
CREATE INDEX idx_itens_pedido_fk    ON itens_pedido (pedido_id);
