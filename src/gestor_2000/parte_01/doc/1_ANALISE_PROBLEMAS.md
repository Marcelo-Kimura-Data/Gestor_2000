# Análise de Qualidade de Dados - Gestor2000

## Resumo Executivo
- **Total Clientes:** 6.300 registros
- **Total Pedidos:** 20.200 registros  
- **Total Pagamentos:** 18.250 registros
- **Problemas critéricos encontrados:** SIM (referências órfãs, inconsistências de formato, encoding)

---

## Problemas Encontrados e Decisões

### 1. CLIENTES_LEGADO.CSV

#### Problema 1.1: CPF com formatos mistos
- **O quê:** 4.226 sem máscara (11 dígitos) vs 2.074 com máscara (XXX.XXX.XXX-XX)
- **Impacto:** Impossível fazer JOIN com pedidos sem normalizar
- **Decisão:** CORRIGIR - Remover toda pontuação, guardar apenas 11 dígitos
- **Trade-off:** Nenhum — é obrigação técnica para join

#### Problema 1.2: Data de cadastro em 3 formatos
- **O quê:** 
  - 2.018 em DD/MM/YYYY (11/12/2021)
  - 2.127 em DD-MM-YY (01-02-21)
  - 2.155 em YYYY-MM-DD (2022-05-30)
- **Impacto:** Ambiguidade (01-02-21 pode ser 01 fev ou 02 jan?)
- **Decisão:** CORRIGIR - Padronizar para YYYY-MM-DD ISO 8601
- **Trade-off:** Perder informação do formato original, mas ganhar consistência

#### Problema 1.3: Cidade com case inconsistente + espaços
- **O quê:** 
  - MAIÚSCULA: "SÃO PAULO", "NITERÓI"
  - minúscula: "rio de janeiro", "são paulo"
  - Misto: "São Paulo", "Rio de Janeiro"
  - Espaços extras: " Santo André  " (466 registros)
- **Impacto:** Mesmo cliente com 2 cidades diferentes (query de analytics quebra)
- **Decisão:** CORRIGIR - Title Case + strip
- **Trade-off:** Nenhum

#### Problema 1.4: 346 emails inválidos ou ausentes
- **O quê:**
  - 257 clientes SEM email (NULL)
  - 89 clientes com email inválido (ex: "-")
  - Total de emails problemáticos: 346
- **Impacto:** Impossível contato legítimo
- **Decisão:** REJEITAR - Email é obrigatório (NOT NULL) no banco
- **Trade-off:** Rejeitar ~5,5% dos clientes vs. garantir dados confiáveis

#### Problema 1.5: Encoding corrompido ("cartÃ£o")
- **O quê:** Alguns CPFs/métodos com encoding latino-1 vs UTF-8 misturado
- **Impacto:** Busca por "cartão" falha
- **Decisão:** CORRIGIR - Usar encoding correto na leitura (já feito: latin-1)
- **Trade-off:** Nenhum

---

### 2. PAGAMENTOS_LEGADO.CSV

#### Problema 2.1: Método com 6 variações de case
- **O quê:** 
  - cartao, cartão (2.901 + 3.103 = 6.004)
  - pix, PIX (3.155 + 3.036 = 6.191)
  - boleto, Boleto (3.086 + 2.969 = 6.055)
- **Impacto:** Reports por método quebram
- **Decisão:** CORRIGIR - Normalizar para lowercase: cartao, pix, boleto
- **Trade-off:** Perder capitalização original, mas ganhar consitência

#### Problema 2.2: 288 valores negativos
- **O quê:** Min: -3.475,88; ex: -2.000,21, -937,05
- **Impacto:** Pagamentos negativos não são válidos
- **Decisão:** REJEITAR - Enviar para quarentena
- **Trade-off:** Perder ~2% dos pagamentos vs. garantir que só valores positivos entrem
- **Por quê:** Pagamentos devem ser valores POSITIVOS. Ajustes/reembolsos devem ser tratados como operações separadas

#### Problema 2.3: Data de pagamento em 2 formatos
- **O quê:** 
  - 9.100 em DD/MM/YYYY
  - 9.150 em YYYY-MM-DD
- **Impacto:** Ambiguidade em datas como 03-04-2025
- **Decisão:** CORRIGIR - Padronizar para YYYY-MM-DD ISO 8601
- **Trade-off:** Nenhum

---

### 3. PEDIDOS_LEGADO.CSV

#### Problema 3.1: Valor total em 2 formatos de decimal
- **O quê:** 
  - 10.062 com vírgula como separador: 1.033,80 (50%)
  - 10.138 com ponto: 3285.97 (50%)
- **Impacto:** CRÍTICO - impossível cálculos sem tratar
- **Decisão:** CORRIGIR - Detectar formato e converter para decimal Python
- **Trade-off:** Nenhum, é obrigação

#### Problema 3.2: Status com 12 variações
- **O quê:**
  - PAGO / pago / Pago (3 variações) = ~5.100
  - PENDENTE / pendente = ~3.400
  - CANCELADO / cancelado / canc (3 variações) = ~4.050
  - ENVIADO / enviado = ~3.300
  - pg (1.737)
- **Impacto:** Dashboard de vendas está completamente quebrado
- **Decisão:** CORRIGIR - Mapear para 4 valores canônicos: PAGO, PENDENTE, CANCELADO, ENVIADO
- **Trade-off:** Interpretação subjetiva (pg → PAGO? sim, é óbvio em português). "canc" → CANCELADO.

#### Problema 3.3: Canal com 5 variações
- **O quê:**
  - site / SITE = ~8.050
  - app / App / "App " = ~7.988
  - marketplace = 4.164
- **Impacto:** Análise de canal errada
- **Decisão:** CORRIGIR - Normalizar para: site, app, marketplace (lowercase)
- **Trade-off:** Nenhum

#### Problema 3.4: Data de pedido em 2 formatos
- **O quê:** DD/MM/YYYY vs YYYY-MM-DD
- **Decisão:** CORRIGIR - Padronizar para YYYY-MM-DD
- **Trade-off:** Nenhum

#### Problema 3.5: CPF cliente com formatos mistos
- **O quê:** Mesmo que clientes (com/sem máscara)
- **Decisão:** CORRIGIR - Remover pontuação
- **Trade-off:** Nenhum

---

### 4. RELACIONAMENTOS (INTEGRIDADE REFERENCIAL)

#### Problema 4.1: 590 pedidos com CPF de cliente inexistente
- **O quê:** Pedido refencia CPF que não está em clientes_legado
- **Impacto:** Impossível fazer JOIN pedido → cliente
- **Decisão:** REJEITAR - Quarentena de pedidos órfãos
- **Trade-off:** Perder ~3% dos pedidos vs. deixar carregar dados inconsistentes
- **Por quê:** Sem cliente, não podemos rastrear origem → melhor rejeitar explicitamente

#### Problema 4.2: 258 pagamentos com num_pedido inexistente
- **O quê:** Pagamento referencia pedido que não existe em pedidos_legado
- **Impacto:** Impossível fazer JOIN pagamento → pedido
- **Decisão:** REJEITAR - Quarentena de pagamentos órfãos
- **Trade-off:** Perder ~1,4% dos pagamentos vs. dados inconsistentes
- **Por quê:** Sem pedido, não sabemos o que foi pago → rejeitar

---

## Resumo de Decisões

| Camada | Problema | Decisão | Registros Afetados |
|--------|----------|---------|-------------------|
| Bronze | CPF mistos (clientes) | CORRIGIR | 6.300 |
| Bronze | Datas (3 formatos) | CORRIGIR | ~6.300 |
| Bronze | Cidade case/espaços | CORRIGIR | ~500 |
| Silver | Email inválido/ausente | REJEITAR | 346 |
| Bronze | Método case | CORRIGIR | 18.250 |
| Silver | Valores negativos | REJEITAR | 288 |
| Bronze | Valor total (2 decimais) | CORRIGIR | 20.200 |
| Bronze | Status (12 variações) | CORRIGIR | 20.200 |
| Bronze | Canal case | CORRIGIR | 20.200 |
| Bronze | CPF mistos (pedidos) | CORRIGIR | 20.200 |
| Silver | Pedidos órfãos | REJEITAR | ~590 |
| Silver | Pagamentos órfãos | REJEITAR | ~258 |

**Total de registros após limpeza:**
- Clientes: 6.300 originais → **5.755 válidos** (91,4%) + 545 rejeitados (8,6%)
- Pedidos: ~20.200 → **~17.846 válidos** (~88%) + ~2.354 rejeitados (~12%)
- Pagamentos: ~18.250 → **~13.225 válidos** (~72,5%) + ~5.025 rejeitados (~27,5%)

---

## Resultados Reais - Fase 1 (CLIENTES)

**Processado em:** `tratar_clientes.py`  
**Data:** 2026-07-22

### Clientes - Validação Realizada
| Categoria | Quantidade | Percentual |
|-----------|-----------|-----------|
| **Bronze (entrada)** | 6.300 | 100% |
| **Silver (válidos)** | 5.755 | 91,4% |
| **Quarentena (rejeitados)** | 545 | 8,6% |

### Detalhamento de Rejeições
| Motivo | Quantidade |
|--------|-----------|
| CPF inválido (< 11 dígitos) | 199 |
| Email ausente | 257 |
| Email inválido (ex: "-") | 89 |
| **Total rejeitado** | **545** |

### Dados Carregados em Silver
- **Arquivo:** `silver/clientes.csv`
- **Registros:** 5.755
- **Colunas:** id_legado, cpf (normalizado), nome, email (válido), cidade (MAIÚSCULA sem acentos), dt_cadastro (ISO 8601)
- **Validações garantidas:** CPF com 11 dígitos, Email válido (@ e .), Cidade normalizada

### Dados em Quarentena
- **Arquivo:** `quarentena/clientes_rejeitados.jsonl`
- **Registros:** 545
- **Formato:** JSONL (um JSON por linha), contém dados originais + motivo rejeição
- **Uso:** Auditoria, análise posterior, possível carregamento manual
