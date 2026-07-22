# Teste técnico — Engenheiro(a) de Dados Sênior

Bem-vindo(a). Este teste tem 3 partes e foi desenhado para tomar **~4 horas de trabalho**. Você tem **3 dias corridos** para entregar. Não esperamos perfeição — esperamos decisões bem justificadas.

## Regras

- **Uso de IA é liberado e esperado** (Claude, ChatGPT, Copilot, o que você usa no dia a dia). Você vai defender cada decisão ao vivo depois, então use a IA como usaria em produção: entendendo o que está entregando.
- Linguagem livre na Parte 1 (Python, SQL puro, dbt — o que preferir). Banco alvo: **PostgreSQL 16**.
- Se algo no enunciado for ambíguo, **decida e documente a premissa**. Ambiguidade aqui é proposital: dado de verdade é assim.

## Estrutura

| Parte | O quê | Peso |
|---|---|---|
| 1 | Pipeline com dados legados sujos | 40% |
| 2 | Diagnóstico e tuning de queries | 40% |
| 3 | Perguntas de arquitetura | 20% |

Enunciados detalhados nas pastas `parte1_pipeline/`, `parte2_tuning/` e no arquivo `parte3_arquitetura.md`.

## Entrega

Um repositório git (ou zip) contendo:

1. `parte1/` — DDL, código do pipeline, `DATA_QUALITY.md` e instruções de execução (um `README` curto com como rodar; se usar Docker, melhor ainda, mas não é obrigatório).
2. `parte2/` — um único arquivo `TUNING.md` com diagnóstico e proposta por query.
3. `parte3/` — `ARQUITETURA.md` com as respostas.

## Etapa seguinte

Entrevista de **1 hora** onde você apresenta suas decisões (15 min), a gente muda requisitos ao vivo e discute os planos de execução. Não precisa preparar slides.
