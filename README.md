# Location Intelligence Brasil

Protótipo de inteligência territorial municipal: integra dados públicos do IBGE (SIDRA), gera bases analíticas por município, aplica segmentação (clusters) e oferece um app para **pré-selecionar** localidades conforme o perfil do negócio ou **comparar** cidades.

Não substitui estudo de ponto comercial, concorrência ou viabilidade financeira.

## O que há neste repositório

| Caminho | Função |
|---------|--------|
| `src/ingestion`, `src/transformation` | Coleta e padronização IBGE → camadas bronze/silver |
| `src/analytics` | Indicadores derivados e relatório de qualidade |
| `src/modeling` | Clusterização (K-means) e relatório técnico |
| `src/pipeline` | Orquestração do fluxo completo |
| `src/app` | Aplicação Streamlit |
| `data/` | Dados do pipeline (bronze, silver, gold) |
| `outputs/dashboards` | Relatórios HTML gerados |
| `outputs/data` | Resumos JSON e métricas da última execução |
| `docs/` | Notas da descoberta de dados (`data_discovery.md`) |

## Pré-requisitos

Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Rodar o pipeline

Atualiza dados (opcional), base analítica, clusters e relatórios HTML:

```bash
uv run python -m src.pipeline
```

Sem chamar a API do IBGE (usa a gold já presente no repo):

```bash
uv run python -m src.pipeline --skip-ingestion
```

Relatórios estáticos (opcional):

```bash
open outputs/dashboards/sprint2_data_catalog.html
open outputs/dashboards/sprint3_model_report.html
```

## Rodar o app

Na raiz do repositório, após o pipeline (precisa de `data/gold/municipal_clustered_base.csv`):

```bash
uv run streamlit run src/app/streamlit_app.py
```

- **Perfil da empresa** — questionário e ranking de municípios compatíveis.  
- **Comparar municípios** — indicadores, cluster e diferenças lado a lado.
