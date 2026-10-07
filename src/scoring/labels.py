"""Rótulos em português para indicadores e clusters."""

FEATURES_ML = [
    "gdp_per_capita_estimated",
    "density_per_km2",
    "active_companies_per_1000_inhabitants",
    "employed_per_1000_inhabitants",
    "avg_monthly_salary_brl",
    "formal_employment_rate",
]

FEATURE_LABELS: dict[str, str] = {
    "gdp_per_capita_estimated": "PIB per capita estimado (R$)",
    "density_per_km2": "Densidade demográfica (hab/km²)",
    "active_companies_per_1000_inhabitants": "Empresas ativas por mil habitantes",
    "employed_per_1000_inhabitants": "Empregos formais por mil habitantes",
    "avg_monthly_salary_brl": "Salário médio mensal (R$)",
    "formal_employment_rate": "Taxa de emprego assalariado (%)",
    "population_estimated": "População estimada",
    "gdp_current_brl_thousand": "PIB municipal (R$ mil)",
    "active_companies": "Empresas ativas",
    "employed_total": "Total de empregados formais",
}

# cluster_id na base = 0..k-1 do K-means; na interface exibimos +1 (Cluster 1..3).
CLUSTER_SUMMARY: dict[int, str] = {
    0: "Territórios com maior PIB per capita e densidade — perfil mais urbano e de maior renda média.",
    1: "Territórios com indicadores econômicos em geral abaixo da mediana nacional — mercados menores ou em estruturação.",
    2: "Territórios com forte dinamismo empresarial e emprego relativo à população — consumo e varejo em escala.",
}


def cluster_label(cluster_id: int | float) -> str:
    cid = int(cluster_id)
    return f"Cluster {cid + 1}"

COMPARE_METRICS = [
    "population_estimated",
    "gdp_per_capita_estimated",
    "density_per_km2",
    "active_companies_per_1000_inhabitants",
    "employed_per_1000_inhabitants",
    "avg_monthly_salary_brl",
    "formal_employment_rate",
    "active_companies",
    "employed_total",
]
