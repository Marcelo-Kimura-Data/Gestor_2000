# Parte 1: Pipeline de Migracao Gestor2000

Pipeline para migrar dados legados (CSVs sujos) para PostgreSQL com validacao e normalizacao.

## Quick Start

### 1. Instalar Dependencias

```bash
cd c:\Users\caldo\OneDrive\Desktop\Projeto_gestor2000\gestor_2000
pip install -e .
```

### 2. Configurar Banco de Dados

Crie um arquivo `.env` na raiz do projeto:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua_senha
POSTGRES_DB=gestor2000
```

### 3. Rodar o Pipeline

```bash
python run.py
```

Ou diretamente:

```bash
python src/gestor_2000/parte_01/executar_pipeline.py
```

## O que Faz

1. **Analise Exploratoria**: Detecta problemas nos CSVs (formatos, duplicatas, valores invalidos)
2. **Validacao**: Normaliza dados e valida contra schema
3. **Carga**: Insere dados validos em PostgreSQL
4. **Quarentena**: Registra dados rejeitados em JSONL (auditavel)

## Estrutura de Pastas

```
parte_01/
├── README.md                      (este arquivo)
├── DATA_QUALITY.md               (resultados da validacao)
├── analise_exploratoria.py       (analise inicial dos CSVs)
├── calcular_metricas.py          (calcula receita e divergencias)
├── executar_pipeline.py          (orquestra o pipeline)
│
├── pipe/                         (validadores e tratadores)
│   ├── utils.py                 (funcoes de normalizacao)
│   ├── tratar_clientes.py       (validacao de clientes)
│   ├── tratar_pedidos.py        (validacao de pedidos)
│   └── tratar_pagamentos.py     (validacao de pagamentos)
│
└── schema/
    └── schema.sql                (DDL PostgreSQL)
```

## Entrada (CSVs)

Esperados em: `arquivos_projeto/parte1_pipeline/dados/`

- clientes_legado.csv (6.300 registros)
- pedidos_legado.csv (20.200 registros)
- pagamentos_legado.csv (18.250 registros)

## Saidas Geradas

### Banco de Dados
- clientes (5.477 validos)
- pedidos (17.846 validos)
- pagamentos (13.225 validos)

### Arquivos de Rejeicao
- quarentena/clientes_rejeitados.jsonl (823 rejeitados)
- quarentena/pedidos_rejeitados.jsonl (2.354 rejeitados)
- quarentena/pagamentos_rejeitados.jsonl (5.025 rejeitados)

### Relatorios
- DATA_QUALITY.md - Taxa rejeicao, receita, divergencias
- analise/ - Saida da analise exploratoria

## Comandos Uteis

### Apenas Analise Exploratoria

```bash
python src/gestor_2000/parte_01/analise_exploratoria.py
```

### Calcular Metricas de Qualidade

```bash
python src/gestor_2000/parte_01/calcular_metricas.py
```

### Com Dev Tools (testes, type checking)

```bash
pip install -e ".[dev]"
pytest                    # rodar testes
mypy src/                 # type checking
black src/                # formatar codigo
```

## Resultados Esperados

```
PIPELINE CONCLUIDO COM SUCESSO!

Resumo final:
  Clientes:    5477 inseridos | 823 rejeitados
  Pedidos:    17846 inseridos | 2354 rejeitados
  Pagamentos: 13225 inseridos | 5025 rejeitados

Receita Total: R$ 23.362.823,14
Taxa de Rejeicao: 19,5%
```

## Problemas Comuns

### Erro: "ModuleNotFoundError: No module named 'gestor_2000'"
- Execute a partir da raiz do projeto (nao de dentro de parte_01)
- Ou rode: pip install -e .

### Erro: "psycopg2.OperationalError"
- Verifique se PostgreSQL esta rodando
- Verifique credenciais no .env

### Erro: "No such file or directory: clientes_legado.csv"
- CSVs devem estar em: arquivos_projeto/parte1_pipeline/dados/

## Documentacao Completa

- 1_ANALISE_PROBLEMAS.md - Analise detalhada dos problemas encontrados
- DATA_QUALITY.md - Metricas de qualidade e decisoes de tratamento
- schema.sql - Design do banco com justificativas

---

Versao: 1.0
Data: 2026-07-23
Status: Pipeline funcional e testado
