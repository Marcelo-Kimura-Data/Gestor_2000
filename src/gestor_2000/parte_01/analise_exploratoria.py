import pandas as pd
import os
import sys
from pathlib import Path
import re
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gestor_2000.config import CLIENTES_LEGADO, PEDIDOS_LEGADO, PAGAMENTOS_LEGADO

ANALISE_DIR = Path(__file__).parent.parent.parent / "analise"
ANALISE_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("ANÁLISE EXPLORATÓRIA - DADOS LEGADOS")
print("=" * 80)

# ============================================================================
# 1. CLIENTES
# ============================================================================
print("\n\n### 1. CLIENTES_LEGADO.CSV ###\n")

df_clientes = pd.read_csv(CLIENTES_LEGADO, sep=";", encoding="latin-1")
print(f"Total de registros: {len(df_clientes)}")
print(f"Colunas: {df_clientes.columns.tolist()}")

# CPF - análise
print("\n--- CPF ---")
cpf_formats = df_clientes['cpf'].apply(lambda x:
    "Com máscara" if "." in str(x) or "-" in str(x) else "Sem máscara"
).value_counts()
print(f"Formatos: {cpf_formats.to_dict()}")
print(f"Exemplos:\n{df_clientes['cpf'].head(10).values}")

# Data - análise
print("\n--- Data de Cadastro ---")
def detect_date_format(date_str):
    if pd.isna(date_str):
        return "NaN"
    date_str = str(date_str).strip()
    if re.match(r"\d{1,2}/\d{1,2}/\d{4}", date_str):
        return "DD/MM/YYYY"
    elif re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return "YYYY-MM-DD"
    elif re.match(r"\d{1,2}-\d{1,2}-\d{2}", date_str):
        return "DD-MM-YY"
    return "OUTRO"

date_formats = df_clientes['dt_cadastro'].apply(detect_date_format).value_counts()
print(f"Formatos encontrados: {date_formats.to_dict()}")
print(f"Exemplos:\n{df_clientes['dt_cadastro'].head(10).values}")

# Cidade - análise
print("\n--- Cidade ---")
print(f"Total único: {df_clientes['cidade'].nunique()}")
print(f"Exemplos com espaços/case inconsistente:")
cidades_exemplo = df_clientes['cidade'].apply(lambda x: (len(x) != len(x.strip()), x.isupper(), x.islower())).value_counts().head()
print(f"Espaços extras/case: {cidades_exemplo.to_dict()}")
print(f"Exemplos:\n{df_clientes['cidade'].head(15).values}")

# Email
print("\n--- Email ---")
email_validos = df_clientes['email'].apply(lambda x: "@" in str(x) and "." in str(x)).sum()
print(f"Emails com @ e .: {email_validos}/{len(df_clientes)}")
print(f"Exemplos:\n{df_clientes['email'].head(10).values}")

# ============================================================================
# 2. PAGAMENTOS
# ============================================================================
print("\n\n### 2. PAGAMENTOS_LEGADO.CSV ###\n")

df_pagtos = pd.read_csv(PAGAMENTOS_LEGADO, sep=";", encoding="latin-1")
print(f"Total de registros: {len(df_pagtos)}")
print(f"Colunas: {df_pagtos.columns.tolist()}")

# Método - análise
print("\n--- Método de Pagamento ---")
print(f"Valores únicos: {df_pagtos['metodo'].nunique()}")
print(f"Distribuição:")
print(df_pagtos['metodo'].value_counts())
print(f"Variações de case detectadas:")
for metodo in df_pagtos['metodo'].unique():
    print(f"  - '{metodo}'")

# Valor pago - análise
print("\n--- Valor Pago ---")
print(f"Min: {df_pagtos['valor_pago'].min()}")
print(f"Max: {df_pagtos['valor_pago'].max()}")
print(f"Média: {df_pagtos['valor_pago'].mean():.2f}")
valores_negativos = (df_pagtos['valor_pago'] < 0).sum()
print(f"Valores negativos: {valores_negativos} registros")
if valores_negativos > 0:
    print(f"Exemplos de negativos:")
    print(df_pagtos[df_pagtos['valor_pago'] < 0][['id_pagto', 'valor_pago']].head())

# Data pagamento - análise
print("\n--- Data Pagamento ---")
date_formats_pagto = df_pagtos['dt_pagto'].apply(detect_date_format).value_counts()
print(f"Formatos encontrados: {date_formats_pagto.to_dict()}")
print(f"Exemplos:\n{df_pagtos['dt_pagto'].head(10).values}")

# ============================================================================
# 3. PEDIDOS
# ============================================================================
print("\n\n### 3. PEDIDOS_LEGADO.CSV ###\n")

df_pedidos = pd.read_csv(PEDIDOS_LEGADO, sep=";", encoding="latin-1")
print(f"Total de registros: {len(df_pedidos)}")
print(f"Colunas: {df_pedidos.columns.tolist()}")

# Status - análise
print("\n--- Status ---")
print(f"Valores únicos: {df_pedidos['status'].nunique()}")
print(f"Distribuição:")
print(df_pedidos['status'].value_counts())
print(f"Variações detectadas:")
for status in df_pedidos['status'].unique():
    print(f"  - '{status}'")

# Canal - análise
print("\n--- Canal ---")
print(f"Valores únicos: {df_pedidos['canal'].nunique()}")
print(f"Distribuição:")
print(df_pedidos['canal'].value_counts())
print(f"Variações detectadas:")
for canal in df_pedidos['canal'].unique():
    print(f"  - '{canal}'")

# Valor total - análise
print("\n--- Valor Total ---")
print(f"Tipo de dado: {df_pedidos['valor_total'].dtype}")
print(f"Exemplos (primeiros 20):")
print(df_pedidos['valor_total'].head(20).values)
# Tentar converter pra numérico
df_pedidos['valor_total_str'] = df_pedidos['valor_total'].astype(str)
valor_com_virgula = df_pedidos['valor_total_str'].apply(lambda x: "," in x).sum()
print(f"Valores com vírgula como separador: {valor_com_virgula}")

# Data pedido - análise
print("\n--- Data Pedido ---")
date_formats_pedido = df_pedidos['dt_pedido'].apply(detect_date_format).value_counts()
print(f"Formatos encontrados: {date_formats_pedido.to_dict()}")
print(f"Exemplos:\n{df_pedidos['dt_pedido'].head(10).values}")

# CPF - análise
print("\n--- CPF Cliente ---")
cpf_formats_pedido = df_pedidos['cpf_cliente'].apply(lambda x:
    "Com máscara" if "." in str(x) or "-" in str(x) else "Sem máscara"
).value_counts()
print(f"Formatos: {cpf_formats_pedido.to_dict()}")

# ============================================================================
# 4. RELACIONAMENTOS
# ============================================================================
print("\n\n### 4. RELACIONAMENTOS ###\n")

print("--- Pedidos referenciando clientes ---")
cpf_clientes = set(df_clientes['cpf'].astype(str).str.replace(".", "").str.replace("-", "").values)
cpf_pedidos = set(df_pedidos['cpf_cliente'].astype(str).str.replace(".", "").str.replace("-", "").values)
orfaos_pedidos = cpf_pedidos - cpf_clientes
print(f"Pedidos sem cliente correspondente: {len(orfaos_pedidos)}")
print(f"Exemplos: {list(orfaos_pedidos)[:5]}")

print("\n--- Pagamentos referenciando pedidos ---")
pedidos_ids = set(df_pedidos['num_pedido'].values)
pagtos_pedidos = set(df_pagtos['num_pedido'].values)
orfaos_pagtos = pagtos_pedidos - pedidos_ids
print(f"Pagamentos sem pedido correspondente: {len(orfaos_pagtos)}")
print(f"Exemplos: {list(orfaos_pagtos)[:5]}")

print("\n" + "=" * 80)
print("FIM DA ANÁLISE")
print("=" * 80)
