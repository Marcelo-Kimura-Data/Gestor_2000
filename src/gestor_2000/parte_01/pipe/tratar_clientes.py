"""
Tratamento de dados: CLIENTES_LEGADO.CSV

Fluxo:
1. Ler dados brutos de Bronze
2. Validar e normalizar cada registro
3. Separar válidos de rejeitados
4. Salvar válidos em Silver (CSV)
5. Salvar rejeitados em Quarentena (JSONL)
"""

import pandas as pd
import logging
from pathlib import Path
import sys

# Adicionar scripts ao path para importar config e utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from gestor_2000.config import CLIENTES_LEGADO, CLIENTES_QUARENTENA
from gestor_2000.database import DatabaseConnection
from .utils import (
    normalizar_cpf,
    normalizar_data,
    normalizar_cidade,
    validar_email,
    criar_registro_rejeicao,
    salvar_quarentena,
    resumo_rejeicoes
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================================

def validar_cliente(row: dict) -> tuple[bool, list, dict]:
    """
    Valida um cliente individual.

    Retorna:
        (valido: bool, erros: list[str], cliente_normalizado: dict)
    """
    erros = []
    cliente = {}

    # 1. Validar id_legado
    id_legado = row.get("id_legado")
    if pd.isna(id_legado):
        erros.append("id_legado vazio")
    else:
        try:
            cliente["id_legado"] = int(id_legado)
        except (ValueError, TypeError):
            erros.append(f"id_legado inválido: {id_legado}")

    # 2. Validar e normalizar CPF
    cpf_norm = normalizar_cpf(row.get("cpf"))
    if not cpf_norm:
        erros.append(f"CPF inválido: {row.get('cpf')}")
    else:
        cliente["cpf"] = cpf_norm

    # 3. Validar nome
    nome = str(row.get("nome", "")).strip() if pd.notna(row.get("nome")) else None
    if not nome:
        erros.append("Nome vazio")
    else:
        cliente["nome"] = nome

    # 4. Validar e normalizar cidade
    cidade_norm = normalizar_cidade(row.get("cidade"))
    if not cidade_norm:
        erros.append(f"Cidade inválida: {row.get('cidade')}")
    else:
        cliente["cidade"] = cidade_norm

    # 5. Email obrigatório e validado
    email = str(row.get("email", "")).strip() if pd.notna(row.get("email")) else None
    if not email:
        erros.append("Email ausente")
    elif not validar_email(email):
        erros.append(f"Email inválido: {email}")
    else:
        cliente["email"] = email

    # 6. Validar e normalizar data
    data_norm = normalizar_data(row.get("dt_cadastro"))
    if not data_norm:
        erros.append(f"Data de cadastro inválida: {row.get('dt_cadastro')}")
    else:
        cliente["dt_cadastro"] = data_norm

    # Retornar resultado
    valido = len(erros) == 0

    return valido, erros, cliente if valido else {}


# ============================================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================================

def processar_clientes():
    """
    Processa arquivo de clientes: validação, normalização, quarentena e inserção no banco.
    """
    logger.info("=" * 80)
    logger.info("PROCESSANDO: CLIENTES_LEGADO.CSV")
    logger.info("=" * 80)

    # Ler arquivo bruto
    if not CLIENTES_LEGADO.exists():
        logger.error(f"Arquivo não encontrado: {CLIENTES_LEGADO}")
        return None, []

    logger.info(f"Lendo: {CLIENTES_LEGADO}")
    df = pd.read_csv(CLIENTES_LEGADO, sep=";", encoding="latin-1")
    logger.info(f"  Total de registros: {len(df)}")

    # Processar cada cliente
    clientes_validos = []
    clientes_rejeitados = []
    cpfs_vistos = set()  # Rastrear CPFs para detectar duplicatas

    for idx, row in df.iterrows():
        valido, erros, cliente = validar_cliente(row.to_dict())

        # Verificar CPF duplicado (mesmo que valido)
        if valido and "cpf" in cliente:
            cpf = cliente["cpf"]
            if cpf in cpfs_vistos:
                valido = False
                erros.append(f"CPF duplicado: {cpf}")
            else:
                cpfs_vistos.add(cpf)

        if valido:
            clientes_validos.append(cliente)
        else:
            rejeicao = criar_registro_rejeicao(
                tabela="clientes",
                motivo="; ".join(erros),
                dados=row.to_dict(),
                referencia_id=str(row.get("id_legado", "?"))
            )
            clientes_rejeitados.append(rejeicao)

    # Log de resultados
    logger.info("")
    logger.info("RESULTADO:")
    logger.info(f"  ✓ Válidos: {len(clientes_validos)}")
    logger.info(f"  ✗ Rejeitados: {len(clientes_rejeitados)}")

    if clientes_rejeitados:
        logger.info("")
        logger.info("Motivos de rejeição:")
        logger.info(resumo_rejeicoes(clientes_rejeitados))

    # Salvar rejeitados em quarentena
    if clientes_rejeitados:
        salvar_quarentena(clientes_rejeitados, CLIENTES_QUARENTENA, "clientes")
        logger.info(f"✓ Registros rejeitados: {CLIENTES_QUARENTENA}")

    # Inserir dados validados no banco
    if clientes_validos:
        try:
            db = DatabaseConnection()
            db.connect()
            db.insert_many(
                table="clientes",
                columns=["id_legado", "cpf", "nome", "cidade", "email", "dt_cadastro"],
                records=clientes_validos
            )
            db.disconnect()
            logger.info(f"✓ {len(clientes_validos)} clientes inseridos no banco")
        except Exception as e:
            logger.error(f"✗ Erro ao inserir no banco: {e}")
            raise
    else:
        logger.warning("⚠ Nenhum cliente válido para inserir")

    logger.info("=" * 80 + "\n")

    return len(clientes_validos), len(clientes_rejeitados)


# ============================================================================
# EXECUTAR SE CHAMADO DIRETO
# ============================================================================

if __name__ == "__main__":
    df_clientes, rejeitados = processar_clientes()
