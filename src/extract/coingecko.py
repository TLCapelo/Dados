"""
Extrator para CoinGecko API (Dados de Criptomoedas).
"""
import requests
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import time
import logging

logger = logging.getLogger(__name__)


class CoinGeckoExtractor:
    """Extrator de dados de criptomoedas da API CoinGecko."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "https://api.coingecko.com/api/v3")
        self.coins = config.get("coins", [])
        self.vs_currencies = config.get("vs_currencies", ["brl", "usd"])
        self.market_data_fields = config.get("market_data", [])
        self.price_history_days = config.get("price_history_days", 30)
        # Rate limit mais conservador: 10 req/min (free tier sem API key)
        # Com API key pode subir para 50-100 req/min
        self.rate_limit = config.get("rate_limit_per_minute", 10)
        self._last_request_time = 0
        self._min_interval = 60.0 / self.rate_limit  # segundos entre requests

    def _rate_limit_wait(self):
        """Aplica rate limiting simples."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _fetch_market_data(self) -> List[Dict[str, Any]]:
        """Busca dados de mercado atuais para todas as moedas configuradas."""
        self._rate_limit_wait()

        coin_ids = [c["id"] for c in self.coins]
        all_results = []

        # CoinGecko não aceita múltiplas vs_currency em uma requisição
        # Fazemos uma requisição por moeda fiat
        for vs_currency in self.vs_currencies:
            self._rate_limit_wait()
            params = {
                "ids": ",".join(coin_ids),
                "vs_currency": vs_currency,  # singular, uma por vez
                "order": "market_cap_desc",
                "per_page": len(coin_ids),
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,7d,30d"
            }

            url = f"{self.base_url}/coins/markets"
            headers = {"Accept": "application/json", "User-Agent": "data-pipeline-estudo/1.0"}
            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                logger.debug(f"CoinGecko market response ({vs_currency}): {response.status_code}")
                response.raise_for_status()
                data = response.json()
                # Debug: log first item structure
                if data:
                    logger.debug(f"CoinGecko sample keys: {list(data[0].keys())}")
                    logger.debug(f"CoinGecko current_price type: {type(data[0].get('current_price'))}")
                # Adiciona a moeda fiat em cada registro
                for coin in data:
                    coin["_vs_currency"] = vs_currency
                all_results.extend(data)
            except requests.exceptions.HTTPError as e:
                logger.error(f"CoinGecko HTTP Error ({vs_currency}): {e.response.status_code} - {e.response.text[:200]}")
                raise
            except Exception as e:
                logger.error(f"CoinGecko Error ({vs_currency}): {type(e).__name__}: {e}")
                raise

        return all_results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _fetch_coin_history(self, coin_id: str, days: int = 30) -> Dict[str, Any]:
        """Busca histórico de preços para uma moeda."""
        self._rate_limit_wait()

        params = {
            "vs_currency": "usd",  # Histórico em USD
            "days": days,
            "interval": "daily" if days > 1 else "hourly"
        }

        url = f"{self.base_url}/coins/{coin_id}/market_chart"
        headers = {"Accept": "application/json", "User-Agent": "data-pipeline-estudo/1.0"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            logger.debug(f"CoinGecko history response: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"CoinGecko HTTP Error: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"CoinGecko Error: {type(e).__name__}: {e}")
            raise

    def _parse_market_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converte dados de mercado para formato tabular."""
        records = []
        extracted_at = datetime.now().isoformat()
        date_today = datetime.now().date().isoformat()

        # Mapeia id para metadados da moeda
        coin_meta = {c["id"]: c for c in self.coins}

        for coin in raw_data:
            coin_id = coin["id"]
            meta = coin_meta.get(coin_id, {})
            vs_currency = coin.get("_vs_currency", "usd")

            record = {
                "coin_id": coin_id,
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", meta.get("name", "")),
                "date": date_today,
                "extracted_at": extracted_at,
                "vs_currency": vs_currency,
            }

            # Preços e market data para a moeda fiat desta requisição
            # A API retorna valores diretos (float) quando vs_currency é único
            prefix = f"{vs_currency}_"
            current_price = coin.get("current_price")
            market_cap = coin.get("market_cap")
            total_volume = coin.get("total_volume")

            # Se for dict (múltiplas moedas), pega o valor da moeda atual
            if isinstance(current_price, dict):
                current_price = current_price.get(vs_currency)
            if isinstance(market_cap, dict):
                market_cap = market_cap.get(vs_currency)
            if isinstance(total_volume, dict):
                total_volume = total_volume.get(vs_currency)

            record[f"{prefix}current_price"] = current_price
            record[f"{prefix}market_cap"] = market_cap
            record[f"{prefix}total_volume"] = total_volume

            # Campos adicionais
            record["price_change_24h"] = coin.get("price_change_24h")
            record["price_change_percentage_24h"] = coin.get("price_change_percentage_24h")
            
            # price_change_percentage_7d_in_currency pode ser float (uma moeda) ou dict (múltiplas)
            pct_7d = coin.get("price_change_percentage_7d_in_currency")
            if isinstance(pct_7d, dict):
                record["price_change_percentage_7d"] = pct_7d.get("usd")
            else:
                record["price_change_percentage_7d"] = pct_7d
            
            # price_change_percentage_30d_in_currency pode ser float ou dict
            pct_30d = coin.get("price_change_percentage_30d_in_currency")
            if isinstance(pct_30d, dict):
                record["price_change_percentage_30d"] = pct_30d.get("usd")
            else:
                record["price_change_percentage_30d"] = pct_30d
            
            record["circulating_supply"] = coin.get("circulating_supply")
            record["total_supply"] = coin.get("total_supply")
            record["max_supply"] = coin.get("max_supply")
            
            # ath/atl podem ser float (uma moeda) ou dict (múltiplas)
            ath = coin.get("ath")
            if isinstance(ath, dict):
                record["ath"] = ath.get("usd")
            else:
                record["ath"] = ath
            
            ath_pct = coin.get("ath_change_percentage")
            if isinstance(ath_pct, dict):
                record["ath_change_percentage"] = ath_pct.get("usd")
            else:
                record["ath_change_percentage"] = ath_pct
            
            atl = coin.get("atl")
            if isinstance(atl, dict):
                record["atl"] = atl.get("usd")
            else:
                record["atl"] = atl
            
            atl_pct = coin.get("atl_change_percentage")
            if isinstance(atl_pct, dict):
                record["atl_change_percentage"] = atl_pct.get("usd")
            else:
                record["atl_change_percentage"] = atl_pct
            
            record["last_updated"] = coin.get("last_updated")

            records.append(record)

        return records

    def _parse_history_data(self, coin_id: str, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converte histórico de preços para formato tabular."""
        records = []

        prices = raw_data.get("prices", [])
        market_caps = raw_data.get("market_caps", [])
        volumes = raw_data.get("total_volumes", [])

        # Cria dicionários para lookup rápido
        mc_dict = {int(ts): val for ts, val in market_caps}
        vol_dict = {int(ts): val for ts, val in volumes}

        for ts, price in prices:
            dt = datetime.fromtimestamp(ts / 1000)
            date_str = dt.date().isoformat()

            record = {
                "coin_id": coin_id,
                "date": date_str,
                "datetime": dt.isoformat(),
                "price_usd": price,
                "market_cap_usd": mc_dict.get(int(ts)),
                "volume_usd": vol_dict.get(int(ts)),
            }
            records.append(record)

        return records

    def extract_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extrai dados de mercado e histórico para todas as moedas."""
        # 1. Dados de mercado atuais
        logger.info("Buscando dados de mercado atuais...")
        market_raw = self._fetch_market_data()
        market_parsed = self._parse_market_data(market_raw)

        # 2. Histórico de preços para cada moeda
        logger.info(f"Buscando histórico de {self.price_history_days} dias para {len(self.coins)} moedas...")
        all_history = []

        for coin in self.coins:
            try:
                logger.info(f"  Histórico: {coin['id']}...")
                history_raw = self._fetch_coin_history(coin["id"], self.price_history_days)
                history_parsed = self._parse_history_data(coin["id"], history_raw)
                all_history.extend(history_parsed)
            except Exception as e:
                logger.error(f"Erro ao buscar histórico de {coin['id']}: {e}")
                continue

        return {
            "market": market_parsed,
            "history": all_history,
            "extracted_at": datetime.now().isoformat(),
            "source": "coingecko"
        }