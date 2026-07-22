# Parte 2 — Diagnóstico e Tuning de Queries

## Arquivo Principal

- **`TUNING.md`** — Análise completa de 4 queries + questão discursiva

## Resumo Executivo

| Query | Problema | Solução Recomendada | Impacto | Criticidade |
|---|---|---|---|---|
| **Q1: Vendas Diárias** | `date()` função impeça índice | Usar range query `>=...  <...` | 319ms → 10ms | 🔴 Alta |
| **Q2: Fila Pendentes App** | Índice não cobre status+canal | Índice composto: (status, canal, created_at) | 21ms → 2ms | 🟡 Média |
| **Q3: Ranking Clientes** | work_mem=4MB insuficiente | Aumentar para 100-256MB | 3.07s → 0.5s | 🔴 CRÍTICA |
| **Q4: Busca Produtos** | ILIKE com wildcard início | Trigram index (pg_trgm) | 10ms → 2ms | 🟢 Baixa |

## Como Testar

### 1. Verificar Estado Atual

```bash
# Conectar ao PostgreSQL
psql -h localhost -p 5433 -U postgres -d gestor2000

-- Ver índices existentes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename IN ('pedidos', 'produtos')
ORDER BY tablename, indexname;
```

### 2. Rodar EXPLAIN nas Queries Atuais

```sql
-- Q1: Vendas diárias (ANTES)
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE date(created_at) = '2026-05-10';
-- Expected: Seq Scan, ~319ms

-- Q2: Fila pendentes (ANTES)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, cliente_id, total, created_at
FROM pedidos
WHERE status = 'pendente'
  AND canal = 'app'
ORDER BY created_at
LIMIT 200;
-- Expected: Index Scan mas filtra 6.832 linhas, ~21ms

-- Q3: Ranking clientes (ANTES)
EXPLAIN (ANALYZE, BUFFERS)
SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;
-- Expected: Sort em disco, 41 batches, ~3.07s

-- Q4: Busca produtos (ANTES)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
-- Expected: Seq Scan, 10.684ms
```

### 3. Aplicar Otimizações

#### Q1: Range Query Fix

```sql
-- ANTES:
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE date(created_at) = '2026-05-10';

-- DEPOIS:
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE created_at >= '2026-05-10'::timestamp
  AND created_at < '2026-05-11'::timestamp;

-- Verificar: deve usar Index Scan, ~10-15ms
EXPLAIN (ANALYZE, BUFFERS) ...
```

#### Q2: Índice Composto

```sql
-- Criar novo índice (não deleta o antigo)
CREATE INDEX idx_pedidos_status_canal_time 
ON pedidos (status, canal, created_at)
WHERE status IN ('pendente', 'enviado');

-- Reanalizar query (sem mudanças):
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, cliente_id, total, created_at
FROM pedidos
WHERE status = 'pendente'
  AND canal = 'app'
ORDER BY created_at
LIMIT 200;
-- Esperado: 0 rows removed, ~2-3ms
```

#### Q3: Aumentar work_mem

```sql
-- Opção A: Por sessão
SET work_mem = '256MB';

-- Então rodar query
EXPLAIN (ANALYZE, BUFFERS)
SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;
-- Esperado: 1 batch (vs 41), ~400-500ms

-- Opção B: Globalmente (recomendado para batch jobs)
ALTER SYSTEM SET work_mem = '100MB';
SELECT pg_reload_conf();

-- Verificar:
SHOW work_mem;
```

#### Q4: Trigram Index

```sql
-- Ativar extensão
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Criar índice
CREATE INDEX idx_produtos_nome_trgm 
ON produtos USING GIST (nome gist_trgm_ops);

-- Query não muda, mas fica mais rápida:
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
-- Esperado: Index Scan, ~2-3ms
```

### 4. Benchmark Comparativo

```bash
# Criar script de teste:
cat > benchmark.sql << 'EOF'
\timing on

-- Q1
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE created_at >= '2026-05-10'::timestamp
  AND created_at < '2026-05-11'::timestamp;

-- Q2
SELECT id, cliente_id, total, created_at
FROM pedidos
WHERE status = 'pendente'
  AND canal = 'app'
ORDER BY created_at
LIMIT 200;

-- Q3
SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;

-- Q4
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
EOF

# Rodar 3x (warm up cache)
psql -h localhost -p 5433 -U postgres -d gestor2000 -f benchmark.sql
```

## Estimated Impact (After 6 months growth)

| Query | Current (2M) | Projected (3.6M) | W/ Tuning | Improvement |
|---|---|---|---|---|
| Q1 | 319ms | 574ms | 12ms | ✅ 48x |
| Q2 | 21ms | 38ms | 3ms | ✅ 13x |
| Q3 | 3.07s | 5.5s | 0.5s | ✅ 11x |
| Q4 | 10ms | 18ms | 2ms | ✅ 9x |

## Implementation Checklist

### Phase 1: Quick Wins (Week 1)
- [ ] Q1: Reescrever query com range
- [ ] Q4: Criar trigram index
- [ ] Set work_mem=64MB globalmente

### Phase 2: Índices (Week 2)
- [ ] Q2: Criar índice composto
- [ ] Validate com EXPLAIN ANALYZE

### Phase 3: Estrutural (Week 3)
- [ ] Q3: Aumentar work_mem para 256MB em batch jobs
- [ ] Criar summary table para relatórios pesados
- [ ] Implementar table partitioning para `eventos`

### Phase 4: Monitoring (Week 4)
- [ ] Ativar pg_stat_statements
- [ ] Set auto_explain.log_min_duration = 1000ms
- [ ] Monitor com `SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC`

## Próximos Passos

1. Testar otimizações em staging/dev
2. Benchmark com dados reais (ou usar pgbench para gerar volumes)
3. Implementar mudanças no plano de maintenance
4. Monitorar por 2 semanas antes de aplicar globalmente

## Referências PostgreSQL

- [Index Types](https://www.postgresql.org/docs/16/indexes-types.html)
- [Query Planning](https://www.postgresql.org/docs/16/runtime-config-query.html)
- [Table Partitioning](https://www.postgresql.org/docs/16/ddl-partitioning.html)
- [pg_trgm Extension](https://www.postgresql.org/docs/16/pgtrgm.html)
- [Full Text Search](https://www.postgresql.org/docs/16/textsearch.html)

