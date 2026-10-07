from __future__ import annotations

import logging
from datetime import datetime
import pandas as pd

from src.ingestion.ibge_client import IBGEClient
from src.transformation.sidra import normalize_sidra_long, pivot_indicators, sidra_to_dataframe
from src.utils.io import write_dataframe, write_json
from src.utils.paths import BRONZE, DOCS, GOLD, SILVER
from src.validation.basic_checks import summarize_dataframe, validate_gold

SOURCES = {
    "population_estimate": {
        "table_id": "6579",
        "period": "2024",
        "variables": ["9324"],
        "indicator_map": {"9324": "population_estimated"},
    },
    "municipal_gdp": {
        "table_id": "5938",
        "period": "2021",
        "variables": ["37"],
        "indicator_map": {"37": "gdp_current_brl_thousand"},
    },
    "cempre_general": {
        "table_id": "9509",
        "period": "2024",
        "variables": ["706", "367", "707", "708", "662", "10143"],
        "indicator_map": {
            "706": "local_units",
            "367": "active_companies",
            "707": "employed_total",
            "708": "employed_salaried",
            "662": "wages_brl_thousand",
            "10143": "avg_monthly_salary_brl",
        },
    },
    "census_area_density": {
        "table_id": "4714",
        "period": "2022",
        "variables": ["93", "6318", "614"],
        "indicator_map": {
            "93": "census_population",
            "6318": "area_km2",
            "614": "density_per_km2",
        },
    },
}


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def flatten_municipalities(rows: list[dict]) -> pd.DataFrame:
    records = []
    for row in rows:
        if row.get("microrregiao") and row["microrregiao"].get("mesorregiao"):
            uf = row["microrregiao"]["mesorregiao"]["UF"]
        else:
            uf = row["regiao-imediata"]["regiao-intermediaria"]["UF"]
        records.append(
            {
                "municipality_code": str(row["id"]),
                "municipality_name_ref": row["nome"],
                "state_code": uf["id"],
                "state": uf["sigla"],
                "state_name": uf["nome"],
                "region": uf["regiao"]["nome"],
            }
        )
    return pd.DataFrame(records)


def build_markdown_report(summary: dict, gold_issues: list[str]) -> str:
    lines = [
        "# Data discovery IBGE/SIDRA",
        "",
        f"Gerado em: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Documentação oficial consultada",
        "",
        "- API de dados agregados do IBGE/SIDRA: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3",
        "- API de localidades do IBGE: https://servicodados.ibge.gov.br/api/docs/localidades",
        "- Lista de municípios usada como referência: https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
        "",
        "## Fontes testadas",
        "",
    ]
    for name, item in summary["sources"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Tabela SIDRA: `{item['table_id']}`",
                f"- Endpoint dados: `{item['data_url_pattern']}`",
                f"- Período consultado: `{item['period']}`",
                f"- Variáveis: {', '.join(item['variables'])}",
                f"- Linhas Bronze: {item['bronze_rows']}",
                f"- Linhas Silver: {item['silver_rows']}",
                f"- Municípios distintos: {item['municipalities']}",
                f"- Colunas Bronze: {', '.join(item['bronze_columns'])}",
                "",
            ]
        )

    lines.extend(
        [
            "## Tabela Gold inicial",
            "",
            f"- Linhas: {summary['gold']['rows']}",
            f"- Colunas: {summary['gold']['columns']}",
            f"- Municípios distintos: {summary['gold']['municipalities']}",
            f"- Colunas: {', '.join(summary['gold']['column_names'])}",
            f"- Valores nulos por coluna: {summary['gold']['null_counts']}",
            f"- Problemas de validação: {', '.join(gold_issues) if gold_issues else 'nenhum problema crítico encontrado'}",
            "",
            "Observação territorial: a base de localidades do IBGE já traz `Boa Esperança do Norte` (`5101837`), em Mato Grosso. Nas consultas SIDRA testadas, esse município aparece sem valor (`...`) ou ainda não aparece em PIB/Censo/CEMPRE, o que reforça a necessidade de controlar safra territorial e período de cada fonte.",
            "",
            "## Viabilidade do projeto",
            "",
            "**SIM, COM RESSALVAS.** A PoC conseguiu conectar em APIs oficiais do IBGE, obter dados municipais, integrar mais de uma fonte pelo código municipal e gerar uma primeira Gold com uma linha por município. As ressalvas principais são escolher variáveis com granularidade municipal, documentar diferenças de período entre fontes e evitar consultas muito amplas de tabelas com classificações detalhadas, como CEMPRE por CNAE.",
            "",
            "## Próximos passos recomendados",
            "",
            "- Manter População/Área/Densidade, PIB dos Municípios e CEMPRE geral como fontes iniciais.",
            "- Investigar variáveis de idade, renda e escolaridade do Censo 2022 antes do clustering.",
            "- Usar CEMPRE por CNAE em amostras controladas para criar indicadores setoriais derivados, não como extração bruta total no primeiro momento.",
            "- Criar indicadores derivados: PIB per capita, empresas por 1.000 habitantes, empregos por 1.000 habitantes, salário médio, densidade e composição econômica.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    setup_logging()
    client = IBGEClient()

    summary: dict = {"sources": {}}

    municipalities_raw = client.get_municipalities()
    write_json(BRONZE / "localidades_municipios_raw.json", municipalities_raw)
    municipalities = flatten_municipalities(municipalities_raw)
    write_dataframe(municipalities, SILVER / "municipalities.csv")

    gold = municipalities.copy()

    for source_name, config in SOURCES.items():
        table_id = config["table_id"]
        metadata = client.get_aggregate_metadata(table_id)
        periods = client.get_aggregate_periods(table_id)
        values = client.get_sidra_values(
            table_id=table_id,
            period=config["period"],
            variables=config["variables"],
        )

        write_json(BRONZE / f"{source_name}_metadata.json", metadata)
        write_json(BRONZE / f"{source_name}_periods.json", periods)
        write_json(BRONZE / f"{source_name}_raw.json", values)

        bronze_df = sidra_to_dataframe(values)
        silver_long = normalize_sidra_long(bronze_df, source_name)
        silver_wide = pivot_indicators(silver_long, config["indicator_map"])

        write_dataframe(silver_long, SILVER / f"{source_name}_long.csv")
        write_dataframe(silver_wide, SILVER / f"{source_name}_wide.csv")

        gold = gold.merge(
            silver_wide.drop(columns=["municipality_name"], errors="ignore"),
            on="municipality_code",
            how="left",
            suffixes=("", f"_{source_name}"),
        )

        summary["sources"][source_name] = {
            "table_id": table_id,
            "period": config["period"],
            "variables": config["variables"],
            "data_url_pattern": (
                "https://apisidra.ibge.gov.br/values"
                f"/t/{table_id}/n6/all/v/{','.join(config['variables'])}/p/{config['period']}/h/y/f/a/d/m"
            ),
            "bronze_rows": int(len(bronze_df)),
            "silver_rows": int(len(silver_long)),
            "municipalities": int(silver_long["municipality_code"].nunique()),
            "bronze_columns": list(bronze_df.columns),
            "dataframe_summary": summarize_dataframe(silver_long),
        }

    period_cols = [col for col in gold.columns if col == "period" or col.startswith("period_")]
    gold = gold.drop(columns=period_cols, errors="ignore")
    if "population_estimated" in gold and "gdp_current_brl_thousand" in gold:
        gold["gdp_per_capita_estimated"] = (
            gold["gdp_current_brl_thousand"] * 1000 / gold["population_estimated"]
        )
    if "population_estimated" in gold and "active_companies" in gold:
        gold["active_companies_per_1000_inhabitants"] = (
            gold["active_companies"] / gold["population_estimated"] * 1000
        )

    write_dataframe(gold, GOLD / "municipal_gold_initial.csv")
    write_dataframe(gold, GOLD / "municipal_gold_initial.parquet")

    summary["gold"] = summarize_dataframe(gold)
    summary["gold"]["municipalities"] = int(gold["municipality_code"].nunique())
    summary["gold"]["null_counts"] = {
        col: int(gold[col].isna().sum()) for col in gold.columns if int(gold[col].isna().sum()) > 0
    }
    gold_issues = validate_gold(gold)
    summary["gold"]["validation_issues"] = gold_issues
    write_json(DOCS / "discovery_summary.json", summary)
    (DOCS / "data_discovery.md").write_text(build_markdown_report(summary, gold_issues), encoding="utf-8")

    print("=== IBGE/SIDRA DATA DISCOVERY ===")
    for source_name, item in summary["sources"].items():
        print(
            f"{source_name}: tabela {item['table_id']} | periodo {item['period']} | "
            f"bronze_rows={item['bronze_rows']} | municipios={item['municipalities']}"
        )
    print(
        f"GOLD: rows={summary['gold']['rows']} | columns={summary['gold']['columns']} | "
        f"municipios={summary['gold']['municipalities']}"
    )
    print(f"Validation issues: {gold_issues or 'none'}")
    print(f"Gold file: {GOLD / 'municipal_gold_initial.csv'}")
    print(f"Report: {DOCS / 'data_discovery.md'}")


if __name__ == "__main__":
    main()
