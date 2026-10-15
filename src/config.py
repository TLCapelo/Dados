"""
Carregador de configuração YAML.
"""
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Carrega configuração do arquivo YAML.
    
    Args:
        config_path: Caminho para o arquivo config.yaml. Se None, usa o padrão.
        
    Returns:
        Dicionário com a configuração carregada.
    """
    if config_path is None:
        # Procura config.yaml na raiz do projeto
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Obtém valor aninhado da configuração usando notação de ponto.
    
    Exemplo: get_config_value(config, "open_meteo.cities")
    """
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value