# Guia de Conexão - Power BI

## Visão Geral
Este pipeline gera dados diários de clima (Open-Meteo), criptomoedas (CoinGecko) e indicadores econômicos (BCB/SGS).
Os dados estão disponíveis em formato CSV e Parquet no GitHub Pages.

## URLs de Acesso (após deploy no GitHub Pages)

Base URL: `https://tlcapelo.github.io/Dados/data/serving/`

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
2. Cole a URL completa do CSV (ex: `https://usuario.github.io/repo/data/serving/powerbi/clima_diario.csv`)
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
