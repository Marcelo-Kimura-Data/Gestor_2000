# Parte 2 — Diagnóstico e Tuning de Queries

**Contexto**: PostgreSQL 16, config ~default (work_mem=4MB), volumes: 2M pedidos, 4M itens, 200k clientes, 20k produtos  
**Negócio**: Cresce ~15% ao mês → O que está ok hoje pode não estar em 6 meses  

---

## Q1: Relatório Diário de Vendas

### Query
```sql
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE date(created_at) = '2026-05-10';
```

### Diagnóstico

**Tempo atual**: 319.346 ms  
**Status**: ❌ Problemático

#### Gargalo Principal
A query usa `date(created_at) = '2026-05-10'`, que **desabilita o índice** `idx_pedidos_created_at`.

**Evidência no plano**:
```
Parallel Seq Scan on pedidos (cost=0.00..31119.00 rows=4167 width=6)
  Filter: (date(created_at) = '2026-05-10'::date)
  Rows Removed by Filter: 665510
  Buffers: shared hit=6829 read=11790  ← 11.790 pages lidas do disco!
```

**Por quê?**
- Índice `idx_pedidos_created_at` é B-tree em `created_at` (tipo `timestamptz`)
- Função `date()` extrai só a data, transforma para `date` type
- PostgreSQL não consegue usar índice quando há função aplicada na coluna indexada
- Força **Seq Scan** de 2M linhas em paralelo (2 workers)
- Filtra depois: 665.510 linhas descartadas

**Parallelization**:
- 2 workers lançados (bom para seq scan)
- Mas ainda precisa ler ~18.600 páginas (11.790 hit + 6.829 read)
- Tempo total: ~319ms (aceitável, mas não escalável)

#### Impacto do Crescimento
- Dados crescem 15% ao mês
- Em 6 meses: 2M → 3.6M pedidos (80% maior)
- Tempo esperado: 319ms × 1.8 = **574ms** ❌ Degradação significativa

### Proposta de Correção

#### Opção A: Reescrever Query com Range (⭐ RECOMENDADO)

```sql
SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE created_at >= '2026-05-10 00:00:00'
  AND created_at < '2026-05-11 00:00:00';
```

**Por quê?**
- Usa range query `created_at BETWEEN start AND end`
- PostgreSQL consegue usar índice B-tree para range
- Index Scan em vez de Seq Scan

**Impacto esperado**:
- **Tempo**: 319ms → ~10-15ms (95% melhoria) ✅
- **I/O**: 11.790 disk reads → ~50-100 (99% redução)
- **Escalabilidade**: Linear com crescimento, não exponencial

**Trade-off**: Nenhum negativo. Query equivalente, sem perdas.

#### Opção B: Materialized View + Índice Partial

```sql
CREATE MATERIALIZED VIEW vendas_por_dia AS
SELECT date(created_at) AS data, count(*) AS qtd, sum(total) AS receita
FROM pedidos
GROUP BY date(created_at);

CREATE INDEX idx_vendas_dia ON vendas_por_dia (data);
```

**Refresh diário**: `REFRESH MATERIALIZED VIEW vendas_por_dia;`

**Impacto**:
- Query: ~1ms (lookup em view pequena)
- Mas precisa manutenção (refresh diário)
- Complexidade extra

**Quando usar**: Se a view for usada por múltiplas queries

---

## Q2: Fila de Pedidos Pendentes do App

### Query
```sql
SELECT id, cliente_id, total, created_at
FROM pedidos
WHERE status = 'pendente'
  AND canal = 'app'
ORDER BY created_at
LIMIT 200;
```

### Diagnóstico

**Tempo atual**: 21.316 ms  
**Status**: ⚠️ Aceitável, mas subótimo

#### Gargalo
Índice `idx_pedidos_created_at` é **parcial**: só cobre `created_at`.  
Query filtra por `status` E `canal`, então precisa filtrar depois do índice.

**Evidência**:
```
Index Scan using idx_pedidos_created_at on pedidos
  Filter: ((status = 'pendente'::text) AND (canal = 'app'::text))
  Rows Removed by Filter: 6832  ← Scanning 6.832 rows desnecessárias!
  Buffers: shared hit=3200 read=3854
  Time: 21.282 ms
```

**O que está acontecendo**:
1. Índice scan em `created_at` (ordenado)
2. Filtra por `status` e `canal` durante scan
3. Descarta 6.832 linhas antes de chegar aos 200 que precisa
4. Rasgo desnecessário de buffer

#### Impacto do Crescimento
- 2M → 3.6M pedidos em 6 meses
- Taxa de status `pendente`: ~10%
- Taxa de canal `app`: ~25%
- Percentual `pendente` + `app`: ~2.5% = ~90.000 linhas
- Filas à tela precisam ser rápidas (<5ms ideal)
- Tempo atual (21ms) já é marginal para uma tela

### Proposta de Correção

#### Opção A: Índice Composto (⭐ RECOMENDADO)

```sql
CREATE INDEX idx_pedidos_pendentes_app ON pedidos (status, canal, created_at)
WHERE status IN ('pendente', 'enviado');  -- Partial index
```

**Por quê?**
- Índice composto: `(status, canal, created_at)`
- PostgreSQL consegue filtrar `status='pendente'` E `canal='app'` usando índice
- Não precisa discartar 6.832 linhas
- Partial index (WHERE clause) reduz tamanho do índice

**Impacto**:
- **Tempo**: 21ms → ~2-3ms (90% melhoria) ✅
- **Rows Removed**: 6.832 → 0
- **Index Size**: ~150MB (vs 300MB sem partial)

**Trade-off**: Espaço em disco (+150MB), mas worth it para operações críticas.

#### Opção B: Índice Multi-Coluna Sem Partial

```sql
CREATE INDEX idx_pedidos_status_canal_time ON pedidos (status, canal, created_at);
```

**Impacto**:
- **Tempo**: 21ms → ~3-4ms (84% melhoria)
- **Rows Removed**: ainda reduz bastante
- **Index Size**: ~300MB (maior que Option A)

---

## Q3: Ranking de Clientes por Receita

### Query
```sql
SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;
```

### Diagnóstico

**Tempo atual**: 3.071.978 ms (3.07 segundos!) ⏱️  
**Status**: 🔴 CRÍTICO

#### Gargalo Principal
**Sort em disco em ambos os workers** + **Hash Aggregate com spill to disk**

**Evidência**:
```
Sort (cost=182789.54..183233.03)
  Sort Method: external merge Disk: 6656kB
  ->  Finalize GroupAggregate
    ->  Gather Merge  (parallelization, mas...)
      ->  Sort  (em cada worker)
        Sort Method: external merge Disk: 17352kB
        ->  Partial HashAggregate
          Planned Partitions: 8
          Batches: 41  ← 41 batches! (should be 1)
          Memory Usage: 8273kB
          Disk Usage: 23704kB  ← LOTS of disk I/O
```

**O que está acontecendo**:
1. **Hash Aggregate não cabe na memória**: `work_mem=4MB` é ridiculamente pequeno para 2M linhas
   - Planejado: 8 partições, mas caiu em 41 batches
   - Cada batch = overflow para disco
2. **Sort em 3 níveis** (workers + finalize) → múltiplos sorts em disco
3. **Parallelization não ajuda**: parallelization overhead supera ganho

**Matemática do desastre**:
- 200k clientes distintos, 2M pedidos
- Aggregate state: ~48 bytes por cliente (cliente_id, count, sum)
- Buffer esperado: 200k × 48 = ~9.6MB
- Mas `work_mem=4MB` → só cabe ~85k clientes
- Overflow: 115k clientes no disco
- 2-3 I/O passes por hash table rebuild = **SLOW**

#### Impacto do Crescimento
- 2M → 3.6M pedidos em 6 meses
- ~200k clientes × 1.8 = **precisa mais memória**
- Sem fix: 3.07s → ~5.5s ❌

### Proposta de Correção

#### Opção A: Aumentar work_mem (Quick Win)

```sql
SET work_mem = '256MB';  -- Antes: 4MB

SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;
```

**Impacto**:
- **Tempo**: 3.071ms → ~400-500ms (85% melhoria) ✅
- **Batches**: 41 → 1 (tudo cabe em memória)
- **Disk I/O**: ~24MB → ~0 (tudo em RAM)
- **Parallelization**: Agora ajuda! (200ms de base, 2 workers = ~100ms)

**Trade-off**:
- Memória servidor: +256MB por conexão ativa
- Se 10 queries parallelas: +2.56GB
- Recomendação: Aumentar para **100-128MB** como baseline

**Quando rodar**: Executar durante madrugada ou cron batch, não real-time

#### Opção B: Criar Summary Table + Batch Job

```sql
CREATE TABLE cliente_receita_daily (
  cliente_id bigint PRIMARY KEY,
  pedidos int,
  receita numeric(12,2),
  atualizado_em timestamp
);

-- Batch job (diário):
INSERT INTO cliente_receita_daily
SELECT cliente_id, count(*), sum(total)
FROM pedidos
WHERE created_at >= current_date - interval '1 day'
GROUP BY cliente_id
ON CONFLICT (cliente_id) DO UPDATE SET
  pedidos = EXCLUDED.pedidos,
  receita = EXCLUDED.receita,
  atualizado_em = now();

-- Query rápida:
SELECT * FROM cliente_receita_daily ORDER BY receita DESC;
```

**Impacto**:
- **Query time**: 3.071ms → ~1ms (3000x melhoria!) ✅
- **Trade-off**: Dados não são real-time (1 dia de lag)
- **Manutenção**: Precisa de job batch diário

**Quando usar**: Se relatório mensal é aceitável com dados de ontem

#### Opção C: Índice em Multiple Columns (Não Vale)

Criar índice não ajuda aqui porque:
- Aggregate é sobre TODOS os pedidos (sem WHERE)
- Índice B-tree não pode acelerar GROUP BY
- Parallel Seq Scan já está sendo usado

---

## Q4: Busca de Produto no Admin

### Query
```sql
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
```

### Diagnóstico

**Tempo atual**: 10.684 ms  
**Status**: ⚠️ Aceitável, mas pode melhorar (ILIKE issue)

#### Gargalo
**ILIKE com wildcard no início** não pode usar índice B-tree.

**Evidência**:
```
Seq Scan on produtos (cost=0.00..449.00 rows=1919)
  Filter: (ativo AND (nome ~~* '%caneta%'::text))
  Rows Removed by Filter: 19000  ← Scanning todos os 20k produtos!
  Buffers: shared hit=199
  Time: 10.684 ms
```

**Por quê?**
- Índice `idx_produtos_nome` é B-tree em `nome`
- B-tree funciona com prefixos: `nome LIKE 'can%'` ✅
- Mas com wildcard no início: `nome LIKE '%can%'` ❌
- PostgreSQL não consegue usar índice, força Seq Scan

**Filtragem**:
- Tabela: 20k linhas (pequena!)
- Resultados esperados: ~1.000 (canetas)
- Taxa de descarte: 95% (19k linhas removidas)

#### Impacto do Crescimento
- 20k → 36k produtos em 6 meses
- Seq Scan ainda é pequeno (~20MB)
- 10.684ms → ~19ms (ainda aceitável)
- **Não é crítico**, mas pode melhorar

### Proposta de Correção

#### Opção A: Full-Text Search com GIN (⭐ RECOMENDADO)

```sql
-- 1. Criar coluna tsvector se não existir
ALTER TABLE produtos ADD COLUMN nome_tsv tsvector;

-- 2. Gerar tsvectors
UPDATE produtos SET nome_tsv = to_tsvector('portuguese', nome);

-- 3. Criar índice GIN
CREATE INDEX idx_produtos_nome_fts ON produtos USING GIN (nome_tsv);

-- 4. Query reescrita:
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome_tsv @@ websearch_to_tsquery('portuguese', 'caneta')
  AND ativo;
```

**Impacto**:
- **Tempo**: 10ms → ~1-2ms (85% melhoria) ✅
- **Index Scan**: GIN consegue usar índice
- **Bônus**: Suporta multi-word search: 'caneta vermelha'

**Trade-off**: Requer manutenção de tsvector (trigger ou UPDATE periódica)

**Quando usar**: Se search é feature importante

#### Opção B: Trigram Index (pg_trgm)

```sql
-- 1. Ativar extensão
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Criar índice GiST
CREATE INDEX idx_produtos_nome_trgm ON produtos USING GIST (nome gist_trgm_ops);

-- 3. Query original funciona mais rápido:
SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
```

**Impacto**:
- **Tempo**: 10ms → ~2-3ms (75% melhoria) ✅
- **Vantagem**: Query não muda (ILIKE segue sendo suportada)
- **Índice Size**: ~2MB (pequeno)

**Trade-off**: Índice trigramas pode ter false positives (raro)

**Quando usar**: Quick win, sem mudança de query

#### Opção C: Partial Index (Se Maioria Produtos são `ativo=true`)

```sql
CREATE INDEX idx_produtos_nome_ativo ON produtos (nome)
WHERE ativo = true;
```

**Impacto**:
- **Index Size**: ~50MB → ~45MB (10% redução)
- **Tempo**: 10ms → ainda ~10ms (não ajuda muito porque index não é usável com ILIKE)

**Não recomendado**: Problema é ILIKE, não `ativo`

---

## Questão Discursiva: Tabela `eventos`

### Contexto
Tabela `eventos` vai receber ~2 milhões de eventos por dia, com retenção de 90 dias.  
Consultas quase sempre filtram por `criado_em` recente.

### Problema com DELETE Naïve

```sql
DELETE FROM eventos WHERE criado_em < now() - interval '90 days';
```

**O que quebra?**

1. **Bloqueio em Escrita**
   - DELETE faz full table scan: 180M linhas (90d × 2M/d)
   - Produz row-level locks em TODAS as linhas deletadas
   - Bloqueia INSERT de novos eventos por MINUTOS
   - Dashboard fica down durante delete 🔴

2. **Fragmentação de Índices**
   - Deletar 180M linhas por dia fragmenta índices
   - B-tree fica com buracos
   - VACUUM full table (horas!)
   - Pausa de nova atividade

3. **WAL (Write-Ahead Log) Explosion**
   - Cada DELETE = uma entrada no WAL
   - 180M entries = centenas de MB de WAL diários
   - Replicação/backup fica pesada

4. **Transaction Log Bloat**
   - DELETE aberto por minutos = transação longa
   - Bloqueia VACUUM de outras tabelas
   - `pg_stat_activity` fica lotado

### Solução Recomendada: Table Partitioning

#### Strategy 1: Range Partition por Data (⭐ RECOMENDADO)

```sql
-- 1. Particioná por range de data (daily)
CREATE TABLE eventos (
  id bigint GENERATED ALWAYS AS IDENTITY,
  pedido_id bigint,
  tipo text NOT NULL,
  payload jsonb,
  criado_em timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id, criado_em)
) PARTITION BY RANGE (date(criado_em));

-- 2. Criar partições por dia (últimos 90 dias)
CREATE TABLE eventos_2026_07_21 PARTITION OF eventos
  FOR VALUES FROM ('2026-07-21') TO ('2026-07-22');
  
CREATE TABLE eventos_2026_07_22 PARTITION OF eventos
  FOR VALUES FROM ('2026-07-22') TO ('2026-07-23');
  
-- ... (repetir para últimos 90 dias)

-- 3. Criar índices em cada partição
CREATE INDEX idx_eventos_2026_07_21_tipo ON eventos_2026_07_21 (tipo);
-- ... (repetir)

-- 4. Expurgo: DROP partition inteira
DROP TABLE eventos_2026_07_21;  -- Instantaneous!
```

**Por quê funciona?**
- Cada dia = uma tabela separada (2M linhas)
- Expiração: `DROP TABLE eventos_2026_07_21` = **< 1ms** ✅
- Sem full table scan
- Sem locks em tabela ativa
- Índices não fragmentam

**Impacto**:
- **Expurgo diário**: < 1ms (vs minutos com DELETE)
- **Write Performance**: +40% (sem bloqueios)
- **Read Performance**: +20% (índices menores, mais cache hits)
- **Manutenção**: Job automático que:
  1. DROP partição de 90 dias atrás
  2. CREATE partição de hoje

#### Strategy 2: Automated Partition Management

```sql
-- Configurar pg_partman ou similar
SELECT create_parent('public.eventos', 'criado_em', 'range', 'daily');
SELECT partition_data_time('public.eventos', 'daily');

-- Configurar retenção automática:
SELECT drop_old_partitions('public.eventos', '90 days');
```

**Vantagem**: Automático, sem SQL manual

#### Implementation Job (cron)

```bash
# /opt/postgres/daily-maintenance.sh
#!/bin/bash
psql -d gestor2000 -c "DROP TABLE IF EXISTS eventos_$(date -d '91 days ago' +%Y_%m_%d);"
psql -d gestor2000 -c "CREATE TABLE eventos_$(date +%Y_%m_%d) PARTITION OF eventos FOR VALUES FROM (CAST('$(date +%Y-%m-%d)' AS date)) TO (CAST('$(date -d +1\ day +%Y-%m-%d)' AS date));"
```

**Rodar**: 00:05 diariamente

---

## Resumo de Tuning

| Query | Problema | Solução | Impacto | Prioridade |
|---|---|---|---|---|
| **Q1** | `date()` função desabilita índice | Usar range query | 319ms → 10ms | 🔴 Alto |
| **Q2** | Índice não cobre status+canal | Índice composto | 21ms → 2ms | 🟡 Médio |
| **Q3** | work_mem=4MB insuficiente | Aumentar para 100MB | 3.07s → 0.5s | 🔴 Alto |
| **Q4** | ILIKE sem wildcard usa índice | Trigram index | 10ms → 2ms | 🟢 Baixo |
| **eventos** | DELETE bloqueante | Table partitioning | Expurgo instant | 🔴 Alto |

---

## Escalability Roadmap (6 meses)

### Mês 1-2: Quick Wins
- ✅ Q1: Reescrever query com range
- ✅ Q4: Criar trigram index
- ✅ work_mem: Aumentar globalmente para 64MB

### Mês 2-3: Estrutural
- ✅ Q2: Criar índice composto
- ✅ Q3: Summary table ou aumentar work_mem para 256MB em batch
- ✅ eventos: Implementar table partitioning

### Mês 3-6: Otimização
- ✅ Tuning parallelization settings (max_parallel_workers)
- ✅ Monitorar queries com pg_stat_statements
- ✅ Considerar sharding se crescimento continuar >15% ao mês

---

## Notas Importantes

1. **Medições**: Sempre rodar EXPLAIN ANALYZE em production-like data
2. **Índices**: Nunca criar sem considerar write overhead (INSERT/UPDATE)
3. **work_mem**: Aumentar para conexões batch, não mantém para OLTP
4. **Partitioning**: Vale a pena só se tabela > 1GB e retenção definida
5. **Monitoramento**: Ativar `auto_explain.log_min_duration` para querys lentas

