"""
Preparador de arquivos para Power BI.
Gera arquivos CSV consolidados e documentação de conexão.
"""
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class PowerBIPreparer:
    """Prepara dados e documentação para consumo no Power BI."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        pipeline_config = config.get("pipeline", {})
        self.serving_path = Path(pipeline_config.get("paths", {}).get("serving", "data/serving"))
        self.powerbi_config = config.get("powerbi", {})
        self.github_pages_url = self.powerbi_config.get("github_pages_base_url", "")
    
    def prepare_all(self, transformed: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara todos os arquivos para Power BI."""
        results = {}
        
        # 1. Gera CSVs consolidados (mais fáceis para Power BI Web connector)
        results["csv"] = self._generate_consolidated_csvs(transformed)
        
        # 2. Gera arquivo de metadados/tabelas
        results["metadata"] = self._generate_metadata(transformed)
        
        # 3. Gera instruções de conexão
        results["connection_guide"] = self._generate_connection_guide()
        
        # 4. Gera medidas DAX sugeridas
        results["dax_measures"] = self._generate_dax_measures()
        
        return results
    
    def _generate_consolidated_csvs(self, transformed: Dict[str, Any]) -> Dict[str, str]:
        """Gera CSVs consolidados por domínio para facilitar no Power BI."""
        csv_files = {}
        
        for domain, data in transformed.items():
            if domain == "clima":
                # Consolida diário
                if "daily" in data and data["daily"]:
                    df = pd.DataFrame(data["daily"])
                    path = self.serving_path / "powerbi" / "clima_diario.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(path, index=False, encoding="utf-8")
                    csv_files["clima_diario"] = str(path)
                
                # Consolida horário (apenas últimas 48h para não ficar grande)
                if "hourly" in data and data["hourly"]:
                    df = pd.DataFrame(data["hourly"])
                    # Filtra últimas 48h
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    cutoff = df["datetime"].max() - pd.Timedelta(hours=48)
                    df = df[df["datetime"] >= cutoff]
                    path = self.serving_path / "powerbi" / "clima_horario_recente.csv"
                    df.to_csv(path, index=False, encoding="utf-8")
                    csv_files["clima_horario_recente"] = str(path)
            
            elif domain == "crypto":
                if "market" in data and data["market"]:
                    df = pd.DataFrame(data["market"])
                    path = self.serving_path / "powerbi" / "crypto_market.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(path, index=False, encoding="utf-8")
                    csv_files["crypto_market"] = str(path)
                
                if "history" in data and data["history"]:
                    df = pd.DataFrame(data["history"])
                    path = self.serving_path / "powerbi" / "crypto_historico.csv"
                    df.to_csv(path, index=False, encoding="utf-8")
                    csv_files["crypto_historico"] = str(path)
            
            elif domain == "economia":
                if "data" in data and data["data"]:
                    df = pd.DataFrame(data["data"])
                    path = self.serving_path / "powerbi" / "economia_diario.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(path, index=False, encoding="utf-8")
                    csv_files["economia_diario"] = str(path)
        
        logger.info(f"CSVs para Power BI gerados: {list(csv_files.keys())}")
        return csv_files
    
    def _generate_metadata(self, transformed: Dict[str, Any]) -> str:
        """Gera arquivo de metadados das tabelas."""
        metadata = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "source": "data-pipeline-estudo",
            "tables": {}
        }
        
        for domain, data in transformed.items():
            if domain == "clima":
                if "daily" in data and data["daily"]:
                    df = pd.DataFrame(data["daily"])
                    metadata["tables"]["clima_diario"] = self._table_metadata(df, "clima_diario")
                if "hourly" in data and data["hourly"]:
                    df = pd.DataFrame(data["hourly"])
                    metadata["tables"]["clima_horario"] = self._table_metadata(df, "clima_horario")
            
            elif domain == "crypto":
                if "market" in data and data["market"]:
                    df = pd.DataFrame(data["market"])
                    metadata["tables"]["crypto_market"] = self._table_metadata(df, "crypto_market")
                if "history" in data and data["history"]:
                    df = pd.DataFrame(data["history"])
                    metadata["tables"]["crypto_historico"] = self._table_metadata(df, "crypto_historico")
            
            elif domain == "economia":
                if "data" in data and data["data"]:
                    df = pd.DataFrame(data["data"])
                    metadata["tables"]["economia_diario"] = self._table_metadata(df, "economia_diario")
        
        path = self.serving_path / "powerbi" / "metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        return str(path)
    
    def _table_metadata(self, df: pd.DataFrame, table_name: str) -> Dict[str, Any]:
        """Gera metadados de uma tabela."""
        cols = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            sample = df[col].dropna().head(3).tolist()
            null_pct = (df[col].isnull().sum() / len(df) * 100).round(2)

            cols.append({
                "name": col,
                "type": dtype,
                "nullable": df[col].isnull().any(),
                "null_percentage": float(null_pct),
                "sample_values": sample,
                "unique_count": int(df[col].nunique()) if df[col].nunique() < 1000 else "1000+"
            })

            # Find date/datetime columns
            date_cols = df.select_dtypes(include=["datetime64", "datetime64[ns]"]).columns
            date_range = {"min": None, "max": None}
            if len(date_cols) > 0:
                try:
                            min_vals = df[date_cols].min()
                            max_vals = df[date_cols].max()
                            date_range["min"] = str(min_vals.min()) if not min_vals.isna().all() else None
                            date_range["max"] = str(max_vals.max()) if not max_vals.isna().all() else None
                except Exception:
                            pass

            return {
                "name": table_name,
                "row_count": int(len(df)),
                "column_count": len(df.columns),
                "columns": cols,
                "date_range": date_range
            }
    
    def _generate_connection_guide(self) -> str:
        """Gera guia de conexão para Power BI."""
        guide = f"""# Guia de Conexão - Power BI

## Visão Geral
Este pipeline gera dados diários de clima (Open-Meteo), criptomoedas (CoinGecko) e indicadores econômicos (BCB/SGS).
Os dados estão disponíveis em formato CSV e Parquet no GitHub Pages.

## URLs de Acesso (após deploy no GitHub Pages)

Base URL: `{self.github_pages_url or 'https://<SEU_USUARIO>.github.io/<SEU_REPO>/data/serving/'}`

### Arquivos CSV (Recomendado para Power BI Web Connector)
- Clima Diário: `powerbi/clima_diario.csv`
- Clima Horário (últimas 48h): `powerbi/clima_horario_recente.csv`
- Crypto Market: `powerbi/crypto_market.csv`
- Crypto Histórico: `powerbi/crypto_historico.csv`
- Economia Diário: `powerbi/economia_diario.csv`

### Arquivos Parquet (Para uso avançado)
- Clima Diário: `clima/diario/` (particionado por date, state)
- Clima Horário: `clima/horario/` (particionado por date, state)
- Crypto Diário: `crypto/diario/` (particionado por date)
- Crypto Histórico: `crypto/historico/` (particionado por date, coin_id)
- Economia Diário: `economia/diario/` (particionado por date, series_code)

## Como Conectar no Power BI Desktop

### Opção 1: Web Connector (Mais Simples)
1. Power BI Desktop → Obter Dados → Web
2. Cole a URL completa do CSV (ex: `https://usuario.github.io/repo/powerbi/clima_diario.csv`)
3. Power BI detecta automaticamente o CSV
4. Repita para cada tabela necessária

### Opção 2: Pasta (Para Parquet)
1. Obter Dados → Pasta
2. Aponte para a pasta local onde clonou o repo (ou use GitHub como fonte)
3. Combine arquivos Parquet

## Modelo de Dados Sugerido

### Tabelas de Dimensão
- **Dim_Cidade** (city, state, latitude, longitude) - chave: city+state
- **Dim_Moeda** (coin_id, symbol, name) - chave: coin_id
- **Dim_Serie_Economica** (series_code, series_name, description, unit) - chave: series_code
- **Dim_Data** (date, year, month, day, week, quarter, season, is_weekend) - chave: date

### Tabelas de Fato
- **Fato_Clima_Diario** (city, state, date, temp_max, temp_min, temp_mean, precip, humidity, wind, uv, etc.)
- **Fato_Clima_Horario** (city, state, datetime, temp, humidity, precip, wind, etc.)
- **Fato_Crypto_Market** (coin_id, date, price_brl, price_usd, market_cap, volume, change_24h, etc.)
- **Fato_Crypto_Historico** (coin_id, date, price_usd, market_cap, volume)
- **Fato_Economia** (series_code, date, value, change_1d, pct_change_1d, ma_7d, ma_30d, alert)

## Relacionamentos
- Dim_Cidade 1:* Fato_Clima_Diario (city+state)
- Dim_Cidade 1:* Fato_Clima_Horario (city+state)
- Dim_Moeda 1:* Fato_Crypto_Market (coin_id)
- Dim_Moeda 1:* Fato_Crypto_Historico (coin_id)
- Dim_Serie_Economica 1:* Fato_Economia (series_code)
- Dim_Data 1:* Todas as tabelas de fato (date)

## Atualização Automática
- Pipeline roda diariamente às 06:00 (horário de Brasília) via GitHub Actions
- Dados ficam disponíveis em ~10-15 min após execução
- Configure atualização agendada no Power BI Service para 07:00

## Medidas DAX Sugeridas
Veja arquivo `dax_measures.txt` para medidas prontas.

## Solução de Problemas
- **Erro 404**: Verifique se o GitHub Pages está ativo (Settings → Pages → Deploy from branch → gh-pages)
- **Dados antigos**: Limpe cache do Power BI (Arquivo → Opções → Limpar cache)
- **Timeout**: CSVs grandes podem demorar; use Parquet particionado para datasets maiores

## Contato
Projeto: data-pipeline-estudo
Autor: Matheus Capelo
"""
        
        path = self.serving_path / "powerbi" / "CONEXAO_POWERBI.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(guide)
        
        return str(path)
    
    def _generate_dax_measures(self) -> str:
        """Gera medidas DAX sugeridas."""
        dax = """# Medidas DAX Sugeridas para o Dashboard

## ==========================================
## CLIMA
## ==========================================

// Temperatura média ponderada por população (se tiver pop)
Temp_Media_Ponderada = 
DIVIDE(
    SUMX(Fato_Clima_Diario, Fato_Clima_Diario[temp_mean] * Dim_Cidade[populacao]),
    SUM(Dim_Cidade[populacao])
)

// Amplitude térmica média
Temp_Amplitude_Media = AVERAGE(Fato_Clima_Diario[temp_amplitude])

// Dias com chuva (%)
Pct_Dias_Chuva = 
DIVIDE(
    CALCULATE(COUNTROWS(Fato_Clima_Diario), Fato_Clima_Diario[precipitation_sum] > 0),
    COUNTROWS(Fato_Clima_Diario)
)

// Precipitação total no período
Precip_Total = SUM(Fato_Clima_Diario[precipitation_sum])

// UV Index máximo
UV_Max = MAX(Fato_Clima_Diario[uv_index_max])

// Variação de temperatura vs média histórica (7 dias)
Temp_vs_Media_7d = 
VAR Media7d = CALCULATE(AVERAGE(Fato_Clima_Diario[temp_mean]), 
    DATESINPERIOD(Dim_Data[date], MAX(Dim_Data[date]), -7, DAY))
RETURN
AVERAGE(Fato_Clima_Diario[temp_mean]) - Media7d

// Alerta de onda de calor (temp > 35°C por 3+ dias)
Alerta_Onda_Calor = 
VAR Consecutivos = 
    CALCULATE(
        COUNTROWS(Fato_Clima_Diario),
        Fato_Clima_Diario[temp_max] > 35,
        DATESINPERIOD(Dim_Data[date], MAX(Dim_Data[date]), -3, DAY)
    )
RETURN
IF(Consecutivos >= 3, "⚠️ Onda de Calor", "✅ Normal")


## ==========================================
## CRYPTO
## ==========================================

// Preço médio ponderado por volume (VWAP simplificado)
Preco_VWAP_24h = 
DIVIDE(
    SUMX(Fato_Crypto_Market, Fato_Crypto_Market[price_brl] * Fato_Crypto_Market[volume_brl]),
    SUM(Fato_Crypto_Market[volume_brl])
)

// Market Cap Total (BRL)
Market_Cap_Total_BRL = SUM(Fato_Crypto_Market[market_cap_brl])

// Dominância do Bitcoin
BTC_Dominance = 
DIVIDE(
    CALCULATE(SUM(Fato_Crypto_Market[market_cap_brl]), Dim_Moeda[symbol] = "BTC"),
    [Market_Cap_Total_BRL]
)

// Variação 24h média ponderada
Var_24h_Ponderada = 
DIVIDE(
    SUMX(Fato_Crypto_Market, Fato_Crypto_Market[change_24h] * Fato_Crypto_Market[market_cap_brl]),
    SUM(Fato_Crypto_Market[market_cap_brl])
)

// Top Gainers (maior alta 24h)
Top_Gainers = 
TOPN(5, 
    SUMMARIZE(Fato_Crypto_Market, Dim_Moeda[symbol], "Var24h", SUM(Fato_Crypto_Market[change_24h])),
    [Var24h], DESC
)

// Top Losers (maior queda 24h)
Top_Losers = 
TOPN(5, 
    SUMMARIZE(Fato_Crypto_Market, Dim_Moeda[symbol], "Var24h", SUM(Fato_Crypto_Market[change_24h])),
    [Var24h], ASC
)

// Distância do ATH (%)
Pct_From_ATH = AVERAGE(Fato_Crypto_Market[pct_from_ath])

// Volume/Market Cap Ratio (Liquidez)
Liquidez_Media = AVERAGE(Fato_Crypto_Market[volume_market_cap_ratio])


## ==========================================
## ECONOMIA
## ==========================================

// Selic Atual
Selic_Atual = 
CALCULATE(
    LASTNONBLANKVALUE(Dim_Data[date], AVERAGE(Fato_Economia[value])),
    Dim_Serie_Economica[series_code] = 11
)

// IPCA Acumulado 12m
IPCA_12m = 
CALCULATE(
    PRODUCTX(
        FILTER(Fato_Economia, Dim_Serie_Economica[series_code] = 433),
        1 + Fato_Economia[value] / 100
    ) - 1
) * 100

// Dólar Atual
Dolar_Atual = 
CALCULATE(
    LASTNONBLANKVALUE(Dim_Data[date], AVERAGE(Fato_Economia[value])),
    Dim_Serie_Economica[series_code] = 1
)

// Variação Cambial 30d
Var_Cambio_30d = 
VAR Atual = [Dolar_Atual]
VAR Passado = 
    CALCULATE(
        LASTNONBLANKVALUE(Dim_Data[date], AVERAGE(Fato_Economia[value])),
        Dim_Serie_Economica[series_code] = 1,
        DATEADD(Dim_Data[date], -30, DAY)
    )
RETURN
DIVIDE(Atual - Passado, Passado) * 100

// Alerta de séries econômicas
Alerta_Economico = 
CONCATENATEX(
    FILTER(Fato_Economia, Fato_Economia[alert] = "Alerta"),
    Dim_Serie_Economica[series_name] & ": " & FORMAT(Fato_Economia[value], "#,##0.00") & " (" & FORMAT(Fato_Economia[z_score_30d], "+#.##;-#.##") & "σ)",
    " | "
)


## ==========================================
## CRUZAMENTOS (INSIGHTS)
## ==========================================

// Correlação Temp vs Crypto (exemplo simplificado)
Correl_Temp_BTC = 
VAR TempSeries = CALCULATETABLE(VALUES(Fato_Clima_Diario[temp_mean]), Dim_Cidade[city] = "São Paulo")
VAR BTCSeries = CALCULATETABLE(VALUES(Fato_Crypto_Market[price_brl]), Dim_Moeda[symbol] = "BTC")
RETURN
// Requer cálculo mais complexo com CORREL ou R/Python visual

// Índice de Conforto vs Atividade Crypto
// Hipótese: dias mais agradáveis = mais trading?
Conforto_vs_Volume = 
DIVIDE(
    SUMX(Fato_Clima_Diario, Fato_Clima_Diario[heat_index] * Fato_Crypto_Market[volume_brl]),
    SUM(Fato_Crypto_Market[volume_brl])
)


## ==========================================
## TIME INTELLIGENCE
## ==========================================

// YTD, MTD, QTD para qualquer medida
Vendas_YTD = TOTALYTD([Medida], Dim_Data[date])
Vendas_MTD = TOTALMTD([Medida], Dim_Data[date])
Vendas_QTD = TOTALQTD([Medida], Dim_Data[date])

// Same Period Last Year
SPLY = CALCULATE([Medida], SAMEPERIODLASTYEAR(Dim_Data[date]))

// YoY Growth
YoY_Growth = DIVIDE([Medida] - [SPLY], [SPLY])

// Rolling 7/30 days
Rolling_7d = CALCULATE([Medida], DATESINPERIOD(Dim_Data[date], MAX(Dim_Data[date]), -7, DAY))
Rolling_30d = CALCULATE([Medida], DATESINPERIOD(Dim_Data[date], MAX(Dim_Data[date]), -30, DAY))
"""
        
        path = self.serving_path / "powerbi" / "dax_measures.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(dax)
        
        return str(path)