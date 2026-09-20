# PFC Location Intelligence - Data Discovery

PoC inicial para validar a viabilidade técnica de uma solução de inteligência territorial municipal usando dados públicos oficiais do IBGE.

## Objetivo desta etapa

- Conectar em APIs oficiais do IBGE/SIDRA.
- Ler metadados e dados municipais reais.
- Avaliar linhas, colunas, períodos, variáveis e cobertura municipal.
- Gerar uma primeira tabela Gold com uma linha por município.

## Execução com uv (recomendado)

Requer Python 3.11 ou superior e o [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m src.ingestion.run_ibge_discovery
```

O `uv sync` cria o ambiente virtual local e instala as dependências a partir
do `pyproject.toml` e do `uv.lock`.

## Execução com venv/pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.ingestion.run_ibge_discovery
```

Os resultados são gravados em:

- `data/bronze/`: respostas brutas e metadados da consulta.
- `data/silver/`: dados tabulares padronizados.
- `data/gold/`: primeira tabela municipal integrada.
- `docs/data_discovery.md`: resumo técnico da descoberta.

## Sprint 2: base analítica e catálogo

Depois de gerar a Gold inicial, atualize a base analítica e o relatório HTML:

```bash
uv run python -m src.analytics.generate_report
```

O comando gera `data/gold/municipal_analytical_base.csv` e
`docs/reports/sprint2_data_catalog.html`, com indicadores derivados,
catálogo de variáveis, validações, nulos e correlações.

## Sprint 3: avaliação e ajustes analíticos

### Execução do analytics

Com o ambiente instalado e a Gold inicial atualizada, execute:

```bash
uv run python -m src.analytics.generate_report
```

O comando lê `data/gold/municipal_gold_initial.csv`, recalcula os
indicadores analíticos e atualiza:

- `data/gold/municipal_analytical_base.csv`: base municipal enriquecida;
- `docs/reports/sprint2_data_catalog.html`: catálogo visual e relatório de qualidade;
- `docs/reports/sprint2_summary.json`: resumo estruturado da execução.

O relatório HTML pode ser aberto diretamente no navegador. Sempre que o
comando for executado, esses arquivos são sobrescritos com os resultados
mais recentes.

A Sprint 3 utiliza a base analítica enriquecida para preparar e avaliar a
segmentação não supervisionada dos municípios.

Objetivos desta etapa:

- selecionar as variáveis com justificativa de negócio;
- tratar valores ausentes, assimetrias e outliers;
- aplicar transformações e escalonamento;
- avaliar correlações e variáveis redundantes;
- explorar PCA para avaliar a estrutura multivariada;
- testar diferentes quantidades de clusters;
- comparar métricas, estabilidade e interpretabilidade;
- descrever os perfis municipais encontrados;
- registrar limitações e ajustes do modelo.

Os principais produtos esperados são:

- base analítica preparada para modelagem;
- relatório de transformações e variáveis selecionadas;
- métricas de avaliação dos agrupamentos;
- perfis interpretáveis dos clusters;
- documentação das limitações e decisões analíticas.
