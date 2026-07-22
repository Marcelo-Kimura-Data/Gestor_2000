"""
Tratamento de dados: PAGAMENTOS_LEGADO.CSV

Fluxo:
1. Ler dados brutos de Bronze
2. Carregar referência de pedidos válidos (Silver)
3. Validar e normalizar cada pagamento
4. Separar válidos de rejeitados
5. Salvar válidos em Silver (CSV)
6. Salvar rejeitados em Quarentena (JSONL)
"""

import pandas as pd
import logging
from pathlib import Path
import sys

# Adicionar scripts ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from gestor_2000.config import PAGAMENTOS_LEGADO, PAGAMENTOS_QUARENTENA
from gestor_2000.database import DatabaseConnection
from .utils import (
    normalizar_data,
    normalizar_metodo,
    converter_valor,
    criar_registro_rejeicao,
    salvar_quarentena
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# UTILITÁRIOS
# ============================================================================

def carregar_pedidos_validos() -> set:
    """
    Carrega números de pedidos válidos do banco de dados.
    Retorna um set com todos os pedidos que foram inseridos com sucesso.
    """
    try:
        db = DatabaseConnection()
        db.connect()
        db.cursor.execute("SELECT num_pedido FROM pedidos")
        pedidos = set(row[0] for row in db.cursor.fetchall())
        db.disconnect()
        logger.info(f"Carregados {len(pedidos)} pedidos válidos do banco")
        return pedidos
    except Exception as e:
        logger.error(f"Erro ao carregar pedidos do banco: {e}")
        logger.error("Dica: execute tratar_pedidos.py primeiro")
        return set()


# ============================================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================================

def validar_pagamento(row: dict, pedidos_validos: set) -> tuple[bool, list, dict]:
    """
    Valida um pagamento individual.

    Retorna:
        (valido: bool, erros: list[str], pagamento_normalizado: dict)
    """
    erros = []
    pagamento = {}

    # 1. Validar id_pagto
    id_pagto = row.get("id_pagto")
    if pd.isna(id_pagto):
        erros.append("id_pagto vazio")
        return False, erros, {}

    try:
        pagamento["id_pagto"] = int(id_pagto)
    except (ValueError, TypeError):
        erros.append(f"id_pagto inválido: {id_pagto}")
        return False, erros, {}

    # 2. Validar num_pedido
    num_pedido = row.get("num_pedido")
    if pd.isna(num_pedido):
        erros.append("num_pedido vazio")
    else:
        try:
            num_pedido_int = int(num_pedido)
            if num_pedido_int not in pedidos_validos:
                erros.append(f"Pedido não existe: {num_pedido}")
            else:
                pagamento["num_pedido"] = num_pedido_int
        except (ValueError, TypeError):
            erros.append(f"num_pedido inválido: {num_pedido}")

    # 3. Validar e converter valor_pago (deve ser positivo)
    valor = converter_valor(row.get("valor_pago"))
    if valor is None:
        erros.append(f"Valor_pago inválido: {row.get('valor_pago')}")
    elif valor <= 0:
        erros.append(f"Valor_pago deve ser positivo (> 0): {valor} (REEMBOLSO/AJUSTE - QUARENTENA)")
    else:
        pagamento["valor_pago"] = valor

    # 4. Validar e normalizar método
    metodo_norm = normalizar_metodo(row.get("metodo"))
    if not metodo_norm:
        erros.append(f"Método inválido: {row.get('metodo')}")
    else:
        pagamento["metodo"] = metodo_norm

    # 5. Validar e normalizar data
    data_norm = normalizar_data(row.get("dt_pagto"))
    if not data_norm:
        erros.append(f"Data de pagamento inválida: {row.get('dt_pagto')}")
    else:
        pagamento["dt_pagto"] = data_norm

    # Retornar resultado
    valido = len(erros) == 0

    return valido, erros, pagamento if valido else {}


# ============================================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================================

def processar_pagamentos():
    """
    Processa arquivo de pagamentos: validação, normalização, quarentena.
    """
    logger.info("=" * 80)
    logger.info("PROCESSANDO: PAGAMENTOS_LEGADO.CSV")
    logger.info("=" * 80)

    # Carregar pedidos válidos
    pedidos_validos = carregar_pedidos_validos()
    if not pedidos_validos:
        logger.error("Não foi possível carregar pedidos válidos. Aborte.")
        return None, []

    # Ler arquivo bruto
    if not PAGAMENTOS_LEGADO.exists():
        logger.error(f"Arquivo não encontrado: {PAGAMENTOS_LEGADO}")
        return None, []

    logger.info(f"Lendo: {PAGAMENTOS_LEGADO}")
    df = pd.read_csv(PAGAMENTOS_LEGADO, sep=";", encoding="latin-1")
    logger.info(f"  Total de registros: {len(df)}")

    # Processar cada pagamento
    pagamentos_validos = []
    pagamentos_rejeitados = []

    for idx, row in df.iterrows():
        valido, erros, pagamento = validar_pagamento(row.to_dict(), pedidos_validos)

        if valido:
            pagamentos_validos.append(pagamento)
        else:
            rejeicao = criar_registro_rejeicao(
                tabela="pagamentos",
                motivo="; ".join(erros),
                dados=row.to_dict(),
                referencia_id=str(row.get("id_pagto", "?"))
            )
            pagamentos_rejeitados.append(rejeicao)

    # Log de resultados
    total = len(pagamentos_validos) + len(pagamentos_rejeitados)
    logger.info("")
    logger.info("RESULTADO:")
    logger.info(f"  ✓ Válidos: {len(pagamentos_validos)} ({100*len(pagamentos_validos)/total:.1f}%)" if total > 0 else f"  ✓ Válidos: {len(pagamentos_validos)}")
    logger.info(f"  ✗ Rejeitados: {len(pagamentos_rejeitados)} ({100*len(pagamentos_rejeitados)/total:.1f}%)" if total > 0 else f"  ✗ Rejeitados: {len(pagamentos_rejeitados)}")

    if pagamentos_rejeitados:
        logger.info("")
        logger.info("Motivos de rejeição:")
        motivos_dict = {}
        for rej in pagamentos_rejeitados:
            motivo_base = rej['motivo'].split(';')[0].strip()
            motivos_dict[motivo_base] = motivos_dict.get(motivo_base, 0) + 1

        for motivo, count in sorted(motivos_dict.items(), key=lambda x: -x[1]):
            pct = 100 * count / len(pagamentos_rejeitados)
            logger.info(f"  • {motivo}: {count} ({pct:.1f}%)")

    # Salvar rejeitados em quarentena
    if pagamentos_rejeitados:
        salvar_quarentena(pagamentos_rejeitados, PAGAMENTOS_QUARENTENA, "pagamentos")
        logger.info(f"✓ Registros rejeitados: {PAGAMENTOS_QUARENTENA}")

    # Inserir dados validados no banco
    if pagamentos_validos:
        try:
            db = DatabaseConnection()
            db.connect()
            db.insert_many(
                table="pagamentos",
                columns=["id_pagto", "num_pedido", "valor_pago", "metodo", "dt_pagto"],
                records=pagamentos_validos
            )
            db.disconnect()
            logger.info(f"✓ {len(pagamentos_validos)} pagamentos inseridos no banco")
        except Exception as e:
            logger.error(f"✗ Erro ao inserir no banco: {e}")
            raise
    else:
        logger.warning("⚠ Nenhum pagamento válido para inserir")

    logger.info("=" * 80 + "\n")

    return len(pagamentos_validos), len(pagamentos_rejeitados)


# ============================================================================
# EXECUTAR SE CHAMADO DIRETO
# ============================================================================

if __name__ == "__main__":
    df_pagamentos, rejeitados = processar_pagamentos()
