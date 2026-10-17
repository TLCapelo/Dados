"""
Extrator para BCB/SGS API (Dados Econômicos Brasileiros).
"""
import requests
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import time
import logging

logger = logging.getLogger(__name__)


class BCBExtractor:
    """Extrator de dados econômicos do BCB/SGS."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "https://api.bcb.gov.br/dados/serie/bcdata.sgs")
        self.series = config.get("series", [])
        self.date_format = config.get("date_format", "%d/%m/%Y")
        self.lookback_days = config.get("lookback_days", 60)

    def _build_url(self, series_code: int, lookback_days: int = None) -> str:
        """Constrói URL para uma série específica."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days or self.lookback_days)

        start_str = start_date.strftime(self.date_format)
        end_str = end_date.strftime(self.date_format)

        # BCB SGS API - formato correto (novo endpoint)
        # https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/12/2024
        return f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados?formato=json&dataInicial={start_str}&dataFinal={end_str}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=30)
    )
    def _fetch_series(self, series_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Busca dados de uma série específica."""
        series_code = series_config["code"]
        url = self._build_url(series_code, series_config.get("lookback_days"))

        headers = {"Accept": "application/json", "User-Agent": "data-pipeline-estudo/1.0"}
        # Timeout maior para BCB que pode ser lento
        try:
            response = requests.get(url, headers=headers, timeout=60)
            logger.debug(f"BCB series {series_code} response: {response.status_code}")
            response.raise_for_status()
            data = response.json()

            # Adiciona metadados
            for record in data:
                record["series_code"] = series_code
                record["series_name"] = series_config["name"]
                record["series_description"] = series_config["description"]
                record["unit"] = series_config["unit"]
                record["kind"] = series_config.get("kind", "price")
                record["frequency"] = series_config.get("frequency", "daily")
                record["decimals"] = series_config.get("decimals", 2)

            return data
        except requests.exceptions.HTTPError as e:
            logger.error(f"BCB HTTP Error (series {series_code}): {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"BCB Error (series {series_code}): {type(e).__name__}: {e}")
            raise

    def _parse_date(self, date_str: str) -> str:
        """Converte data do formato DD/MM/YYYY para YYYY-MM-DD."""
        try:
            dt = datetime.strptime(date_str, self.date_format)
            return dt.date().isoformat()
        except Exception:
            return date_str

    def extract_all(self) -> List[Dict[str, Any]]:
        """Extrai dados de todas as séries configuradas."""
        all_records = []

        for i, series_config in enumerate(self.series):
            try:
                logger.info(f"Buscando série {series_config['code']} - {series_config['name']}...")
                raw_data = self._fetch_series(series_config)

                # Normaliza datas
                for record in raw_data:
                    if "data" in record:
                        record["date"] = self._parse_date(record["data"])
                        del record["data"]
                    if "valor" in record:
                        record["value"] = record["valor"]
                        del record["valor"]

                # Algumas series (ex.: Meta Selic) trazem datas futuras agendadas.
                hoje = datetime.now().date().isoformat()
                raw_data = [r for r in raw_data if r.get("date", "") <= hoje]

                all_records.extend(raw_data)
                logger.info(f"  Série {series_config['name']}: {len(raw_data)} registros")

                # Pequeno delay entre séries para não sobrecarregar a API
                if i < len(self.series) - 1:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Erro ao buscar série {series_config['code']}: {e}")
                continue

        return all_records