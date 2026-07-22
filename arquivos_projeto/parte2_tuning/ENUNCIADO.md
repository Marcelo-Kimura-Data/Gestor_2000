# Parte 2 — Tuning (peso 40%)

## Contexto

Você herdou o banco de um e-commerce em Postgres 16. Configuração praticamente default (`work_mem = 4MB`, `shared_buffers` modesto). Volumes atuais:

| Tabela | Linhas |
|---|---|
| `pedidos` | 2.000.000 |
| `itens_pedido` | 4.000.000 |
| `clientes` | 200.000 |
| `produtos` | 20.000 |

O schema e os índices **como estão hoje em produção** estão em `schema.sql`. As 4 queries problemáticas estão em `queries.sql`, e o output real de `EXPLAIN (ANALYZE, BUFFERS)` de cada uma está em `explain_outputs.md`.

Detalhe importante: o negócio cresce ~15% ao mês. O que está "aceitável" hoje pode não estar em 6 meses.

## O que fazer

Para **cada uma das 4 queries**, escreva no seu `TUNING.md`:

1. **Diagnóstico**: qual é o gargalo, apontando as evidências no plano de execução (nós, estimativas, buffers, o que for relevante).
2. **Proposta de correção**: DDL/rewrite/configuração — o que você faria de fato. Se houver mais de uma abordagem, diga qual escolheria e por quê.
3. **Impacto esperado**: ordem de grandeza da melhoria e efeitos colaterais (custo de escrita, espaço, lock durante criação, etc).

## Questão discursiva (máx. 15 linhas)

A tabela `eventos` (hoje vazia) vai passar a receber **~2 milhões de linhas por dia** de eventos de tracking, com retenção de 90 dias. Consultas quase sempre filtram por faixa de `criado_em` recente. Como você desenharia essa tabela e a rotina de expurgo? O que quebra se fizerem do jeito ingênuo (`DELETE FROM eventos WHERE criado_em < ...` diário)?
