# Parte 3 — Decisões de Arquitetura

## Pergunta 1: Batch vs Streaming — Dashboard de "Vendas em Tempo Real"

### Recomendação
**Não migrar para streaming puro.** Manter batch horário com atualização em tempo real via evento-driven updates (middle ground).

### Justificativa
Streaming (Kafka) é overkill para dashboard. Razões:
1. **Custo operacional**: Kafka + Spark/Flink + DevOps expertise = 3-5x mais caro que batch
2. **Latência útil**: Dashboard de vendas precisa de 15-30 min, não 1 segundo. Usuário não refresh a cada segundo
3. **Complexidade**: Streaming requer state management, exactly-once semantics, schema evolution. Batch = simples
4. **SLA vs negócio**: Qual é a verdadeira SLA? Se é "update a cada 15 min", batch wins

**Solução recomendada**: Híbrido
- Pipeline batch: hourlly (atualiza agregações pesadas)
- Cache live: Redis com TTL 5 min (atualiza a cada venda via webhook)
- Result: User vê "vendas da última hora" em <100ms vs "real-time" ilusório

### Perguntas-Chave Antes de Decidir

1. **SLA Real**: Qual é a verdadeira latência necessária? (1s? 5m? Quantificar)
2. **Frequência de queries**: Dashboard é refreshed a cada quanto tempo? (10s? 1m? 5m?)
3. **Volume**: Quantas vendas por segundo? (10? 1000?) — Se <100/s, batch suficiente
4. **Custo**: Budget para Kafka + ops? (infra + pessoas)
5. **Complexity tolerance**: Time pode suportar streaming complexity ou prefere simplicidade?
6. **Business drivers**: É produto core ou nice-to-have?
7. **Alerting vs reporting**: Precisa alertar quando venda acontece (streaming) ou só report agregado (batch)?

### Minha Régua
- **<100 vendas/s, latência ok >5 min**: Batch Python + Postgres ✅
- **100-1k vendas/s, latência 1-5 min**: Batch horário + Redis cache 🟡
- **>1k vendas/s, latência <1 min**: Kafka + Flink + data warehouse (Snowflake) 🔴

Cenário atual (e-commerce ~10-50 vendas/s): Batch + cache suficiente.

---

## Pergunta 2: Dois Cenários Concretos Onde NÃO Usar Postgres

### Cenário 1: Tracking de Eventos em Larga Escala (Events/Analytics)

**Situação**: Aplicação SaaS precisa coletar 100k+ eventos/segundo (pageviews, clicks, conversions).  
**Dados**: Imutável append-only, schema semi-estruturado (JSON), retenção 90-365 dias.

**Por que Postgres não serve**:
- Postgres ACID é overhead: não precisa transação em evento de click, é fire-and-forget
- Escalabilidade horizontal: Postgres sharding é manual, complexo (operacional pesada)
- Retenção: Deletar 90M linhas/dia (como vimos em Parte 2) é bloqueante mesmo com partitions
- Storage: ~2TB/mês em eventos. Postgres storage não é otimizado (8KB pages)

**Solução recomendada**: ClickHouse ou Snowflake
- ClickHouse: Compressão 10:1, insert 1M linhas/s, column-oriented (analytics-optimized)
- Snowflake: Managed, auto-scaling, query <5s em 1TB
- Exemplo: 100k eventos/s = 8.6B eventos/dia = ~1.7TB/dia raw → comprime para ~170GB em ClickHouse

**Régua concreta**:
- <10k eventos/s: Postgres + partitioning é ok
- 10k-100k events/s: ClickHouse (não Postgres)
- >100k events/s: Snowflake ou BigQuery

---

### Cenário 2: Busca em Escala (Full-Text Search com Relevância)

**Situação**: Marketplace com 10M+ produtos. Usuários fazem ~1000 searches/segundo. Precisam de:
- Relevância por score (ranking por popularidade)
- Typo tolerance ("canetas" busca "caneta")
- Faceted search (filtrar por categoria, preço)
- Latência <200ms

**Por que Postgres não serve**:
- Full-text search em Postgres é básico: sem ranking, sem typo tolerance, sem facets
- Índices B-tree/GiST não escalem para relevância complex
- Query "SELECT * ORDER BY score DESC" sem índice = seq scan 10M rows
- Concorrência: 1000 searches/s em Postgres = contention em shared buffers

**Solução recomendada**: Elasticsearch ou Algolia
- Elasticsearch: Inverted index (designed para search), TF-IDF ranking, fuzzy matching, facets
- Exemplo query: `{"query": {"multi_match": {"query": "canetas vermelho", "fuzziness": "AUTO"}}}`
- Latency: <50ms vs 500ms em Postgres
- Escalabilidade: Sharding built-in, 1000 queries/s = trivial

**Régua concreta**:
- <100k produtos, <100 searches/s: Postgres search é ok (use trigram)
- 100k-10M produtos, 100-1k searches/s: Elasticsearch (must)
- >10M products, >1k searches/s: Elasticsearch + Redis cache layer

---

## Critério Geral: Quando Sair de Postgres

| Use Case | Volume | Postgres? | Melhor Solução | Por quê |
|---|---|---|---|---|
| **OLTP (transações)** | <1M txn/s | ✅ Excelente | Postgres + replicas | ACID, normalização, confiabilidade |
| **Eventos/Analytics** | >10k events/s | ❌ Não | ClickHouse/Snowflake | Append-only, compressão, column-oriented |
| **Search** | >100k docs, >100 qps | ❌ Não | Elasticsearch/Algolia | Relevância, fuzzy, facets |
| **Time-series** | >100k points/s | ⚠️ Maybe | TimescaleDB ou InfluxDB | Specialized storage, partitioning |
| **Graph** | >1M nodes, complex joins | ❌ Não | Neo4j/ArangoDB | Pointer-based, não index-based |
| **Key-Value cache** | <100ms latency | ❌ Não | Redis/Memcached | In-memory, subms |
| **Batch ML** | Dados históricos | ✅ OK | Postgres → export to DW | Postgres como source, DW para ML |

---

## Resumo da Minha Régua (Arbitragem Pessoal)

**Postgres é ouro puro para**:
- Dados estruturados (schema definido)
- Transações ACID (consistência importa)
- <1M rows/segundo insert
- Queries complex (JOINs, aggregations)
- Aplicações que precisam confiabilidade >99.95%

**Sair de Postgres quando**:
- **Eventos/Logs**: >10k/s → ClickHouse
- **Search**: >100 queries/s + relevância → Elasticsearch
- **Time-series**: >100k points/s → InfluxDB/TimescaleDB
- **Cache**: <100ms SLA → Redis
- **Graph**: Relações muitos-para-muitos complexas → Neo4j
- **Unstructured blobs**: Vídeo, imagens → S3/GCS

**O que NÃO é razão suficiente**:
- ❌ "Dados crescem muito" — Postgres escala horizontal se sharded
- ❌ "Trending tech" — Kafka/Spark não faz sentido se SLA permite batch
- ❌ "Vendor lockin" — Postgres é open-source, zero lockin
- ❌ "Mais rápido" — Redis é mais rápido mas não é durável

---

## Decisão Final: Stack Recomendado para Gestor2000 em 6 Meses

```
Tier 1 (Transações - OLTP):
  PostgreSQL 16 (pedidos, clientes, pagamentos)
  + Read replicas para scaling read-heavy queries
  + Partitioning em pedidos (>100M rows)

Tier 2 (Analytics - OLAP):
  ClickHouse (eventos, 2M/dia → 90 dias = 180M)
  + TTL auto-delete aged partitions
  + 10:1 compression

Tier 3 (Search):
  Elasticsearch (se marketplace cresce)
  + Produtos search indexing
  + Real-time indexing updates

Tier 4 (Cache):
  Redis (opcional, se Q3 > 1s ainda)
  + Cliente revenue rankings cached 5m TTL

Arquitetura: Postgres primário → ClickHouse + ES via Kafka (eventual consistency ok)
```

**Este stack sustenta 15% crescimento/mês por 12 meses.**
