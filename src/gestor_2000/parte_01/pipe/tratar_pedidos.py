"""
Tratamento de dados: PEDIDOS_LEGADO.CSV

Fluxo:
1. Ler dados brutos de Bronze
2. Carregar referência de clientes válidos (Silver)
3. Validar e normalizar cada pedido
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

from gestor_2000.config import PEDIDOS_LEGADO, PEDIDOS_QUARENTENA, CLIENTES_LEGADO
from gestor_2000.database import DatabaseConnection
from .utils import (
    normalizar_cpf,
    normalizar_data,
    normalizar_status,
    normalizar_canal,
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

def carregar_cpfs_validos() -> set:
    """
    Carrega CPFs válidos do banco de dados (tabela clientes).
    Retorna um set com todos os CPFs que foram inseridos com sucesso.
    """
    try:
        db = DatabaseConnection()
        db.connect()
        db.cursor.execute("SELECT cpf FROM clientes")
        cpfs = set(row[0] for row in db.cursor.fetchall())
        db.disconnect()
        logger.info(f"Carregados {len(cpfs)} CPFs válidos do banco")
        return cpfs
    except Exception as e:
        logger.error(f"Erro ao carregar CPFs do banco: {e}")
        logger.error("Dica: execute tratar_clientes.py primeiro")
        return set()


# ============================================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================================

def validar_pedido(row: dict, cpfs_validos: set) -> tuple[bool, list, dict]:
    """
    Valida um pedido individual.

    Retorna:
        (valido: bool, erros: list[str], pedido_normalizado: dict)
    """
    erros = []
    pedido = {}

    # 1. Validar num_pedido
    num_pedido = row.get("num_pedido")
    if pd.isna(num_pedido):
        erros.append("num_pedido vazio")
        return False, erros, {}

    try:
        pedido["num_pedido"] = int(num_pedido)
    except (ValueError, TypeError):
        erros.append(f"num_pedido inválido: {num_pedido}")
        return False, erros, {}

    # 2. Validar e normalizar CPF cliente
    cpf_norm = normalizar_cpf(row.get("cpf_cliente"))
    if not cpf_norm:
        erros.append(f"CPF cliente inválido: {row.get('cpf_cliente')}")
    elif cpf_norm not in cpfs_validos:
        erros.append(f"Cliente não existe: {cpf_norm}")
    else:
        pedido["cpf_cliente"] = cpf_norm

    # 3. Validar e normalizar status
    status_norm = normalizar_status(row.get("status"))
    if not status_norm:
        erros.append(f"Status inválido: {row.get('status')}")
    else:
        pedido["status"] = status_norm

    # 4. Validar e converter valor_total
    valor = converter_valor(row.get("valor_total"))
    if valor is None:
        erros.append(f"Valor_total inválido: {row.get('valor_total')}")
    elif valor <= 0:
        erros.append(f"Valor_total deve ser > 0: {valor}")
    else:
        pedido["valor_total"] = valor

    # 5. Validar e normalizar data
    data_norm = normalizar_data(row.get("dt_pedido"))
    if not data_norm:
        erros.append(f"Data de pedido inválida: {row.get('dt_pedido')}")
    else:
        pedido["dt_pedido"] = data_norm

    # 6. Validar e normalizar canal
    canal_norm = normalizar_canal(row.get("canal"))
    if not canal_norm:
        erros.append(f"Canal inválido: {row.get('canal')}")
    else:
        pedido["canal"] = canal_norm

    # Retornar resultado
    valido = len(erros) == 0

    return valido, erros, pedido if valido else {}


# ============================================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================================

def processar_pedidos():
    """
    Processa arquivo de pedidos: validação, normalização, quarentena.
    """
    logger.info("=" * 80)
    logger.info("PROCESSANDO: PEDIDOS_LEGADO.CSV")
    logger.info("=" * 80)

    # Carregar CPFs válidos
    cpfs_validos = carregar_cpfs_validos()
    if not cpfs_validos:
        logger.error("Não foi possível carregar CPFs válidos. Aborte.")
        return None, []

    # DEBUG: Mostrar exemplo de CPFs carregados
    if cpfs_validos:
        exemplo_cpf_banco = list(cpfs_validos)[0]
        logger.info(f"  Exemplo de CPF no banco: '{exemplo_cpf_banco}' (tipo: {type(exemplo_cpf_banco).__name__}, len: {len(exemplo_cpf_banco)})")

    # Ler arquivo bruto
    if not PEDIDOS_LEGADO.exists():
        logger.error(f"Arquivo não encontrado: {PEDIDOS_LEGADO}")
        return None, []

    logger.info(f"Lendo: {PEDIDOS_LEGADO}")
    df = pd.read_csv(PEDIDOS_LEGADO, sep=";", encoding="latin-1")
    logger.info(f"  Total de registros: {len(df)}")

    # DEBUG: Mostrar exemplo de CPF do arquivo
    if len(df) > 0:
        exemplo_cpf_arquivo = df.iloc[0]['cpf_cliente']
        cpf_norm_exemplo = normalizar_cpf(exemplo_cpf_arquivo)
        logger.info(f"  Exemplo de CPF no arquivo: '{exemplo_cpf_arquivo}' → normalizado: '{cpf_norm_exemplo}' (existe no banco: {cpf_norm_exemplo in cpfs_validos if cpf_norm_exemplo else False})")

    # Processar cada pedido
    pedidos_validos = []
    pedidos_rejeitados = []
    num_pedidos_vistos = set()  # Rastrear num_pedido para detectar duplicatas

    for idx, row in df.iterrows():
        valido, erros, pedido = validar_pedido(row.to_dict(), cpfs_validos)

        # Verificar num_pedido duplicado (mesmo que valido)
        if valido and "num_pedido" in pedido:
            num_pedido = pedido["num_pedido"]
            if num_pedido in num_pedidos_vistos:
                valido = False
                erros.append(f"num_pedido duplicado: {num_pedido}")
            else:
                num_pedidos_vistos.add(num_pedido)

        if valido:
            pedidos_validos.append(pedido)
        else:
            rejeicao = criar_registro_rejeicao(
                tabela="pedidos",
                motivo="; ".join(erros),
                dados=row.to_dict(),
                referencia_id=str(row.get("num_pedido", "?"))
            )
            pedidos_rejeitados.append(rejeicao)

    # Log de resultados
    total = len(pedidos_validos) + len(pedidos_rejeitados)
    logger.info("")
    logger.info("RESULTADO:")
    logger.info(f"  ✓ Válidos: {len(pedidos_validos)} ({100*len(pedidos_validos)/total:.1f}%)" if total > 0 else f"  ✓ Válidos: {len(pedidos_validos)}")
    logger.info(f"  ✗ Rejeitados: {len(pedidos_rejeitados)} ({100*len(pedidos_rejeitados)/total:.1f}%)" if total > 0 else f"  ✗ Rejeitados: {len(pedidos_rejeitados)}")

    if pedidos_rejeitados:
        logger.info("")
        logger.info("Motivos de rejeição:")
        motivos_dict = {}
        for rej in pedidos_rejeitados:
            motivo_base = rej['motivo'].split(';')[0].strip()
            motivos_dict[motivo_base] = motivos_dict.get(motivo_base, 0) + 1

        for motivo, count in sorted(motivos_dict.items(), key=lambda x: -x[1]):
            pct = 100 * count / len(pedidos_rejeitados)
            logger.info(f"  • {motivo}: {count} ({pct:.1f}%)")

    # Salvar rejeitados em quarentena
    if pedidos_rejeitados:
        salvar_quarentena(pedidos_rejeitados, PEDIDOS_QUARENTENA, "pedidos")
        logger.info(f"✓ Registros rejeitados: {PEDIDOS_QUARENTENA}")

    # Inserir dados validados no banco
    if pedidos_validos:
        try:
            db = DatabaseConnection()
            db.connect()
            db.insert_many(
                table="pedidos",
                columns=["num_pedido", "cpf_cliente", "status", "valor_total", "dt_pedido", "canal"],
                records=pedidos_validos
            )
            db.disconnect()
            logger.info(f"✓ {len(pedidos_validos)} pedidos inseridos no banco")
        except Exception as e:
            logger.error(f"✗ Erro ao inserir no banco: {e}")
            raise
    else:
        logger.warning("⚠ Nenhum pedido válido para inserir")

    logger.info("=" * 80 + "\n")

    return len(pedidos_validos), len(pedidos_rejeitados)


# ============================================================================
# EXECUTAR SE CHAMADO DIRETO
# ============================================================================

if __name__ == "__main__":
    df_pedidos, rejeitados = processar_pedidos()
