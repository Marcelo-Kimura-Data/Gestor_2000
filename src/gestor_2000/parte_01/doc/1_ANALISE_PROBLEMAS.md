# 📋 Análise de Qualidade de Dados - Gestor 2000

**Versão:** 2.0 (Atualizado 2026-07-23)  
**Escopo:** Análise exploratória de dados legados antes de migração para PostgreSQL  
**Ferramenta de Análise:** `analise_exploratoria.py`

---

## 📊 Resumo Executivo

| Arquivo | Registros | Estado | Problemas |
|---------|-----------|--------|-----------|
| **CLIENTES_LEGADO.CSV** | 6.300 | Analisado ✅ | 5 categorias |
| **PEDIDOS_LEGADO.CSV** | 20.200 | Analisado ✅ | 5 categorias |
| **PAGAMENTOS_LEGADO.CSV** | 18.250 | Analisado ✅ | 3 categorias |
| **TOTAL** | **44.750** | ✅ | **13 problemas** |

**Status Crítico:** Sim - Referências órfãs, inconsistências de formato, problemas de encoding detectados.

---

## 🔍 Análise Detalhada de Problemas

### **1. CLIENTES_LEGADO.CSV** (6.300 registros)

---

#### **1.1 | CPF com Formatos Mistos**

**Descrição Explícita:**
- 4.226 registros com CPF **SEM máscara**: `94473534103` (11 dígitos puros)
- 2.074 registros com CPF **COM máscara**: `891.248.839-21` (formato XXX.XXX.XXX-XX)
- **Total:** 6.300 registros (100%)

**Exemplos Reais:**
```
Sem máscara: 94473534103, 62972669215, 12327489784, 76654842715
Com máscara: 891.248.839-21, 412.126.788-50, 927.769.843-83
```

**Impacto Técnico:**
- ❌ Impossível fazer JOIN com tabela `pedidos` (que referencia CPF normalizado)
- ❌ Buscas por CPF falham (um busca "123.456.789-00", outro "12345678900")
- ❌ Unicidade não pode ser garantida

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_cpf

# Antes: "891.248.839-21" ou "89124883921"
# Depois: "89124883921"
cpf_normalizado = normalizar_cpf(valor_bruto)
```

**Trade-off:** Nenhum - é obrigação técnica para integridade referencial.

---

#### **1.2 | Data de Cadastro em 3 Formatos Diferentes**

**Descrição Explícita:**
- 2.018 registros em formato **DD/MM/YYYY**: `11/12/2021`
- 2.127 registros em formato **DD-MM-YY**: `01-02-21` (ambíguo: jan ou fev?)
- 2.155 registros em formato **YYYY-MM-DD**: `2022-05-30`
- **Total:** 6.300 registros (100%)

**Exemplos Reais:**
```
DD/MM/YYYY: 11/12/2021, 21/08/2022, 01/08/2022
DD-MM-YY:   01-02-21, 17-04-22, 24-03-23
YYYY-MM-DD: 2022-05-30, 2022-11-04, 2025-02-01
```

**Impacto Técnico:**
- ⚠️ Ambiguidade em datas como "01-02-21" (é 1º fev ou 2 jan?)
- ❌ Tipo de dado inconsistente (string em vez de DATE)
- ❌ Ordenação e filtros quebram

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_data

# Antes: "11/12/2021" ou "01-02-21" ou "2022-05-30"
# Depois: "2021-12-11" (ISO 8601)
data_normalizada = normalizar_data(valor_bruto)

# Heurística para DD-MM-YY: se YY < 30 → 20YY, senão 19YY
# (ex: "01-02-21" → "2021-02-01")
```

**Trade-off:** Perder informação do formato original, mas ganhar consistência para analytics.

---

#### **1.3 | Cidade com Variações de Case e Espaços**

**Descrição Explícita:**
- **60 cidades únicas** identificadas
- **Variações de case:**
  - MAIÚSCULA: "SÃO PAULO", "NITERÓI", "GOIÂNIA"
  - Mista: "São Paulo", "Rio de Janeiro", "Belo Horizonte"
  - Minúscula: "rio de janeiro", "são paulo" (raras)
  
- **Espaços extras:** 466 registros com trim necessário
  - Exemplos: `" Santo André  "`, `"  Curitiba"`, `"Sorocaba  "`

**Exemplos Reais:**
```
NITERÓI, Valinhos, Goiânia, SANTO ANDRÉ, Curitiba, Rio de Janeiro
```

**Impacto Técnico:**
- ❌ "SÃO PAULO" ≠ "São Paulo" → Analytics duplica dados
- ❌ "Curitiba " ≠ "Curitiba" → JOIN quebra
- ❌ Acentos variam em encoding

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Funções de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_cidade, remover_acentos

# Antes: "SÃO PAULO" ou " São Paulo  " ou "são paulo"
# Depois: "SAO PAULO" (MAIÚSCULA + sem acentos + trim)
cidade_normalizada = normalizar_cidade(valor_bruto)

# Internamente usa:
# 1. trim() - remove espaços
# 2. remover_acentos() - "São" → "Sao"
# 3. upper() - "Sao Paulo" → "SAO PAULO"
```

**Trade-off:** Nenhum - melhora qualidade de dados sem perder informação.

---

#### **1.4 | Emails Inválidos ou Ausentes**

**Descrição Explícita:**
- **5.936** emails válidos (@ e . presentes)
- **364** emails problemáticos:
  - 257 registros **SEM email** (NULL/vazio)
  - 89 registros com **formato inválido** (ex: "-", "abc", "luis.souza1209gmail.com")
  - 18 registros com **encoding quebrado**

**Taxa de Problemas:** 364/6.300 = **5.8%**

**Exemplos Reais - Válidos:**
```
luis.souza1209@gmail.com
valter.ribeiro2327@gmail.com
patricia.goncalves2155@gmail.com
contato4954@hotmail.com
```

**Exemplos Reais - Inválidos:**
```
(vazio/NULL)
-
abc
luis.souza1209gmail.com (falta @)
```

**Impacto Técnico:**
- ❌ Schema PostgreSQL tem `email NOT NULL`
- ❌ Impossível enviar notificações por email
- ❌ Campos de contato incompletos

**Decisão de Tratamento:** 🚫 **REJEITAR** (não corrigir)

**Função de Validação:**
```python
from gestor_2000.parte_01.pipe.utils import validar_email

# Retorna True/False (não levanta exceção)
if not validar_email(email_bruto):
    # Enviar para quarentena
    rejeitar_cliente("Email inválido: " + email_bruto)

# Validação: deve ter @ E . presentes
# Exemplos:
#   validar_email("luis@gmail.com") → True
#   validar_email("luis.souza1209gmail.com") → False (falta @)
```

**Trade-off:** Rejeitar ~5,8% dos clientes (364 registros) vs. garantir dados confiáveis e NOT NULL no banco.

---

### **2. PAGAMENTOS_LEGADO.CSV** (18.250 registros)

---

#### **2.1 | Método de Pagamento com 6 Variações de Case**

**Descrição Explícita:**
- **cartao/cartão:** 3.103 + 2.901 = **6.004 registros** (33%)
- **pix/PIX:** 3.155 + 3.036 = **6.191 registros** (34%)
- **boleto/Boleto:** 3.086 + 2.969 = **6.055 registros** (33%)
- **Variações encontradas:** 6 (lowercase, UPPERCASE, Titulo, com acento)

**Exemplos Reais:**
```
pix, PIX (variação de case)
cartao, cartÃ£o (encoding quebrado)
boleto, Boleto (case misto)
```

**Impacto Técnico:**
- ❌ Schema tem CHECK (metodo IN ('cartao', 'pix', 'boleto'))
- ❌ Queries como `WHERE metodo = 'pix'` perdem registros
- ❌ Reports por método duplicam dados (pix vs PIX)

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_metodo

# Antes: "cartão" ou "PIX" ou "Boleto" ou "cartÃ£o"
# Depois: "cartao" (lowercase, sem acentos)
metodo_normalizado = normalizar_metodo(valor_bruto)

# Trata encoding quebrado ("cartÃ£o" → "cartao")
# Valores válidos: 'cartao', 'pix', 'boleto'
# Retorna None se inválido
```

**Trade-off:** Perder informação de case original, mas ganhar consistência para relatórios.

---

#### **2.2 | Valores Negativos em Pagamentos**

**Descrição Explícita:**
- **374 registros** com valor_pago < 0
- **Min:** -3.475,88 (reembolso ou ajuste grande)
- **Exemplos negativos:** -2.000,21, -937,05, -2.099,10, -152,95, -1.407,18
- **Taxa:** 374/18.250 = **2.05%**

**Exemplos Reais:**
```
id_pagto: 707494, valor_pago: -2000.21
id_pagto: 703119, valor_pago: -937.05
id_pagto: 716835, valor_pago: -2099.10
```

**Impacto Técnico:**
- ❌ Schema tem `CHECK (valor_pago > 0)` - dados não inserem
- ❌ Cálculo de receita fica negativo
- ❌ Semântica errada (pagamento = valor recebido, deve ser positivo)

**Decisão de Tratamento:** 🚫 **REJEITAR** (não corrigir)

**Justificativa:** 
Pagamentos devem ser **valores positivos**. Se há reembolsos ou ajustes, devem ser operações separadas com semântica explícita (ex: tipo='reembolso'), não valores negativos.

**Função de Validação:**
```python
# Não há função separada, validação é inline:
if valor_pago <= 0:
    rejeitar_pagamento("Valor pago deve ser > 0: " + str(valor_pago))
```

**Trade-off:** Perder ~2% dos pagamentos (374 registros) vs. garantir semântica correta e constraint de banco.

---

#### **2.3 | Data de Pagamento em 2 Formatos**

**Descrição Explícita:**
- **9.100 registros** em formato **DD/MM/YYYY**: `17/10/2025`
- **9.150 registros** em formato **YYYY-MM-DD**: `2025-05-26`
- **Total:** 18.250 registros (100%)

**Exemplos Reais:**
```
DD/MM/YYYY: 17/10/2025, 13/09/2024, 18/02/2025
YYYY-MM-DD: 2025-05-26, 2024-09-03, 2024-07-03
```

**Impacto Técnico:**
- ⚠️ Ambiguidade em datas: "03-04-2025" pode ser 3 de abril ou 4 de março?
- ❌ Ordenação quebra se ficar como string
- ❌ Comparações (WHERE dt_pagto > '2025-01-01') falham

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_data

# Antes: "17/10/2025" ou "2025-05-26"
# Depois: "2025-10-17" (ISO 8601)
data_normalizada = normalizar_data(valor_bruto)
```

**Trade-off:** Nenhum - só padronização.

---

### **3. PEDIDOS_LEGADO.CSV** (20.200 registros)

---

#### **3.1 | Valor Total em 2 Formatos de Decimal**

**Descrição Explícita:**
- **10.062 registros** (50%) com **vírgula como separador**: `1.033,80` (1mil e 33 reais)
- **10.138 registros** (50%) com **ponto como decimal**: `3285.97` (3mil 285 reais)
- **Ambiguidade:** "1.033" pode significar 1.033 ou 1.033,00 dependendo do contexto

**Exemplos Reais - Formato Brasileiro (vírgula decimal):**
```
1.033,80 → 1033.80
3.137,65 → 3137.65
1.397,56 → 1397.56
```

**Exemplos Reais - Formato US (ponto decimal):**
```
3285.97 → 3285.97
1918.42 → 1918.42
2956.67 → 2956.67
```

**Impacto Técnico:**
- 🔴 **CRÍTICO** - Impossível fazer cálculos sem tratar
- ❌ SUM(valor_total) dá resultado completamente errado
- ❌ Comparações (WHERE valor_total > 1000) falham
- ❌ Schema espera `NUMERIC(18,2)` (decimal)

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import converter_valor

# Antes: "1.033,80" ou "3285.97"
# Depois: 1033.8 ou 3285.97 (float Python)
valor_convertido = converter_valor(valor_bruto)

# Lógica interna:
# 1. Se tem , e . → último é decimal: "1.033,80" → 1033.80
# 2. Se tem só , → converter: "1033,80" → 1033.80
# 3. Se tem só . → manter: "3285.97" → 3285.97
# 4. Se numérico puro → converter: "3285" → 3285.0
```

**Trade-off:** Nenhum - é obrigação técnica.

---

#### **3.2 | Status com 12 Variações**

**Descrição Explícita:**
- **12 variações diferentes** de status encontradas
- **Mapeamento necessário para 4 canônicos:**

| Status Canônico | Variações Encontradas | Quantidade | % do Total |
|-----------------|----------------------|-----------|-----------|
| **PAGO** | pago, Pago, PAGO, pg | ~5.162 | 25.6% |
| **PENDENTE** | pendente, PENDENTE | ~3.377 | 16.7% |
| **CANCELADO** | cancelado, CANCELADO, canc | ~4.047 | 20.0% |
| **ENVIADO** | enviado, ENVIADO | ~3.276 | 16.2% |
| **(Inválido)** | Outros | ~3.338 | 16.5% |

**Exemplos Reais:**
```
PAGO, pago, Pago, pg (variações)
PENDENTE, pendente (variações)
CANCELADO, cancelado, canc (variações)
ENVIADO, enviado (variações)
pago  (com espaço extra)
```

**Impacto Técnico:**
- 🔴 **Dashboard completamente quebrado** - não consegue agrupar
- ❌ Schema tem `CHECK (status IN ('PAGO', 'PENDENTE', 'CANCELADO', 'ENVIADO'))`
- ❌ Queries como `WHERE status = 'PAGO'` perdem registros em lowercase

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_status

# Antes: "pago" ou "PAGO" ou "pg" ou "canc"
# Depois: "PAGO" ou "PENDENTE" ou "CANCELADO" ou "ENVIADO"
status_normalizado = normalizar_status(valor_bruto)

# Mapeamento interno:
# "pago", "pg" → "PAGO"
# "pendente" → "PENDENTE"
# "cancelado", "canc" → "CANCELADO"
# "enviado" → "ENVIADO"
# Retorna None se inválido → rejeitar
```

**Trade-off:** Interpretação subjetiva necessária:
- "pg" → "PAGO" ✓ (óbvio em português)
- "canc" → "CANCELADO" ✓ (abreviação clara)

---

#### **3.3 | Canal com 5 Variações**

**Descrição Explícita:**
- **5 variações** de canal (case misto, espaços)
- **Mapeamento necessário para 3 canônicos:**

| Canal Canônico | Variações | Quantidade | % |
|----------------|-----------|-----------|---|
| **site** | site, SITE | ~8.050 | 39.8% |
| **app** | app, App, "App " | ~7.988 | 39.5% |
| **marketplace** | marketplace | 4.164 | 20.6% |

**Exemplos Reais:**
```
site, SITE (case misto)
app, App, App  (case e espaço misto)
marketplace (consistente)
```

**Impacto Técnico:**
- ❌ Schema tem `CHECK (canal IN ('site', 'app', 'marketplace'))`
- ❌ Análise de canal errada (site vs SITE = 2 valores)
- ❌ Queries falham

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_canal

# Antes: "SITE" ou "App " ou "marketplace"
# Depois: "site" (lowercase + trim)
canal_normalizado = normalizar_canal(valor_bruto)

# Valores válidos: 'site', 'app', 'marketplace'
# Retorna None se inválido → rejeitar
```

**Trade-off:** Nenhum - melhora qualidade.

---

#### **3.4 | Data de Pedido em 2 Formatos**

**Descrição Explícita:**
- **10.153 registros** em formato **DD/MM/YYYY**: `08/04/2024`
- **10.047 registros** em formato **YYYY-MM-DD**: `2024-03-08`
- **Total:** 20.200 registros (100%)

**Impacto Técnico:** Mesmo que 1.2 e 2.3

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_data

data_normalizada = normalizar_data(valor_bruto)
```

**Trade-off:** Nenhum.

---

#### **3.5 | CPF Cliente com Formatos Mistos**

**Descrição Explícita:**
- **10.180 registros** com CPF **COM máscara**
- **10.020 registros** com CPF **SEM máscara**
- Mesmo problema que 1.1, mas em pedidos

**Decisão de Tratamento:** ✅ **CORRIGIR**

**Função de Correção:**
```python
from gestor_2000.parte_01.pipe.utils import normalizar_cpf

cpf_normalizado = normalizar_cpf(valor_bruto)
```

**Trade-off:** Nenhum.

---

### **4. RELACIONAMENTOS (INTEGRIDADE REFERENCIAL)**

---

#### **4.1 | 590 Pedidos Órfãos (Cliente Inexistente)**

**Descrição Explícita:**
- **590 pedidos** referenciam CPF de cliente que **NÃO EXISTE** em CLIENTES_LEGADO
- Taxa: 590/20.200 = **2.9%**
- Exemplos de CPFs órfãos: 71816374873, 03128691347, 40306828120

**Cenário Exemplo:**
```
Pedido #12345 foi feito por cliente CPF: 71816374873
MAS: Este CPF não existe em clientes_legado
→ Impossível fazer JOIN pedido → cliente
```

**Impacto Técnico:**
- ❌ FK constraint em PostgreSQL REJEITA a inserção
- ❌ Impossível rastrear cliente do pedido
- ❌ Analytics quebra

**Decisão de Tratamento:** 🚫 **REJEITAR**

**Função de Validação (em tratar_pedidos.py):**
```python
def carregar_cpfs_validos() -> set:
    """Carrega CPFs que foram inseridos com sucesso em clientes."""
    db = DatabaseConnection()
    db.connect()
    db.cursor.execute("SELECT cpf FROM clientes")
    cpfs = set(row[0] for row in db.cursor.fetchall())
    return cpfs

# Depois, ao processar pedido:
if cpf_normalizado not in cpfs_validos:
    rejeitar_pedido("Cliente não existe: CPF " + cpf_normalizado)
```

**Trade-off:** Rejeitar ~3% dos pedidos (590 registros) vs. deixar dados com integridade quebrada.

**Por quê:** Sem cliente, não conseguimos:
- Identificar quem fez o pedido
- Fazer analytics por cliente
- Rastrear histórico

---

#### **4.2 | 258 Pagamentos Órfãos (Pedido Inexistente)**

**Descrição Explícita:**
- **258 pagamentos** referenciam pedido (num_pedido) que **NÃO EXISTE** em PEDIDOS_LEGADO
- Taxa: 258/18.250 = **1.4%**
- Exemplos: 115202, 107011, 109571, 110083, 103942

**Impacto Técnico:**
- ❌ FK constraint REJEITA a inserção
- ❌ Impossível rastrear qual pedido foi pago
- ❌ Reconciliação falha

**Decisão de Tratamento:** 🚫 **REJEITAR**

**Função de Validação (em tratar_pagamentos.py):**
```python
def carregar_pedidos_validos() -> set:
    """Carrega pedidos que foram inseridos com sucesso."""
    db = DatabaseConnection()
    db.connect()
    db.cursor.execute("SELECT num_pedido FROM pedidos")
    pedidos = set(row[0] for row in db.cursor.fetchall())
    return pedidos

# Depois:
if num_pedido not in pedidos_validos:
    rejeitar_pagamento("Pedido não existe: #" + str(num_pedido))
```

**Trade-off:** Rejeitar ~1.4% dos pagamentos (258 registros) vs. dados com integridade quebrada.

---

## 📊 Resumo de Decisões

| # | Tabela | Problema | Decisão | Função de Correção | Registros Afetados |
|----|--------|----------|---------|-------------------|-------------------|
| 1.1 | CLIENTES | CPF mistos | CORRIGIR | `normalizar_cpf()` | 6.300 |
| 1.2 | CLIENTES | Datas 3 formatos | CORRIGIR | `normalizar_data()` | 6.300 |
| 1.3 | CLIENTES | Cidade case/espaços | CORRIGIR | `normalizar_cidade()` | ~500 |
| 1.4 | CLIENTES | Email inválido | REJEITAR | `validar_email()` | 364 |
| 2.1 | PAGAMENTOS | Método case | CORRIGIR | `normalizar_metodo()` | 18.250 |
| 2.2 | PAGAMENTOS | Valores negativos | REJEITAR | Validação inline | 374 |
| 2.3 | PAGAMENTOS | Data 2 formatos | CORRIGIR | `normalizar_data()` | 18.250 |
| 3.1 | PEDIDOS | Valor 2 decimais | CORRIGIR | `converter_valor()` | 20.200 |
| 3.2 | PEDIDOS | Status 12 variações | CORRIGIR | `normalizar_status()` | 20.200 |
| 3.3 | PEDIDOS | Canal 5 variações | CORRIGIR | `normalizar_canal()` | 20.200 |
| 3.4 | PEDIDOS | Data 2 formatos | CORRIGIR | `normalizar_data()` | 20.200 |
| 3.5 | PEDIDOS | CPF mistos | CORRIGIR | `normalizar_cpf()` | 20.200 |
| 4.1 | RELACIONAMENTOS | Pedidos órfãos | REJEITAR | `carregar_cpfs_validos()` | 590 |
| 4.2 | RELACIONAMENTOS | Pagamentos órfãos | REJEITAR | `carregar_pedidos_validos()` | 258 |

---

## 📈 Impacto de Limpeza de Dados

**Registros após pipeline (estimativa):**

| Arquivo | Bronze | Silver | Quarentena | Taxa Rejeição |
|---------|--------|--------|-----------|---------------|
| **CLIENTES** | 6.300 | 5.936 | 364 | 5.8% |
| **PEDIDOS** | 20.200 | 17.846 | 2.354 | 11.6% |
| **PAGAMENTOS** | 18.250 | 13.225 | 5.025 | 27.5% |
| **TOTAL** | 44.750 | 36.007 | 8.743 | 19.5% |

**Interpretação:** 
- 80,5% dos dados são válidos (Silver)
- 19,5% dos dados têm problemas graves o suficiente para rejeição
- Maior taxa em pagamentos (27,5%) devido a valores negativos + pedidos órfãos

---

## 📁 Arquivo de Saída da Análise

**Gerado por:** `analise_exploratoria.py`  
**Localização:** `analise/` (no diretório raiz do projeto)

**Última execução:** 2026-07-23  
**Status:** ✅ Validado contra documentação

---

**Próximos passos:** Implementar pipeline de limpeza em `executar_pipeline.py` usando as funções de `utils.py`.
