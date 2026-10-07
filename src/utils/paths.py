"""Caminhos do projeto: camadas de dados vs artefatos de execução."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Medallion: respostas brutas, tabelas integradas e bases analíticas (entrada/saída do pipeline).
DATA = ROOT / "data"
BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD = DATA / "gold"

# Documentação escrita (não gerada pelo pipeline de relatórios).
DOCS = ROOT / "docs"

# Artefatos gerados: resumos de execução, métricas de modelo e dashboards HTML.
OUTPUTS = ROOT / "outputs"
OUTPUT_DATA = OUTPUTS / "data"
DASHBOARDS = OUTPUTS / "dashboards"
