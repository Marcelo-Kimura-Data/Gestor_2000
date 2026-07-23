#!/usr/bin/env python
"""
Script para calcular métricas de qualidade dos dados carregados.
Conecta ao banco e gera DATA_QUALITY.md automaticamente.
"""

import sys
import json
from pathlib import Path

# Adicionar src ao path (projeto_root é a raiz do projeto, 3 níveis acima)
# __file__ = .../src/gestor_2000/parte_01/calcular_metricas.py
# .parent.parent.parent = .../src/
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gestor_2000.database import DatabaseConnection
from gestor_2000.config import CLIENTES_QUARENTENA, PEDIDOS_QUARENTENA, PAGAMENTOS_QUARENTENA

def contar_rejeicoes(arquivo_quarentena):
    """Conta registros em arquivo JSONL."""
    if not arquivo_quarentena.exists():
        return 0
    with open(arquivo_quarentena, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)

def calcular_metricas():
    """Calcula todas as métricas necessárias."""

    print("\n" + "="*80)
    print("CALCULANDO MÉTRICAS DE QUALIDADE")
    print("="*80)

    try:
        db = DatabaseConnection()
        db.connect()
    except Exception as e:
        print(f"\n❌ Erro ao conectar ao banco de dados: {e}")
        print("Verifique se PostgreSQL está rodando e configurado corretamente.")
        sys.exit(1)

    # ========================================================================
    # 1. CONTAR REGISTROS NO BANCO
    # ========================================================================
    print("\n1. Contando registros inseridos no banco...")

    db.cursor.execute("SELECT COUNT(*) FROM clientes")
    clientes_inseridos = db.cursor.fetchone()[0]

    db.cursor.execute("SELECT COUNT(*) FROM pedidos")
    pedidos_inseridos = db.cursor.fetchone()[0]

    db.cursor.execute("SELECT COUNT(*) FROM pagamentos")
    pagamentos_inseridos = db.cursor.fetchone()[0]

    print(f"  ✓ Clientes: {clientes_inseridos}")
    print(f"  ✓ Pedidos: {pedidos_inseridos}")
    print(f"  ✓ Pagamentos: {pagamentos_inseridos}")

    # ========================================================================
    # 2. CONTAR REJEIÇÕES
    # ========================================================================
    print("\n2. Contando registros rejeitados...")

    clientes_rejeitados = contar_rejeicoes(CLIENTES_QUARENTENA)
    pedidos_rejeitados = contar_rejeicoes(PEDIDOS_QUARENTENA)
    pagamentos_rejeitados = contar_rejeicoes(PAGAMENTOS_QUARENTENA)

    print(f"  ✓ Clientes rejeitados: {clientes_rejeitados}")
    print(f"  ✓ Pedidos rejeitados: {pedidos_rejeitados}")
    print(f"  ✓ Pagamentos rejeitados: {pagamentos_rejeitados}")

    # ========================================================================
    # 3. MÉTRICA (A): RECEITA TOTAL
    # ========================================================================
    print("\n3. Calculando receita total...")

    db.cursor.execute("SELECT SUM(valor_pago) FROM pagamentos")
    receita_total = db.cursor.fetchone()[0] or 0.0

    print(f"  ✓ Receita total (soma de valor_pago): R$ {receita_total:,.2f}")

    # ========================================================================
    # 4. MÉTRICA (B): DIVERGÊNCIAS VALOR_PEDIDO vs VALOR_PAGO
    # ========================================================================
    print("\n4. Calculando divergências entre valor_pedido e valor_pago...")

    # Total de pedidos
    db.cursor.execute("SELECT COUNT(*) FROM pedidos")
    total_pedidos = db.cursor.fetchone()[0]

    # Pedidos com valor_total diferente da soma de pagamentos
    db.cursor.execute("""
        SELECT COUNT(DISTINCT p.num_pedido)
        FROM pedidos p
        LEFT JOIN (
            SELECT num_pedido, SUM(valor_pago) as total_pago
            FROM pagamentos
            GROUP BY num_pedido
        ) pag ON p.num_pedido = pag.num_pedido
        WHERE p.valor_total != COALESCE(pag.total_pago, 0)
    """)
    pedidos_divergencia = db.cursor.fetchone()[0]
    percentual_divergencia = (pedidos_divergencia / total_pedidos * 100) if total_pedidos > 0 else 0

    print(f"  ✓ Pedidos com divergência: {pedidos_divergencia} de {total_pedidos} ({percentual_divergencia:.1f}%)")

    # Detalhe: pedidos não pagos, pagos parcialmente, pagos demais
    db.cursor.execute("""
        SELECT
            COUNT(CASE WHEN COALESCE(total_pago, 0) = 0 THEN 1 END) as nao_pagos,
            COUNT(CASE WHEN COALESCE(total_pago, 0) > 0 AND COALESCE(total_pago, 0) < p.valor_total THEN 1 END) as pago_parcial,
            COUNT(CASE WHEN COALESCE(total_pago, 0) > p.valor_total THEN 1 END) as pago_demais,
            COUNT(CASE WHEN COALESCE(total_pago, 0) = p.valor_total THEN 1 END) as pago_correto
        FROM pedidos p
        LEFT JOIN (
            SELECT num_pedido, SUM(valor_pago) as total_pago
            FROM pagamentos
            GROUP BY num_pedido
        ) pag ON p.num_pedido = pag.num_pedido
    """)
    nao_pagos, pago_parcial, pago_demais, pago_correto = db.cursor.fetchone()

    print(f"    - Não pagos: {nao_pagos}")
    print(f"    - Pago parcial: {pago_parcial}")
    print(f"    - Pago demais: {pago_demais}")
    print(f"    - Pago correto: {pago_correto}")

    # ========================================================================
    # 5. RESUMO DE REJEIÇÕES
    # ========================================================================
    print("\n5. Resumo de rejeições por motivo...")

    # Clientes - motivos principais
    print("\n  Clientes rejeitados:")
    motivos_clientes = {}
    if CLIENTES_QUARENTENA.exists():
        with open(CLIENTES_QUARENTENA, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    motivo = record.get('motivo', 'Desconhecido').split(';')[0].strip()
                    motivos_clientes[motivo] = motivos_clientes.get(motivo, 0) + 1
                except json.JSONDecodeError as e:
                    print(f"    ⚠️ Erro ao parsear JSON: {e}")
                except Exception as e:
                    print(f"    ⚠️ Erro inesperado: {e}")
    else:
        print(f"    ⚠️ Arquivo não encontrado: {CLIENTES_QUARENTENA}")

    if motivos_clientes:
        for motivo, count in sorted(motivos_clientes.items(), key=lambda x: -x[1])[:3]:
            print(f"    - {motivo}: {count}")
    else:
        print("    (Nenhum registro rejeitado)")

    db.disconnect()

    # ========================================================================
    # RETORNAR DADOS PARA DATA_QUALITY.MD
    # ========================================================================
    metrics = {
        "clientes_inseridos": clientes_inseridos,
        "clientes_rejeitados": clientes_rejeitados,
        "pedidos_inseridos": pedidos_inseridos,
        "pedidos_rejeitados": pedidos_rejeitados,
        "pagamentos_inseridos": pagamentos_inseridos,
        "pagamentos_rejeitados": pagamentos_rejeitados,
        "receita_total": receita_total,
        "pedidos_divergencia": pedidos_divergencia,
        "total_pedidos": total_pedidos,
        "percentual_divergencia": percentual_divergencia,
        "nao_pagos": nao_pagos,
        "pago_parcial": pago_parcial,
        "pago_demais": pago_demais,
        "pago_correto": pago_correto,
    }

    print("\n" + "="*80)
    print("MÉTRICAS CALCULADAS COM SUCESSO")
    print("="*80 + "\n")

    return metrics

if __name__ == "__main__":
    calcular_metricas()
