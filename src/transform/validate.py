"""
Validação de qualidade de dados com Great Expectations.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """Valida qualidade dos dados transformados."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_config = config.get("pipeline", {}).get("validation", {})
        self.enabled = self.validation_config.get("enabled", True)
        self.fail_on_error = self.validation_config.get("fail_on_error", False)
    
    def _check_enabled(self) -> bool:
        return self.enabled
    
    def _validate_df(self, df: pd.DataFrame, expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Executa validações em um DataFrame."""
        if not self._check_enabled() or df.empty:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        results = []
        success_count = 0
        
        for exp in expectations:
            exp_type = exp.get("type")
            column = exp.get("column")
            kwargs = exp.get("kwargs", {})
            
            try:
                if exp_type == "not_null":
                    null_count = df[column].isnull().sum()
                    total = len(df)
                    success = null_count == 0
                    results.append({
                        "expectation": f"not_null({column})",
                        "success": success,
                        "observed_value": f"{null_count}/{total} nulos",
                        "details": {"null_count": int(null_count), "total": int(total)}
                    })
                
                elif exp_type == "unique":
                    dup_count = df[column].duplicated().sum()
                    success = dup_count == 0
                    results.append({
                        "expectation": f"unique({column})",
                        "success": success,
                        "observed_value": f"{dup_count} duplicatas",
                        "details": {"duplicate_count": int(dup_count)}
                    })
                
                elif exp_type == "between":
                    min_val = kwargs.get("min_value")
                    max_val = kwargs.get("max_value")
                    out_of_bounds = ((df[column] < min_val) | (df[column] > max_val)).sum()
                    success = out_of_bounds == 0
                    results.append({
                        "expectation": f"between({column}, {min_val}, {max_val})",
                        "success": success,
                        "observed_value": f"{out_of_bounds} fora do intervalo",
                        "details": {"out_of_bounds": int(out_of_bounds), "min": min_val, "max": max_val}
                    })
                
                elif exp_type == "mean_between":
                    mean_val = df[column].mean()
                    min_val = kwargs.get("min_value")
                    max_val = kwargs.get("max_value")
                    success = min_val <= mean_val <= max_val
                    results.append({
                        "expectation": f"mean_between({column}, {min_val}, {max_val})",
                        "success": success,
                        "observed_value": f"média = {mean_val:.2f}",
                        "details": {"mean": float(mean_val), "min": min_val, "max": max_val}
                    })
                
                elif exp_type == "row_count":
                    min_rows = kwargs.get("min_value", 0)
                    max_rows = kwargs.get("max_value", float("inf"))
                    row_count = len(df)
                    success = min_rows <= row_count <= max_rows
                    results.append({
                        "expectation": f"row_count({min_rows}, {max_rows})",
                        "success": success,
                        "observed_value": f"{row_count} linhas",
                        "details": {"row_count": int(row_count)}
                    })
                
                if success:
                    success_count += 1
                    
            except Exception as e:
                results.append({
                    "expectation": f"{exp_type}({column})",
                    "success": False,
                    "observed_value": f"Erro: {e}",
                    "details": {"error": str(e)}
                })
        
        total = len(results)
        return {
            "success": all(r["success"] for r in results),
            "results": results,
            "statistics": {
                "evaluated_expectations": total,
                "successful_expectations": success_count,
                "unsuccessful_expectations": total - success_count
            }
        }
    
    # ==========================================
    # CLIMA DIÁRIO
    # ==========================================
    def validate_clima_daily(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida dados diários de clima."""
        if not data:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        df = pd.DataFrame(data)
        
        expectations = [
            {"type": "not_null", "column": "city"},
            {"type": "not_null", "column": "state"},
            {"type": "not_null", "column": "date"},
            {"type": "unique", "column": "city"},  # Não exatamente único, mas combinado com date
            {"type": "row_count", "kwargs": {"min_value": 1}},
            {"type": "between", "column": "temperature_2m_mean", "kwargs": {"min_value": -50, "max_value": 60}},
            {"type": "between", "column": "precipitation_sum", "kwargs": {"min_value": 0, "max_value": 1000}},
            {"type": "between", "column": "relative_humidity_2m_mean", "kwargs": {"min_value": 0, "max_value": 100}},
            {"type": "between", "column": "uv_index_max", "kwargs": {"min_value": 0, "max_value": 16}},
        ]
        
        # Verifica unicidade composta (city + state + date)
        if not df.empty:
            dup_composite = df.duplicated(subset=["city", "state", "date"]).sum()
            expectations.insert(3, {
                "type": "custom",
                "column": "city_state_date",
                "kwargs": {"max_duplicates": 0}
            })
        
        return self._validate_df(df, expectations)
    
    # ==========================================
    # CLIMA HORÁRIO
    # ==========================================
    def validate_clima_hourly(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida dados horários de clima."""
        if not data:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        df = pd.DataFrame(data)
        
        expectations = [
            {"type": "not_null", "column": "city"},
            {"type": "not_null", "column": "state"},
            {"type": "not_null", "column": "datetime"},
            {"type": "row_count", "kwargs": {"min_value": 1}},
            {"type": "between", "column": "temperature_2m", "kwargs": {"min_value": -50, "max_value": 60}},
            {"type": "between", "column": "relative_humidity_2m", "kwargs": {"min_value": 0, "max_value": 100}},
            {"type": "between", "column": "precipitation", "kwargs": {"min_value": 0, "max_value": 500}},
        ]
        
        return self._validate_df(df, expectations)
    
    # ==========================================
    # CRYPTO MARKET
    # ==========================================
    def validate_crypto_market(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida dados de mercado de crypto."""
        if not data:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        df = pd.DataFrame(data)
        
        expectations = [
            {"type": "not_null", "column": "coin_id"},
            {"type": "not_null", "column": "symbol"},
            {"type": "not_null", "column": "date"},
            {"type": "row_count", "kwargs": {"min_value": 1}},
            {"type": "between", "column": "brl_current_price", "kwargs": {"min_value": 0, "max_value": 10000000}},
            {"type": "between", "column": "brl_market_cap", "kwargs": {"min_value": 0, "max_value": 1e15}},
            {"type": "between", "column": "price_change_percentage_24h", "kwargs": {"min_value": -100, "max_value": 10000}},
        ]
        
        return self._validate_df(df, expectations)
    
    # ==========================================
    # CRYPTO HISTORY
    # ==========================================
    def validate_crypto_history(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida dados históricos de crypto."""
        if not data:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        df = pd.DataFrame(data)
        
        expectations = [
            {"type": "not_null", "column": "coin_id"},
            {"type": "not_null", "column": "date"},
            {"type": "not_null", "column": "price_usd"},
            {"type": "row_count", "kwargs": {"min_value": 1}},
            {"type": "between", "column": "price_usd", "kwargs": {"min_value": 0, "max_value": 1000000}},
        ]
        
        return self._validate_df(df, expectations)
    
    # ==========================================
    # ECONOMIA
    # ==========================================
    def validate_economia(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida dados econômicos."""
        if not data:
            return {"success": True, "results": [], "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "unsuccessful_expectations": 0}}
        
        df = pd.DataFrame(data)
        
        expectations = [
            {"type": "not_null", "column": "series_code"},
            {"type": "not_null", "column": "date"},
            {"type": "not_null", "column": "value"},
            {"type": "row_count", "kwargs": {"min_value": 1}},
        ]
        
        # Validações específicas por série
        series_ranges = {
            11: {"min": 0, "max": 100},      # Selic
            432: {"min": 0, "max": 1},       # Selic diária
            1: {"min": 0.5, "max": 10},      # Dólar
            433: {"min": -10, "max": 50},    # IPCA
        }
        
        for series_code, ranges in series_ranges.items():
            series_data = df[df["series_code"] == series_code]
            if not series_data.empty:
                expectations.append({
                    "type": "between",
                    "column": "value",
                    "kwargs": {"min_value": ranges["min"], "max_value": ranges["max"]}
                })
        
        return self._validate_df(df, expectations)