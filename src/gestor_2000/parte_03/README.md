# Parte 3 — Decisões de Arquitetura

## Arquivo Principal

- **`ARQUITETURA.md`** — Respostas às 2 perguntas de arquitetura

## Estrutura

### Pergunta 1: Batch vs Streaming (Dashboard Tempo Real)

**Recomendação**: Não migrar para streaming puro. Manter batch com cache em tempo real.

**Resposta em 10 linhas**:
- Streaming (Kafka) é overkill: custo 3-5x maior, latência útil é 15-30 min, não 1 segundo
- Dashboard de vendas não precisa sub-segundo; user não refresh a cada segundo
- Solução: Batch horário + Redis cache 5 min (não Kafka)
- Streaming requer expertise (state management, exactly-once), batch é simples
- Minha régua: <100 vendas/s → Batch + cache suficiente
- Perguntas críticas: Qual é SLA real? Volume de vendas/s? Budget para Kafka?

**Perguntas-Chave Antes de Decidir**:
1. Latência real necessária?
2. Frequência de refresh do dashboard?
3. Volume de vendas/segundo?
4. Budget para Kafka + ops?
5. Complexity tolerance do time?
6. É produto core ou nice-to-have?
7. Precisa alertar (streaming) ou apenas report (batch)?

**Minha Régua de Decisão**:
- `<100 vendas/s + latência ok 5 min` → Batch Python + Postgres ✅
- `100-1k vendas/s + latência 1-5 min` → Batch + Redis cache 🟡
- `>1k vendas/s + latência <1 min` → Kafka + Flink + data warehouse 🔴

---

### Pergunta 2: Dois Cenários Concretos Onde NÃO Usar Postgres

#### **Cenário 1: Eventos em Larga Escala (100k+ eventos/segundo)**

**Por que Postgres não serve**:
- Postgres ACID é overhead (eventos são fire-and-forget)
- Escalabilidade horizontal é manual (operacional pesada)
- Deletar 90M linhas/dia é bloqueante (vimos em Parte 2)
- Storage não otimizado (8KB pages)

**Solução**: ClickHouse
- Compressão 10:1
- Insert 1M linhas/segundo
- Column-oriented (analytics)
- ~170GB/dia em ClickHouse vs 1.7TB raw

**Minha Régua**:
- `<10k eventos/s` → Postgres + partitioning ok
- `10k-100k eventos/s` → ClickHouse (must)
- `>100k eventos/s` → Snowflake/BigQuery

---

#### **Cenário 2: Busca em Larga Escala (10M+ produtos, 1000 searches/segundo)**

**Por que Postgres não serve**:
- Full-text search básico (sem ranking, sem typo tolerance)
- Índices B-tree não escalem para relevância complexa
- `SELECT * ORDER BY score DESC` em 10M produtos = seq scan
- 1000 searches/s = contention em shared buffers

**Solução**: Elasticsearch
- Inverted index (designed para search)
- TF-IDF ranking, fuzzy matching, facets
- Latência <50ms vs 500ms em Postgres
- Sharding built-in

**Minha Régua**:
- `<100k produtos + <100 searches/s` → Postgres search ok
- `100k-10M produtos + 100-1k searches/s` → Elasticsearch (must)
- `>10M produtos + >1k searches/s` → Elasticsearch + Redis cache

---

## Tabela de Decisão

| Use Case | Volume | Postgres? | Melhor | Por quê |
|---|---|---|---|---|
| OLTP (txn) | <1M/s | ✅ | Postgres | ACID, normalização |
| Eventos/Analytics | >10k/s | ❌ | ClickHouse | Append-only, compressão |
| Search | >100 qps | ❌ | Elasticsearch | Relevância, fuzzy, facets |
| Time-series | >100k/s | ⚠️ | InfluxDB/TimescaleDB | Partitioning automático |
| Graph | 1M+ nodes | ❌ | Neo4j | Pointer-based |
| Cache | <100ms | ❌ | Redis | In-memory |

---

## Minha Régua Pessoal: Quando Sair de Postgres

**Sair QUANDO**:
- Eventos/logs: >10k/segundo
- Search: >100 queries/segundo com relevância
- Time-series: >100k pontos/segundo
- Cache: <100ms SLA
- Graph: Relações muitos-para-muitos complexas

**NÃO sair QUANDO** (motivos insuficientes):
- ❌ "Dados crescem muito" (Postgres escala com sharding)
- ❌ "Trending tech" (Kafka/Spark não faz sentido se SLA permite batch)
- ❌ "Vendor lockin" (Postgres é open-source)
- ❌ "Mais rápido" (Redis é, mas não é durável)

---

## Stack Recomendado para Gestor2000 (6 Meses)

```
Tier 1 - OLTP (Transações):
  PostgreSQL 16 (pedidos, clientes, pagamentos)
  + Read replicas para scaling
  + Partitioning em pedidos (>100M rows)

Tier 2 - OLAP (Analytics):
  ClickHouse (eventos 2M/dia, retenção 90d = 180M)
  + TTL auto-delete
  + 10:1 compression

Tier 3 - Search:
  Elasticsearch (quando marketplace cresce)
  + Produtos search indexing
  + Real-time updates

Tier 4 - Cache:
  Redis (opcional, se Q3 > 1s)
  + Leaderboards cached 5m TTL

Fluxo: Postgres → Kafka → ClickHouse + ES
```

**Este stack aguenta 15% crescimento/mês por 12 meses.**

---

## Como Apresentar

**Estrutura recomendada**:
1. Responder pergunta diretamente (1-2 frases)
2. Dar exemplos concretos (com números)
3. Apresentar régua de decisão (não é genérico)
4. Mostrar perguntas-chave (não é impulsivo)
5. Trade-offs (não é preto-branco)

**Exemplo de resposta boa**:
> "Não faria streaming Kafka agora. Razão: seu volume é ~20 vendas/s, SLA é 15-30 min, pipeline batch Python + Postgres é 10x mais simples e 10x mais barato. Kafka faria sentido em 6 meses se crescer para >500 vendas/s E precisar sub-minuto latency. Perguntas chave: qual é a verdadeira SLA? Quantas vendas/s têm hoje?"

**Exemplo de resposta ruim**:
> "Streaming é melhor porque é moderno. Use Kafka e Spark. Elasticsearch para search porque é rápido."

---

## Recursos

- [Postgres vs ClickHouse](https://clickhouse.com/blog/analysis-of-real-world-data-indexing)
- [When to Use Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-best-practices.html)
- [Kafka Anti-Patterns](https://www.confluent.io/blog/kafka-anti-patterns-how-to-avoid-them/)
- [PostgreSQL Scaling](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-PARTITION)

