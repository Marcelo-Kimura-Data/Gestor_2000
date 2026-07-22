# Parte 1 — Pipeline de migração do Gestor2000 (peso 40%)

## Contexto

Estamos migrando dados de um ERP legado ("Gestor2000") para o nosso Postgres. O time do fornecedor exportou 3 CSVs e jura que "os dados estão OK". Em `dados/`:

- `clientes_legado.csv`
- `pedidos_legado.csv`
- `pagamentos_legado.csv`

Spoiler: os dados **não** estão OK. Parte do teste é você descobrir o quê está errado.

## O que fazer

**1. Modelagem (DDL)**
Escreva o DDL das tabelas finais no Postgres 16. Justifique em comentários as escolhas relevantes: tipos, chaves, constraints, o que você decidiu garantir no banco vs no pipeline.

**2. Pipeline de carga**
Implemente a carga dos 3 arquivos para o seu modelo. Requisitos:

- **Idempotente**: rodar o pipeline 2x produz o mesmo estado final.
- Registros que você decidir **rejeitar** não podem sumir silenciosamente — devem ir para algum lugar auditável (tabela de quarentena, arquivo de rejeição, como preferir).
- Linguagem livre.

**3. `DATA_QUALITY.md`**
Documento curto listando:

- Cada problema de qualidade que você encontrou nos arquivos.
- Como decidiu tratar cada um (corrigir, rejeitar, aceitar) e **por quê** — inclua o trade-off quando houver.
- Duas métricas de negócio ao final, calculadas a partir dos dados carregados: **(a)** receita total de pedidos pagos e **(b)** quantos pedidos têm divergência entre valor do pedido e valor efetivamente pago. Explique como você definiu "pago" e "divergência".

## O que avaliamos

Muito mais o **raciocínio documentado** do que volume de código. Um pipeline simples com decisões bem defendidas ganha de um pipeline sofisticado que trata sujeira que você não percebeu que existia — ou pior, que carrega ela pra dentro sem perceber.
