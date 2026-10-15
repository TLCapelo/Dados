"""
Testes básicos do pipeline.
"""
import sys
from pathlib import Path
import pytest

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from src.extract.open_meteo import OpenMeteoExtractor
from src.extract.coingecko import CoinGeckoExtractor
from src.extract.bcb import BCBExtractor
from src.transform.clean import DataCleaner
from src.transform.enrich import DataEnricher
from src.transform.validate import DataValidator
from src.load.to_parquet import ParquetLoader


class TestConfig:
    """Testes de configuração."""
    
    def test_load_config(self):
        config = load_config()
        assert config is not None
        assert "open_meteo" in config
        assert "coingecko" in config
        assert "bcb" in config
        assert "pipeline" in config
    
    def test_open_meteo_cities(self):
        config = load_config()
        cities = config["open_meteo"]["cities"]
        assert len(cities) == 10
        for city in cities:
            assert "name" in city
            assert "state" in city
            assert "latitude" in city
            assert "longitude" in city


class TestExtractors:
    """Testes dos extratores (mockados para não chamar APIs reais)."""
    
    def test_open_meteo_extractor_init(self):
        config = load_config()
        extractor = OpenMeteoExtractor(config["open_meteo"])
        assert extractor.base_url == "https://api.open-meteo.com/v1/forecast"
        assert len(extractor.cities) == 10
    
    def test_coingecko_extractor_init(self):
        config = load_config()
        extractor = CoinGeckoExtractor(config["coingecko"])
        assert extractor.base_url == "https://api.coingecko.com/api/v3"
        assert len(extractor.coins) == 10
    
    def test_bcb_extractor_init(self):
        config = load_config()
        extractor = BCBExtractor(config["bcb"])
        assert extractor.base_url == "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
        assert len(extractor.series) == 15


class TestTransformers:
    """Testes de transformação."""
    
    def test_clean_clima_daily(self):
        config = load_config()
        cleaner = DataCleaner(config)
        
        # Dados de teste
        raw = [{
            "city": "São Paulo",
            "state": "SP",
            "date": "2024-01-15",
            "temperature_2m_max": 30.5,
            "temperature_2m_min": 20.1,
            "precipitation_sum": 5.2,
        }]
        
        cleaned = cleaner.clean_clima_daily(raw)
        assert len(cleaned) == 1
        assert cleaned[0]["city"] == "São Paulo"
        assert cleaned[0]["date"].isoformat() == "2024-01-15"
    
    def test_clean_crypto_market(self):
        config = load_config()
        cleaner = DataCleaner(config)
        
        raw = [{
            "coin_id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "date": "2024-01-15",
            "extracted_at": "2024-01-15T12:00:00Z",
            "vs_currency": "brl",
            "brl_current_price": 200000.0,
            "brl_market_cap": 3900000000000.0,
        }]
        
        cleaned = cleaner.clean_crypto_market(raw)
        assert len(cleaned) == 1
        assert cleaned[0]["coin_id"] == "bitcoin"
    
    def test_enrich_clima(self):
        config = load_config()
        enricher = DataEnricher(config)
        
        raw = [{
            "city": "São Paulo",
            "state": "SP",
            "date": "2024-01-15",
            "temperature_2m_max": 30.0,
            "temperature_2m_min": 20.0,
            "precipitation_sum": 0.0,
            "relative_humidity_2m_mean": 60.0,
        }]
        
        enriched = enricher.enrich_clima(raw)
        assert len(enriched) == 1
        assert "temp_amplitude" in enriched[0]
        assert enriched[0]["temp_amplitude"] == 10.0
        assert "precip_category" in enriched[0]
        assert "season" in enriched[0]


class TestValidators:
    """Testes de validação."""
    
    def test_validate_clima_daily_success(self):
        config = load_config()
        validator = DataValidator(config)
        
        # Dados válidos
        data = [{
            "city": "São Paulo",
            "state": "SP",
            "date": "2024-01-15",
            "temperature_2m_mean": 25.0,
            "precipitation_sum": 0.0,
            "relative_humidity_2m_mean": 60.0,
            "uv_index_max": 8.0,
        }]
        
        result = validator.validate_clima_daily(data)
        assert result["success"] is True
        assert result["statistics"]["successful_expectations"] > 0
    
    def test_validate_clima_daily_failure(self):
        config = load_config()
        validator = DataValidator(config)
        
        # Dados com temperatura inválida
        data = [{
            "city": "São Paulo",
            "state": "SP",
            "date": "2024-01-15",
            "temperature_2m_mean": 100.0,  # Inválido
            "precipitation_sum": 0.0,
            "relative_humidity_2m_mean": 60.0,
            "uv_index_max": 8.0,
        }]
        
        result = validator.validate_clima_daily(data)
        assert result["success"] is False


class TestLoader:
    """Testes de carga."""
    
    def test_parquet_loader_init(self):
        config = load_config()
        loader = ParquetLoader(config)
        assert loader.serving_path.name == "serving"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])