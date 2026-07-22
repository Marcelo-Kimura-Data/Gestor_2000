"""
Configurações centralizadas do projeto Gestor2000.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Raiz do projeto
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Carregar variáveis de ambiente do .env (procurar no diretório raiz)
env_file = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_file)

# Diretórios de dados
DADOS_DIR = PROJECT_ROOT / "arquivos_projeto" / "parte1_pipeline" / "dados"
QUARENTENA_DIR = PROJECT_ROOT / "quarentena"

# Criar diretório de quarentena se não existir
QUARENTENA_DIR.mkdir(parents=True, exist_ok=True)

# Arquivos de entrada (CSV brutos)
CLIENTES_LEGADO = DADOS_DIR / "clientes_legado.csv"
PEDIDOS_LEGADO = DADOS_DIR / "pedidos_legado.csv"
PAGAMENTOS_LEGADO = DADOS_DIR / "pagamentos_legado.csv"

# Arquivos de quarentena (dados rejeitados)
CLIENTES_QUARENTENA = QUARENTENA_DIR / "clientes_rejeitados.jsonl"
PEDIDOS_QUARENTENA = QUARENTENA_DIR / "pedidos_rejeitados.jsonl"
PAGAMENTOS_QUARENTENA = QUARENTENA_DIR / "pagamentos_rejeitados.jsonl"

# Banco de dados
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

# Schema SQL
SCHEMA_FILE = PROJECT_ROOT / "src" / "gestor_2000" / "parte_01" / "schema" / "schema.sql"
