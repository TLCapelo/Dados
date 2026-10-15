"""
Pipeline Principal - Orquestrador do ETL
Executa extração, transformação e carga dos dados de clima, crypto e economia.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.extract.open_meteo import OpenMeteoExtractor
from src.extract.coingecko import CoinGeckoExtractor
from src.extract.bcb import BCBExtractor
from src.transform.clean import DataCleaner
from src.transform.enrich import DataEnricher
from src.transform.validate import DataValidator
from src.load.to_parquet import ParquetLoader
from src.load.to_powerbi import PowerBIPreparer
from config import load_config


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configura logging do pipeline."""
    log_config = config.get("pipeline", {}).get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO"))
    log_file = log_config.get("file", "logs/pipeline.log")
    
    # Cria diretório de logs
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def run_extraction(config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Executa extração de todas as fontes."""
    logger.info("=== INICIANDO EXTRAÇÃO ===")
    raw_data = {}
    
    # Open-Meteo (Clima)
    try:
        logger.info("Extraindo dados do Open-Meteo...")
        extractor = OpenMeteoExtractor(config["open_meteo"])
        raw_data["clima"] = extractor.extract_all()
        logger.info(f"Open-Meteo: {len(raw_data['clima'].get('daily', []))} registros diários, "
                   f"{len(raw_data['clima'].get('hourly', []))} registros horários")
    except Exception as e:
        logger.error(f"Erro ao extrair Open-Meteo: {e}")
        raw_data["clima"] = {"daily": [], "hourly": [], "error": str(e)}
    
    # CoinGecko (Crypto)
    try:
        logger.info("Extraindo dados do CoinGecko...")
        extractor = CoinGeckoExtractor(config["coingecko"])
        raw_data["crypto"] = extractor.extract_all()
        logger.info(f"CoinGecko: {len(raw_data['crypto'].get('market', []))} moedas, "
                   f"{len(raw_data['crypto'].get('history', []))} registros históricos")
    except Exception as e:
        logger.error(f"Erro ao extrair CoinGecko: {e}")
        raw_data["crypto"] = {"market": [], "history": [], "error": str(e)}
    
    # BCB/SGS (Economia)
    try:
        logger.info("Extraindo dados do BCB/SGS...")
        extractor = BCBExtractor(config["bcb"])
        raw_data["economia"] = extractor.extract_all()
        logger.info(f"BCB: {len(raw_data['economia'])} séries extraídas")
    except Exception as e:
        logger.error(f"Erro ao extrair BCB: {e}")
        raw_data["economia"] = {"error": str(e)}
    
    return raw_data


def run_transformation(raw_data: Dict[str, Any], config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Executa transformação e validação dos dados."""
    logger.info("=== INICIANDO TRANSFORMAÇÃO ===")
    transformed = {}
    
    cleaner = DataCleaner(config)
    enricher = DataEnricher(config)
    validator = DataValidator(config)
    
    # Clima
    if "clima" in raw_data and "error" not in raw_data["clima"]:
        logger.info("Transformando dados de clima...")
        daily_clean = cleaner.clean_clima_daily(raw_data["clima"].get("daily", []))
        hourly_clean = cleaner.clean_clima_hourly(raw_data["clima"].get("hourly", []))
        
        daily_enriched = enricher.enrich_clima(daily_clean)
        hourly_enriched = enricher.enrich_clima(hourly_clean)
        
        validation_daily = validator.validate_clima_daily(daily_enriched)
        validation_hourly = validator.validate_clima_hourly(hourly_enriched)
        
        transformed["clima"] = {
            "daily": daily_enriched,
            "hourly": hourly_enriched,
            "validation": {"daily": validation_daily, "hourly": validation_hourly}
        }
        logger.info(f"Clima diário: {len(daily_enriched)} registros válidos")
        logger.info(f"Clima horário: {len(hourly_enriched)} registros válidos")
    
    # Crypto
    if "crypto" in raw_data and "error" not in raw_data["crypto"]:
        logger.info("Transformando dados de crypto...")
        market_clean = cleaner.clean_crypto_market(raw_data["crypto"].get("market", []))
        history_clean = cleaner.clean_crypto_history(raw_data["crypto"].get("history", []))
        
        market_enriched = enricher.enrich_crypto(market_clean)
        history_enriched = enricher.enrich_crypto(history_clean)
        
        validation_market = validator.validate_crypto_market(market_enriched)
        validation_history = validator.validate_crypto_history(history_enriched)
        
        transformed["crypto"] = {
            "market": market_enriched,
            "history": history_enriched,
            "validation": {"market": validation_market, "history": validation_history}
        }
        logger.info(f"Crypto market: {len(market_enriched)} registros válidos")
        logger.info(f"Crypto history: {len(history_enriched)} registros válidos")
    
    # Economia
    if "economia" in raw_data and "error" not in raw_data["economia"]:
        logger.info("Transformando dados de economia...")
        econ_clean = cleaner.clean_economia(raw_data["economia"])
        econ_enriched = enricher.enrich_economia(econ_clean)
        validation_econ = validator.validate_economia(econ_enriched)
        
        transformed["economia"] = {
            "data": econ_enriched,
            "validation": validation_econ
        }
        logger.info(f"Economia: {len(econ_enriched)} registros válidos")
    
    return transformed


def run_load(transformed: Dict[str, Any], config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Executa carga dos dados transformados."""
    logger.info("=== INICIANDO CARGA ===")
    load_results = {}
    
    loader = ParquetLoader(config)
    powerbi_preparer = PowerBIPreparer(config)
    
    # Salva em Parquet particionado
    for domain, data in transformed.items():
        if domain == "clima":
            result_daily = loader.save_partitioned(
                data["daily"], "clima", "diario", partition_cols=["date", "state"]
            )
            result_hourly = loader.save_partitioned(
                data["hourly"], "clima", "horario", partition_cols=["date", "state"]
            )
            load_results["clima"] = {"daily": result_daily, "hourly": result_hourly}
            
        elif domain == "crypto":
            result_market = loader.save_partitioned(
                data["market"], "crypto", "diario", partition_cols=["date"]
            )
            result_history = loader.save_partitioned(
                data["history"], "crypto", "historico", partition_cols=["date", "coin_id"]
            )
            load_results["crypto"] = {"market": result_market, "history": result_history}
            
        elif domain == "economia":
            result = loader.save_partitioned(
                data["data"], "economia", "diario", partition_cols=["date", "series_code"]
            )
            load_results["economia"] = result
    
    # Prepara arquivos para Power BI
    powerbi_files = powerbi_preparer.prepare_all(transformed)
    load_results["powerbi"] = powerbi_files
    
    logger.info("Carga concluída")
    return load_results


def main():
    """Função principal do pipeline."""
    start_time = datetime.now()
    
    # Carrega configuração
    config = load_config()
    
    # Setup logging
    logger = setup_logging(config)
    logger.info(f"Pipeline iniciado em {start_time.isoformat()}")
    
    try:
        # 1. Extração
        raw_data = run_extraction(config, logger)
        
        # 2. Transformação
        transformed = run_transformation(raw_data, config, logger)
        
        # 3. Carga
        load_results = run_load(transformed, config, logger)
        
        # Sucesso
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"=== PIPELINE CONCLUÍDO COM SUCESSO EM {elapsed:.1f}s ===")
        
        # Summary
        logger.info("Resumo:")
        for domain, results in load_results.items():
            if domain != "powerbi":
                        if isinstance(results, dict):
                            for sub, res in results.items():
                                if isinstance(res, dict):
                                    logger.info(f"  {domain}.{sub}: {res.get('rows', 0)} linhas, "
                                               f"{res.get('files', 0)} arquivos")
                                else:
                                    logger.info(f"  {domain}.{sub}: {res}")
                        else:
                            logger.info(f"  {domain}: {results}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Erro fatal no pipeline: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())