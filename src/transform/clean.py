"""
Limpeza e normalização de dados.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataCleaner:
    """Limpa e normaliza dados brutos de todas as fontes."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    # ==========================================
    # CLIMA
    # ==========================================
    def clean_clima_daily(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limpa dados diários de clima."""
        if not raw_data:
            return []
        
        df = pd.DataFrame(raw_data)
        
        # Garante tipos corretos
        df["date"] = pd.to_datetime(df["date"]).dt.date
        
        # Colunas numéricas - converte para float, mantém NaN
        numeric_cols = [c for c in df.columns if c not in ["city", "state", "date", "latitude", "longitude"]]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Remove duplicatas (mesma cidade + data)
        df = df.drop_duplicates(subset=["city", "state", "date"], keep="last")
        
        # Ordena
        df = df.sort_values(["state", "city", "date"]).reset_index(drop=True)
        
        return df.to_dict("records")
    
    def clean_clima_hourly(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limpa dados horários de clima."""
        if not raw_data:
            return []
        
        df = pd.DataFrame(raw_data)
        
        # Garante tipos corretos
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date
        
        # Colunas numéricas
        numeric_cols = [c for c in df.columns if c not in ["city", "state", "datetime", "date", "latitude", "longitude"]]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Remove duplicatas
        df = df.drop_duplicates(subset=["city", "state", "datetime"], keep="last")
        
        # Ordena
        df = df.sort_values(["state", "city", "datetime"]).reset_index(drop=True)
        
        return df.to_dict("records")
    
    # ==========================================
    # CRYPTO
    # ==========================================
    def clean_crypto_market(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limpa dados de mercado de crypto."""
        if not raw_data:
            return []
        
        df = pd.DataFrame(raw_data)
        
        # Garante tipos
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["extracted_at"] = pd.to_datetime(df["extracted_at"])
        if "last_updated" in df.columns:
            df["last_updated"] = pd.to_datetime(df["last_updated"], errors="coerce")
        
        # Colunas numéricas
            numeric_cols = [c for c in df.columns if c not in ["coin_id", "symbol", "name", "date", "extracted_at", "last_updated", "vs_currency"]]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
            # Substitui inf/-inf por NaN
            df = df.replace([np.inf, -np.inf], np.nan)
        
            # Remove duplicatas
            df = df.drop_duplicates(subset=["coin_id", "date", "vs_currency"], keep="last")
        
            # Ordena
            df = df.sort_values(["coin_id", "date", "vs_currency"]).reset_index(drop=True)
        
            return df.to_dict("records")
    
    def clean_crypto_history(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limpa dados históricos de crypto."""
        if not raw_data:
            return []
        
        df = pd.DataFrame(raw_data)
        
        # Garante tipos
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["datetime"] = pd.to_datetime(df["datetime"])
        
        # Colunas numéricas
        numeric_cols = [c for c in df.columns if c not in ["coin_id", "date", "datetime"]]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Remove duplicatas
        df = df.drop_duplicates(subset=["coin_id", "date"], keep="last")
        
        # Ordena
        df = df.sort_values(["coin_id", "date"]).reset_index(drop=True)
        
        return df.to_dict("records")
    
    # ==========================================
    # ECONOMIA
    # ==========================================
    def clean_economia(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limpa dados econômicos do BCB."""
        if not raw_data:
            return []
        
        df = pd.DataFrame(raw_data)
        
        # Garante tipos
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series_code"] = df["series_code"].astype(int)
        
        # Remove duplicatas
        df = df.drop_duplicates(subset=["series_code", "date"], keep="last")
        
        # Ordena
        df = df.sort_values(["series_code", "date"]).reset_index(drop=True)
        
        return df.to_dict("records")