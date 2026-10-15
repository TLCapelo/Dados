# Data Pipeline Estudo 📊

Pipeline de dados automatizado que coleta dados de **clima (Open-Meteo)**, **criptomoedas (CoinGecko)** e **indicadores econômicos (BCB/SGS)**, processa e disponibiliza para **Power BI** com deploy automático no **GitHub Pages**.

## 🎯 Objetivo

Demonstrar habilidades de engenharia de dados:
- Extração de APIs públicas (REST)
- Transformação e validação de dados com pandas
- Armazenamento em Parquet particionado
- Orquestração com GitHub Actions
- Preparação para Business Intelligence (Power BI)
- Documentação técnica completa

## 🏗️ Arquitetura

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│  Scheduler  │───▶│  Extractor   │───▶│ Transformer │───▶│   Loader     │
│ (GitHub     │    │ (Open-Meteo, │    │ (limpeza,   │    │ (Parquet/    │
│  Actions    │    │  CoinGecko,  │    │  enriquece, │    │  CSV + PBIX) │
│  daily 06h) │    │  BCB/SGS)    │    │  valida)    │    │              │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
                    │  Raw Zone    │    │ Staging     │    │  Serving     │
                    │ (JSON/CSV)   │    │ (Parquet)   │    │ (GitHub Pages│
                    │  /data/raw   │    │ /data/staging│   │  + Power BI) │
                    └──────────────┘    └─────────────┘    └──────────────┘
```

## 📊 Fontes de Dados

| Fonte | API | Frequência | Dados Principais |
|-------|-----|------------|------------------|
| **Open-Meteo** | Gratuita, sem key | Diária/Horária | Temp, chuva, vento, umidade, UV, radiação (10 cidades BR) |
| **CoinGecko** | API pública | Diária | Preço, market cap, volume, variação 24h/7d/30d (10 moedas; limite local de 10 req/min) |
| **BCB/SGS** | Gratuita | Diária | Selic, CDI, Dólar, Euro, IPCA, IGP-M, PIB, Desemprego, Dívida, Reservas |

## 🚀 Quick Start

### Pré-requisitos
- Python 3.11+
- Git
- Conta GitHub (para Actions + Pages)

### Instalação Local

```bash
# Clone o repositório
git clone https://github.com/TLCapelo/Dados.git
cd Dados

# Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instale dependências
pip install -r requirements.txt

# Execute o pipeline
python src/pipeline.py
```

### Configuração no GitHub

1. Confirme que GitHub Actions está habilitado em **Settings → Actions → General**.
2. Ative GitHub Pages em **Settings → Pages**: escolha **Deploy from a branch**, branch `gh-pages` e pasta `/ (root)`.
3. Acesse **Actions → Daily Data Pipeline → Run workflow** para iniciar uma execução manual. O workflow também roda diariamente às 06h BRT.
4. Quando os dados mudarem, o workflow atualiza `data/serving/` na branch `main` e publica os arquivos no GitHub Pages.

## ⚙️ Configuração

Edite `config.yaml` para personalizar:

```yaml
# Cidades para monitorar (clima)
open_meteo:
  cities:
    - name: "Sua Cidade"
      state: "UF"
      latitude: -XX.XXXX
      longitude: -XX.XXXX

# Criptomoedas para monitorar
coingecko:
  coins:
    - id: "bitcoin"
      symbol: "BTC"
      name: "Bitcoin"

# Séries econômicas (BCB/SGS)
bcb:
  series:
    - code: 11
      name: "selic"
      description: "Taxa Selic"
      unit: "percentual_aa"
```

## 📁 Estrutura do Projeto

```
data-pipeline-estudo/
├── .github/workflows/etl.yml      # GitHub Actions (diário 06h BRT)
├── src/
│   ├── config.py                  # Carregador de config YAML
│   ├── pipeline.py                # Orquestrador principal
│   ├── extract/
│   │   ├── open_meteo.py          # Extrator clima
│   │   ├── coingecko.py           # Extrator crypto
│   │   └── bcb.py                 # Extrator economia
│   ├── transform/
│   │   ├── clean.py               # Limpeza/normalização
│   │   ├── enrich.py              # Enriquecimento (campos derivados)
│   │   └── validate.py            # Validação de qualidade dos dados
│   └── load/
│       ├── to_parquet.py          # Salva Parquet particionado
│       └── to_powerbi.py          # Prepara CSVs + docs Power BI
├── config.yaml                    # Configuração centralizada
├── requirements.txt
├── data/
│   ├── raw/                       # Dados brutos (JSON/CSV)
│   ├── staging/                   # Dados intermediários
│   └── serving/                   # Dados finais (Parquet + CSV Power BI)
│       └── powerbi/               # CSVs consolidados + docs
│           ├── clima_diario.csv
│           ├── crypto_market.csv
│           ├── economia_diario.csv
│           ├── metadata.json
│           ├── CONEXAO_POWERBI.md
│           └── dax_measures.txt
├── powerbi/
│   └── dashboard.pbix             # Template (criar manualmente)
└── logs/
    └── pipeline.log
```

## 📈 Power BI - Conexão Rápida

Após o primeiro deploy (aguarde ~15 min após push):

1. **Power BI Desktop** → Obter Dados → **Web**
2. Cole a URL: `https://tlcapelo.github.io/Dados/data/serving/powerbi/clima_diario.csv`
3. Repita para: `crypto_market.csv`, `economia_diario.csv`
4. Modele relacionamentos usando `Dim_Data`, `Dim_Cidade`, `Dim_Moeda`, `Dim_Serie_Economica`
5. Use as medidas DAX do arquivo `dax_measures.txt`

### Tabelas Disponíveis

| Tabela | Chave | Descrição |
|--------|-------|-----------|
| `clima_diario` | city+state+date | 15 variáveis climáticas/dia |
| `clima_horario` | city+state+datetime | 9 variáveis/hora (últimas 48h) |
| `crypto_market` | coin_id+date | Preço, market cap, volume, var% |
| `crypto_historico` | coin_id+date | Histórico 30 dias (USD) |
| `economia_diario` | series_code+date | 15 indicadores BCB + variações |

## 🔧 Desenvolvimento

### Executar Testes
```bash
pytest tests/ -v
```

### Linting
```bash
ruff check src/
black src/
```

### Adicionar Nova Fonte
1. Crie `src/extract/nova_fonte.py` seguindo padrão
2. Adicione limpeza em `src/transform/clean.py`
3. Adicione enriquecimento em `src/transform/enrich.py`
4. Adicione validação em `src/transform/validate.py`
5. Registre no `src/pipeline.py`
6. Atualize `config.yaml`

## 📋 Logs e Monitoramento

- **GitHub Actions**: [execuções do pipeline](https://github.com/TLCapelo/Dados/actions/workflows/etl.yml)
- **Logs locais**: `logs/pipeline.log`
- **Artefatos**: Download nos runs do Actions (logs + relatórios validação)
- **Falhas**: Workflow `notify` pode ser estendido para Discord/Slack/Email

## 🛡️ Qualidade de Dados

Validações automáticas do pipeline:
- ✅ Não nulos em chaves primárias
- ✅ Unicidade composta (city+state+date, etc.)
- ✅ Intervalos válidos (temp -50 a 60°C, umidade 0-100%, etc.)
- ✅ Contagem mínima de linhas
- ✅ Médias dentro do esperado

## 📝 Licença

MIT License - Use livremente para estudo e portfolio.

## 👨‍💻 Autor

**Matheus Capelo** - Data Analyst & Software Engineer
- LinkedIn: [linkedin.com/in/mxxcapelo](https://linkedin.com/in/mxxcapelo)
- Portfolio: [seu-portfolio.com](https://seu-portfolio.com)

---

⭐ **Se este projeto te ajudou, deixe uma estrela!** ⭐