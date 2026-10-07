"""Executa ingestão IBGE, analytics (Sprint 2) e clusterização (Sprint 3) em sequência."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from src.analytics.generate_report import main as run_analytics
from src.ingestion.run_ibge_discovery import main as run_ingestion
from src.modeling.run_clustering import main as run_clustering
from src.utils.paths import DASHBOARDS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: IBGE/SIDRA → base analítica → relatórios HTML."
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Não chama o IBGE; usa data/gold/municipal_gold_initial.csv já existente.",
    )
    args = parser.parse_args()

    steps: list[tuple[str, Callable[[], None]]] = []
    if not args.skip_ingestion:
        steps.append(("Ingestão e Gold inicial (IBGE/SIDRA)", run_ingestion))
    steps.extend(
        [
            ("Analytics Sprint 2", run_analytics),
            ("Modelagem Sprint 3", run_clustering),
        ]
    )

    for title, step in steps:
        print(f"\n{'=' * 60}\n{title}\n{'=' * 60}\n")
        step()

    print("\nPipeline concluído.")
    print(f"Dashboards: {DASHBOARDS / 'sprint2_data_catalog.html'}")
    print(f"            {DASHBOARDS / 'sprint3_model_report.html'}")


if __name__ == "__main__":
    main()
