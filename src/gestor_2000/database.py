"""
Gerenciamento de conexão e operações com PostgreSQL.
"""

import os
import logging
from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2 import sql, errors
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Gerencia conexão com PostgreSQL e operações básicas."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None,
    ):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", 5432))
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "")
        self.database = database or os.getenv("POSTGRES_DB", "postgres")

        self.connection = None
        self.cursor = None

    def connect(self) -> None:
        """Estabelece conexão com banco de dados."""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=5
            )
            self.cursor = self.connection.cursor()
            logger.info(f"✓ Conectado ao banco: {self.database}@{self.host}:{self.port}")
        except psycopg2.OperationalError as e:
            logger.error(f"✗ Erro ao conectar: {e}")
            raise

    def disconnect(self) -> None:
        """Fecha conexão com banco de dados."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Desconectado do banco")

    def execute_schema(self, schema_path: Path) -> None:
        """Executa arquivo SQL de schema."""
        if not self.connection:
            self.connect()

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            self.cursor.execute(schema_sql)
            self.connection.commit()
            logger.info(f"✓ Schema aplicado: {schema_path}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"✗ Erro ao aplicar schema: {e}")
            raise

    def insert_many(
        self,
        table: str,
        columns: List[str],
        records: List[Dict[str, Any]]
    ) -> int:
        """
        Insere múltiplos registros na tabela.

        Args:
            table: nome da tabela
            columns: lista de nomes de colunas
            records: lista de dicts com dados

        Returns:
            Número de registros inseridos
        """
        if not records:
            logger.warning(f"Nenhum registro para inserir em {table}")
            return 0

        if not self.connection:
            self.connect()

        try:
            # Preparar SQL: INSERT INTO table (col1, col2, ...) VALUES (%s, %s, ...)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

            # Converter dicts para tuplas na ordem das colunas
            rows = [tuple(record.get(col) for col in columns) for record in records]

            # Executar em batch
            self.cursor.executemany(insert_sql, rows)
            self.connection.commit()

            count = self.cursor.rowcount
            logger.info(f"✓ {count} registros inseridos em {table}")
            return count

        except errors.UniqueViolation as e:
            self.connection.rollback()
            logger.error(f"✗ Violação de chave única em {table}: {e}")
            raise
        except errors.ForeignKeyViolation as e:
            self.connection.rollback()
            logger.error(f"✗ Violação de chave estrangeira em {table}: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            logger.error(f"✗ Erro ao inserir em {table}: {e}")
            raise

    def clear_table(self, table: str, cascade: bool = False) -> None:
        """
        Limpa todos os dados de uma tabela.

        Args:
            table: nome da tabela
            cascade: usar CASCADE para apagar dependências
        """
        if not self.connection:
            self.connect()

        try:
            cascade_sql = " CASCADE" if cascade else ""
            self.cursor.execute(f"DELETE FROM {table}{cascade_sql}")
            self.connection.commit()
            logger.info(f"✓ Tabela {table} limpa")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"✗ Erro ao limpar {table}: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def get_db_connection() -> DatabaseConnection:
    """Factory para criar conexão com banco."""
    return DatabaseConnection()
