"""
Enriquecimento de dados - adiciona campos derivados, cálculos, etc.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataEnricher:
    """Adiciona campos calculados e enriquece os dados."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    # ==========================================
    # CLIMA
    # ==========================================
    def enrich_clima(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enriquece dados de clima (diários ou horários)."""
        if not data:
            return []

        df = pd.DataFrame(data)

        # Amplitude térmica
        if "temperature_2m_max" in df.columns and "temperature_2m_min" in df.columns:
            df["temp_amplitude"] = df["temperature_2m_max"] - df["temperature_2m_min"]

        # Classificação de precipitação
        if "precipitation_sum" in df.columns:
            df["precip_category"] = pd.cut(
                df["precipitation_sum"],
                bins=[-0.1, 0, 2.5, 10, 50, float("inf")],
                labels=["Sem chuva", "Leve", "Moderada", "Forte", "Muito forte"]
            ).astype(str)

        # Classificação de temperatura
        if "temperature_2m_mean" in df.columns:
            df["temp_category"] = pd.cut(
                df["temperature_2m_mean"],
                bins=[-float("inf"), 10, 18, 25, 30, float("inf")],
                labels=["Frio", "Ameno", "Agradável", "Quente", "Muito quente"]
            ).astype(str)

        # Índice de conforto (simplificado)
        if "temperature_2m_mean" in df.columns and "relative_humidity_2m_mean" in df.columns:
            # Heat index simplificado
            t = df["temperature_2m_mean"]
            h = df["relative_humidity_2m_mean"]
            df["heat_index"] = t + 0.33 * h - 0.7 * df.get("windspeed_10m_max", 0) - 4.0

        # Estação do ano (hemisfério sul)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df["season"] = df["date"].dt.month.map(self._get_season_south)
            df["month"] = df["date"].dt.month
            df["day_of_year"] = df["date"].dt.dayofyear
            df["week_of_year"] = df["date"].dt.isocalendar().week
            df["is_weekend"] = df["date"].dt.weekday >= 5

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df["hour"] = df["datetime"].dt.hour
            df["is_daytime"] = (df["hour"] >= 6) & (df["hour"] < 18)

        return df.to_dict("records")

    def _get_season_south(self, month: int) -> str:
        """Retorna estação do ano para hemisfério sul."""
        if month in [12, 1, 2]:
            return "Verão"
        elif month in [3, 4, 5]:
            return "Outono"
        elif month in [6, 7, 8]:
            return "Inverno"
        else:
            return "Primavera"

    # ==========================================
    # CRYPTO
    # ==========================================
    def enrich_crypto(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enriquece dados de crypto."""
        if not data:
            return []

        df = pd.DataFrame(data)

        # Market cap dominance (se tiver total market cap)
        # Não temos total market cap aqui, mas podemos calcular rank
        if "market_cap_usd" in df.columns or "brl_market_cap" in df.columns:
            cap_col = "market_cap_usd" if "market_cap_usd" in df.columns else "brl_market_cap"
            # Preenche NaN com 0 antes do rank
            df["market_cap_rank"] = df[cap_col].fillna(0).rank(ascending=False, method="min").astype(int)

        # Volatilidade (se tiver high/low ou change %)
        if "price_change_percentage_24h" in df.columns:
            df["volatility_24h"] = df["price_change_percentage_24h"].abs()
            df["trend_24h"] = df["price_change_percentage_24h"].apply(
                lambda x: "Alta" if x > 2 else ("Baixa" if x < -2 else "Estável")
            )

        # Distance from ATH/ATL
        if "ath" in df.columns and "brl_current_price" in df.columns:
            df["pct_from_ath"] = ((df["brl_current_price"] - df["ath"]) / df["ath"] * 100).round(2)
        if "atl" in df.columns and "brl_current_price" in df.columns:
            df["pct_from_atl"] = ((df["brl_current_price"] - df["atl"]) / df["atl"] * 100).round(2)

        # Volume/Market Cap ratio (liquidez)
        if "brl_total_volume" in df.columns and "brl_market_cap" in df.columns:
            df["volume_market_cap_ratio"] = (df["brl_total_volume"] / df["brl_market_cap"]).round(4)

        # Data fields
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date

        return df.to_dict("records")

    # ==========================================
    # ECONOMIA
    # ==========================================
    def enrich_economia(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enriquece dados econômicos."""
        if not data:
            return []

        df = pd.DataFrame(data)

        # Garante ordenação por série e data
        df = df.sort_values(["series_code", "date"]).reset_index(drop=True)

        # Variação dia a dia
        df["change_1d"] = df.groupby("series_code")["value"].diff()
        df["pct_change_1d"] = df.groupby("series_code")["value"].pct_change() * 100

        # Variação 7 dias
        df["change_7d"] = df.groupby("series_code")["value"].diff(7)
        df["pct_change_7d"] = df.groupby("series_code")["value"].pct_change(7) * 100

        # Variação 30 dias
        df["change_30d"] = df.groupby("series_code")["value"].diff(30)
        df["pct_change_30d"] = df.groupby("series_code")["value"].pct_change(30) * 100

        # Média móvel 7 e 30 dias
        df["ma_7d"] = df.groupby("series_code")["value"].transform(lambda x: x.rolling(7, min_periods=1).mean())
        df["ma_30d"] = df.groupby("series_code")["value"].transform(lambda x: x.rolling(30, min_periods=1).mean())

        # Desvio padrão móvel (volatilidade)
        df["std_7d"] = df.groupby("series_code")["value"].transform(lambda x: x.rolling(7, min_periods=2).std())
        df["std_30d"] = df.groupby("series_code")["value"].transform(lambda x: x.rolling(30, min_periods=2).std())

        # Z-score (quantos desvios padrão da média)
        df["z_score_7d"] = (df["value"] - df["ma_7d"]) / df["std_7d"].replace(0, np.nan)
        df["z_score_30d"] = (df["value"] - df["ma_30d"]) / df["std_30d"].replace(0, np.nan)

        # Sinal de alerta (fora de 2 desvios padrão)
        df["alert"] = df["z_score_30d"].apply(
            lambda x: "Alerta" if pd.notna(x) and abs(x) > 2 else "Normal"
        )

        # Data fields
        df["date"] = pd.to_datetime(df["date"]).dt.date

        return df.to_dict("records")