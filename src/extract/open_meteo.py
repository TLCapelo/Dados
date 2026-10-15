"""
Extrator para Open-Meteo API (Dados Climáticos).
"""
import requests
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)


class OpenMeteoExtractor:
    """Extrator de dados climáticos da API Open-Meteo."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "https://api.open-meteo.com/v1/forecast")
        self.cities = config.get("cities", [])
        self.daily_vars = config.get("daily_variables", [])
        self.hourly_vars = config.get("hourly_variables", [])
        self.timezone = config.get("timezone", "America/Sao_Paulo")
        self.forecast_days = config.get("forecast_days", 2)
        self.past_days = config.get("past_days", 1)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _fetch_city_data(self, city: Dict[str, Any]) -> Dict[str, Any]:
        """Busca dados para uma cidade específica."""
        params = {
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "daily": ",".join(self.daily_vars),
            "hourly": ",".join(self.hourly_vars),
            "timezone": self.timezone,
            "forecast_days": self.forecast_days,
            "past_days": self.past_days,
        }
        
        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Adiciona metadados da cidade
        data["city_meta"] = {
            "city": city["name"],
            "state": city["state"],
            "latitude": city["latitude"],
            "longitude": city["longitude"]
        }
        
        return data
    
    def _parse_daily(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converte dados diários para lista de dicionários."""
        daily = raw_data.get("daily", {})
        meta = raw_data.get("city_meta", {})
        
        if not daily or "time" not in daily:
            return []
        
        records = []
        n_days = len(daily["time"])
        
        for i in range(n_days):
            record = {
                "city": meta.get("city"),
                "state": meta.get("state"),
                "latitude": meta.get("latitude"),
                "longitude": meta.get("longitude"),
                "date": daily["time"][i],
            }
            
            # Adiciona todas as variáveis diárias
            for var in self.daily_vars:
                if var in daily and i < len(daily[var]):
                    record[var] = daily[var][i]
                else:
                    record[var] = None
            
            records.append(record)
        
        return records
    
    def _parse_hourly(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converte dados horários para lista de dicionários."""
        hourly = raw_data.get("hourly", {})
        meta = raw_data.get("city_meta", {})
        
        if not hourly or "time" not in hourly:
            return []
        
        records = []
        n_hours = len(hourly["time"])
        
        for i in range(n_hours):
            record = {
                "city": meta.get("city"),
                "state": meta.get("state"),
                "latitude": meta.get("latitude"),
                "longitude": meta.get("longitude"),
                "datetime": hourly["time"][i],
            }
            
            # Adiciona todas as variáveis horárias
            for var in self.hourly_vars:
                if var in hourly and i < len(hourly[var]):
                    record[var] = hourly[var][i]
                else:
                    record[var] = None
            
            records.append(record)
        
        return records
    
    def extract_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extrai dados de todas as cidades configuradas."""
        all_daily = []
        all_hourly = []
        
        for city in self.cities:
            try:
                logger.info(f"Buscando dados para {city['name']} ({city['state']})...")
                raw = self._fetch_city_data(city)
                
                daily = self._parse_daily(raw)
                hourly = self._parse_hourly(raw)
                
                all_daily.extend(daily)
                all_hourly.extend(hourly)
                
                logger.info(f"  {city['name']}: {len(daily)} dias, {len(hourly)} horas")
                
            except Exception as e:
                logger.error(f"Erro ao buscar {city['name']}: {e}")
                continue
        
        return {
            "daily": all_daily,
            "hourly": all_hourly,
            "extracted_at": datetime.now().isoformat(),
            "source": "open_meteo"
        }