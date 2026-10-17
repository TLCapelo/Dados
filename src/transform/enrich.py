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
        """
        Enriquece os indicadores economicos. Cada serie usa a formula do seu "kind":
          price/stock        -> variacao %, media e z-score de 30 dias (alerta de anomalia)
          index              -> variacao % (mensal e em 12 meses)
          rate/level_pct     -> variacao em pontos percentuais (p.p.)
          monthly_rate       -> variacao em p.p. e acumulado de 12 meses (composto)
        """
        if not data:
            return []

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["series_code", "date"]).reset_index(drop=True)

        partes = [self._enrich_serie(g.copy()) for _, g in df.groupby("series_code", sort=False)]
        df = pd.concat(partes, ignore_index=True)
        df["date"] = df["date"].dt.date
        return df.to_dict("records")

    @staticmethod
    def _enrich_serie(g: pd.DataFrame) -> pd.DataFrame:
        kind = g["kind"].iloc[0] if "kind" in g.columns else "price"
        daily = (g["frequency"].iloc[0] if "frequency" in g.columns else "daily") == "daily"
        pct = kind in ("price", "stock", "index")
        s = g.set_index("date")["value"].astype(float)

        def anterior(offset) -> pd.Series:
            """Valor da serie na data (ou antes) de `data - offset`."""
            return pd.Series(s.asof(s.index - offset).values, index=s.index)

        def variacao(ref: pd.Series) -> pd.Series:
            return (s / ref - 1) * 100 if pct else s - ref

        um_mes = pd.Timedelta(days=30) if daily else pd.DateOffset(months=1)
        v30 = variacao(anterior(um_mes))
        v12m = variacao(anterior(pd.DateOffset(months=12)))

        g["change_1d"] = s.diff().values
        g["delta_30d"] = v30.values
        g["delta_12m"] = v12m.values
        g["delta_unit"] = "%" if pct else "p.p."

        if kind == "monthly_rate":
            fator = 1 + s / 100
            acc = fator.rolling(12, min_periods=12).apply(np.prod, raw=True) - 1
            g["acc_12m"] = (acc * 100).values
        else:
            g["acc_12m"] = np.nan

        if kind in ("price", "stock") and daily:
            media = s.rolling("30D", min_periods=5).mean()
            desvio = s.rolling("30D", min_periods=5).std()
            z = (s - media) / desvio.replace(0, np.nan)
            g["ma_30d"] = media.values
            g["z_score_30d"] = z.values
            g["alert"] = np.where(z.abs() > 2, "Alerta", "Normal")
        else:
            g["ma_30d"] = np.nan
            g["z_score_30d"] = np.nan
            g["alert"] = ""

        limite = 0.05 if pct else 0.01
        g["trend"] = np.select(
            [v30 > limite, v30 < -limite], ["Alta", "Queda"], default="Estavel"
        )
        g.loc[v30.isna().values, "trend"] = ""
        return g.reset_index(drop=True)
