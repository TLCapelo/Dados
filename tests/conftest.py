import sys
from pathlib import Path

# Adiciona src ao path para todos os testes
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))