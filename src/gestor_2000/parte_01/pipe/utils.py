"""
Funções reutilizáveis para tratamento de dados legados do Gestor2000.

Funções de normalização:
- CPF
- Data (3 formatos diferentes)
- Email (validação)
- Cidade (MAIÚSCULA + sem acento)
- Status (12 variações → 4 canônicas)
- Método de pagamento (6 variações → 3 canônicos)
- Canal (5 variações → 3 canônicos)
- Valor monetário (vírgula vs ponto como separador)
"""

import re
import pandas as pd
import unicodedata
from typing import Optional, Dict, Any
import json
from pathlib import Path


# ============================================================================
# UTILITÁRIOS: REMOVER ACENTOS
# ============================================================================

def remover_acentos(texto: str) -> str:
    """
    Remove acentos de um texto.

    Exemplos:
        'São Paulo' → 'Sao Paulo'
        'Brasília' → Brasilia'
        'Niterói' → 'Niteroi'
    """
    if not texto:
        return texto

    # Decompor em caracteres base + diacríticos
    nfd = unicodedata.normalize('NFD', texto)
    # Filtrar apenas caracteres base (remover diacríticos)
    sem_acentos = ''.join(
        char for char in nfd
        if unicodedata.category(char) != 'Mn'
    )
    return sem_acentos


# ============================================================================
# NORMALIZAÇÃO: CPF
# ============================================================================

def normalizar_cpf(cpf: Any) -> Optional[str]:
    """
    Remove pontuação do CPF, retorna 11 dígitos ou None se inválido.

    Exemplos:
        '891.248.839-21' → '89124883921'
        '94473534103' → '94473534103'
        None → None
    """
    if pd.isna(cpf):
        return None

    cpf_str = str(cpf).strip()
    cpf_limpo = re.sub(r"\D", "", cpf_str)  # Remove tudo que não é dígito

    if len(cpf_limpo) == 11:
        return cpf_limpo

    return None


# ============================================================================
# NORMALIZAÇÃO: DATA
# ============================================================================

def normalizar_data(data_str: Any) -> Optional[str]:
    """
    Converte data em múltiplos formatos para ISO 8601 (YYYY-MM-DD).

    Formatos suportados:
        DD/MM/YYYY  → '11/12/2021'
        DD-MM-YY    → '01-02-21' (heurística: YY < 30 → 20YY, senão 19YY)
        YYYY-MM-DD  → '2022-05-30' (já ISO, apenas retorna)

    Retorna None se não conseguir parsear.

    Exemplos:
        '11/12/2021' → '2021-12-11'
        '01-02-21' → '2021-02-01' (assumindo 21 = 2021)
        '2022-05-30' → '2022-05-30'
    """
    if pd.isna(data_str):
        return None

    data_str = str(data_str).strip()

    # Já está em ISO 8601
    if re.match(r"^\d{4}-\d{2}-\d{2}$", data_str):
        return data_str

    # DD/MM/YYYY
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", data_str):
        try:
            dt = pd.to_datetime(data_str, format="%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except:
            return None

    # DD-MM-YY (ambíguo! 01-02-21 pode ser 2021 ou 2001)
    # Heurística: se YY < 30, assume 20YY; se >= 30, assume 19YY
    if re.match(r"^\d{1,2}-\d{1,2}-\d{2}$", data_str):
        try:
            parts = data_str.split("-")
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            # Dados são de 2019-2026, então < 30 = 20XX
            century = 2000 if year < 30 else 1900
            dt = pd.to_datetime(
                f"{day:02d}/{month:02d}/{century + year}",
                format="%d/%m/%Y"
            )
            return dt.strftime("%Y-%m-%d")
        except:
            return None

    return None


# ============================================================================
# NORMALIZAÇÃO: EMAIL
# ============================================================================

def validar_email(email: Any) -> bool:
    """
    Validação simples: verifica se tem @ e ponto (., com ou sem TLD).

    Retorna True/False (não levanta exceção).

    Exemplos:
        'luis.souza@gmail.com' → True
        'contato@hotmail.com' → True
        'luis.souza1209gmail.com' → False (falta @)
        '' → False
        None → False
    """
    if pd.isna(email):
        return False

    email_str = str(email).strip()

    # Validação mínima: tem @ e tem ponto
    return "@" in email_str and "." in email_str


# ============================================================================
# NORMALIZAÇÃO: CIDADE
# ============================================================================

def normalizar_cidade(cidade: Any) -> Optional[str]:
    """
    Normaliza cidade para MAIÚSCULA sem acentos.

    Exemplos:
        'SÃO PAULO' → 'SAO PAULO'
        'rio de janeiro' → 'RIO DE JANEIRO'
        ' Santo André  ' → 'SANTO ANDRE'
        '' → None
    """
    if pd.isna(cidade):
        return None

    cidade_str = str(cidade).strip()

    if not cidade_str:
        return None

    # Remover acentos e maiúscula
    sem_acentos = remover_acentos(cidade_str)
    return sem_acentos.upper()


# ============================================================================
# NORMALIZAÇÃO: STATUS (PEDIDOS)
# ============================================================================

def normalizar_status(status: Any) -> Optional[str]:
    """
    Mapeia 12 variações de status para 4 valores canônicos.

    Mapeamento:
        'pago', 'PAGO', 'Pago', 'pg' → 'PAGO'
        'pendente', 'PENDENTE' → 'PENDENTE'
        'cancelado', 'CANCELADO', 'canc' → 'CANCELADO'
        'enviado', 'ENVIADO' → 'ENVIADO'

    Retorna None se valor inválido.

    Exemplos:
        'pago' → 'PAGO'
        'PENDENTE' → 'PENDENTE'
        'canc' → 'CANCELADO'
        'pg' → 'PAGO'
    """
    if pd.isna(status):
        return None

    status_lower = str(status).strip().lower()

    # Mapeamento de variações para valores canônicos
    mapa = {
        "pago": "PAGO",
        "pg": "PAGO",
        "pendente": "PENDENTE",
        "cancelado": "CANCELADO",
        "canc": "CANCELADO",
        "enviado": "ENVIADO",
    }

    return mapa.get(status_lower)


# ============================================================================
# NORMALIZAÇÃO: MÉTODO DE PAGAMENTO
# ============================================================================

def normalizar_metodo(metodo: Any) -> Optional[str]:
    """
    Normaliza método de pagamento para lowercase.

    Valores válidos: 'cartao', 'pix', 'boleto'

    Trata encoding quebrado ('cartÃ£o' → 'cartao')

    Exemplos:
        'cartão' → 'cartao'
        'PIX' → 'pix'
        'Boleto' → 'boleto'
        'cartÃ£o' → 'cartao'
        'dinheiro' → None
    """
    if pd.isna(metodo):
        return None

    metodo_lower = str(metodo).strip().lower()

    # Limpar encoding quebrado (cartÃ£o → cartao)
    if "ã" in metodo_lower:
        metodo_lower = metodo_lower.replace("ã", "a")

    if metodo_lower in ["cartao", "pix", "boleto"]:
        return metodo_lower

    return None


# ============================================================================
# NORMALIZAÇÃO: CANAL
# ============================================================================

def normalizar_canal(canal: Any) -> Optional[str]:
    """
    Normaliza canal de origem para lowercase.

    Valores válidos: 'site', 'app', 'marketplace'

    Exemplos:
        'SITE' → 'site'
        'App ' → 'app'
        'marketplace' → 'marketplace'
        'telefone' → None
    """
    if pd.isna(canal):
        return None

    canal_lower = str(canal).strip().lower()

    if canal_lower in ["site", "app", "marketplace"]:
        return canal_lower

    return None


# ============================================================================
# CONVERSÃO: VALOR MONETÁRIO
# ============================================================================

def converter_valor(valor_str: Any) -> Optional[float]:
    """
    Converte valor em 2 formatos diferentes (vírgula vs ponto) para float.

    Formatos:
        '1.033,80' (ponto como separador de milhar, vírgula decimal) → 1033.80
        '3285.97' (ponto como decimal) → 3285.97
        '1033,80' (só vírgula) → 1033.80
        '3285' → 3285.0

    Retorna None se não conseguir converter.

    Exemplos:
        '1.033,80' → 1033.8
        '3285.97' → 3285.97
        '1033,80' → 1033.8
        'abc' → None
    """
    if pd.isna(valor_str):
        return None

    valor_str = str(valor_str).strip()

    # Se tem vírgula E ponto: '1.033,80'
    # Último é separador decimal
    if "," in valor_str and "." in valor_str:
        valor_str = valor_str.replace(".", "").replace(",", ".")
    # Se tem só vírgula: '1033,80'
    elif "," in valor_str:
        valor_str = valor_str.replace(",", ".")

    try:
        return float(valor_str)
    except:
        return None


# ============================================================================
# UTILITÁRIOS: QUARENTENA
# ============================================================================

def criar_registro_rejeicao(
    tabela: str,
    motivo: str,
    dados: Dict[str, Any],
    referencia_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cria um registro estruturado de rejeição para salvar em quarentena.

    Retorna dicionário com:
        - tabela: nome da tabela que rejeitou
        - motivo: motivo da rejeição (legível)
        - dados: dados brutos que foram rejeitados (para auditoria)
        - referencia_id: ID do registro (para rastreabilidade)

    Exemplos:
        criar_registro_rejeicao(
            'clientes',
            'CPF inválido: 00000000000',
            {'id_legado': 123, 'cpf': '00000000000'},
            '123'
        )
    """
    return {
        "tabela": tabela,
        "motivo": motivo,
        "dados": dados if isinstance(dados, dict) else dados.to_dict() if hasattr(dados, 'to_dict') else str(dados),
        "referencia_id": referencia_id
    }


def salvar_quarentena(
    rejeicoes: list,
    arquivo_saida: Path,
    tabela: str
) -> None:
    """
    Salva lista de rejeições em arquivo JSONL (JSON Lines).

    Formato: um JSON por linha, sem separador.

    Args:
        rejeicoes: lista de dicts com rejeições
        arquivo_saida: Path do arquivo a salvar
        tabela: nome da tabela (para logging)

    Exemplo:
        salvar_quarentena(
            rejeicoes,
            Path('tratamento/quarentena/clientes.jsonl'),
            'clientes'
        )
    """
    arquivo_saida.parent.mkdir(exist_ok=True, parents=True)

    with open(arquivo_saida, "w", encoding="utf-8") as f:
        for rej in rejeicoes:
            f.write(json.dumps(rej, ensure_ascii=False) + "\n")


def resumo_rejeicoes(rejeicoes: list) -> str:
    """
    Retorna string com resumo legível das rejeições.

    Agrupa por motivo e conta frequências.

    Exemplo de saída:
        CPF inválido: 5
        Data inválida: 3
        Cliente não existe: 2
    """
    if not rejeicoes:
        return "Nenhuma rejeição"

    motivos = {}
    for rej in rejeicoes:
        motivo = rej.get("motivo", "Desconhecido")
        motivos[motivo] = motivos.get(motivo, 0) + 1

    return "\n".join(f"  {motivo}: {count}" for motivo, count in sorted(motivos.items()))
