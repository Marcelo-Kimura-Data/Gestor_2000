"""
Orquestrador do pipeline de migração Gestor2000 → PostgreSQL.

Fluxo:
1. Aplica schema no banco de dados
2. Processa e carrega clientes
3. Processa e carrega pedidos
4. Processa e carrega pagamentos
"""

import logging
import sys
from pathlib import Path

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gestor_2000.config import SCHEMA_FILE
from gestor_2000.database import DatabaseConnection
from gestor_2000.parte_01.pipe.tratar_clientes import processar_clientes
from gestor_2000.parte_01.pipe.tratar_pedidos import processar_pedidos
from gestor_2000.parte_01.pipe.tratar_pagamentos import processar_pagamentos

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def executar_pipeline():
    """Executa o pipeline completo de migração."""
    logger.info("\n" + "=" * 80)
    logger.info("INICIANDO PIPELINE DE MIGRAÇÃO GESTOR2000 → POSTGRESQL")
    logger.info("=" * 80 + "\n")

    try:
        # 1. Aplicar schema
        logger.info("ETAPA 1: Aplicando schema no banco de dados...")
        db = DatabaseConnection()
        db.connect()
        db.execute_schema(SCHEMA_FILE)

        # Limpar dados antigos (para idempotência)
        logger.info("Limpando dados antigos...")
        try:
            db.cursor.execute("DELETE FROM pagamentos")
            db.cursor.execute("DELETE FROM pedidos")
            db.cursor.execute("DELETE FROM clientes")
            db.connection.commit()
            logger.info("✓ Tabelas limpas")
        except Exception as e:
            logger.warning(f"Aviso ao limpar tabelas: {e}")
            db.connection.rollback()

        db.disconnect()
        logger.info("✓ Schema aplicado com sucesso\n")

        # 2. Processar clientes
        logger.info("ETAPA 2: Processando clientes...")
        clientes_ok, clientes_rej = processar_clientes()
        logger.info(f"Resumo: {clientes_ok} inseridos, {clientes_rej} rejeitados\n")

        # 3. Processar pedidos
        logger.info("ETAPA 3: Processando pedidos...")
        pedidos_ok, pedidos_rej = processar_pedidos()
        logger.info(f"Resumo: {pedidos_ok} inseridos, {pedidos_rej} rejeitados\n")

        # 4. Processar pagamentos
        logger.info("ETAPA 4: Processando pagamentos...")
        pagamentos_ok, pagamentos_rej = processar_pagamentos()
        logger.info(f"Resumo: {pagamentos_ok} inseridos, {pagamentos_rej} rejeitados\n")

        # Resumo final
        logger.info("=" * 80)
        logger.info("PIPELINE CONCLUÍDO COM SUCESSO!")
        logger.info("=" * 80)
        logger.info(f"""
Resumo final:
  Clientes:    {clientes_ok:5d} inseridos | {clientes_rej:3d} rejeitados
  Pedidos:     {pedidos_ok:5d} inseridos | {pedidos_rej:3d} rejeitados
  Pagamentos:  {pagamentos_ok:5d} inseridos | {pagamentos_rej:3d} rejeitados

Arquivos de quarentena (dados rejeitados) disponíveis em: quarentena/
        """)

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("ERRO NA EXECUÇÃO DO PIPELINE")
        logger.error("=" * 80)
        logger.error(f"Erro: {e}")
        raise


if __name__ == "__main__":
    executar_pipeline()
