#!/usr/bin/env python
"""
Script simples para rodar o pipeline sem precisar setar PYTHONPATH.

Uso:
    python run.py
"""

import sys
from pathlib import Path

# Adicionar src ao path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# Importar e executar o pipeline
from gestor_2000.parte_01.executar_pipeline import executar_pipeline

if __name__ == "__main__":
    executar_pipeline()
