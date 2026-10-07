"""Perfis de negócio do questionário → pesos e filtros territoriais."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.scoring.labels import FEATURES_ML, FEATURE_LABELS

NATUREZA_OPTS = ["Produto físico", "Serviço", "Misto (produz e comercializa)"]
MACRO_OPTS = [
    "Comércio ao consumidor",
    "Indústria / transformação",
    "Serviços B2B",
    "Serviços ao consumidor",
    "Logística e armazenagem",
]
SUBTIPOS: dict[str, list[str]] = {
    "Comércio ao consumidor": ["Mercado / supermercado", "Farmácia", "Conveniência", "Vestuário / varejo geral"],
    "Indústria / transformação": ["Fábrica leve", "Alimentos e bebidas", "Metal-mecânico / diversos"],
    "Serviços B2B": ["Consultoria e serviços corporativos", "Tecnologia e serviços profissionais", "Manutenção industrial"],
    "Serviços ao consumidor": ["Saúde e clínicas", "Educação", "Alimentação fora do lar"],
    "Logística e armazenagem": ["Centro de distribuição", "Transporte e armazenagem regional"],
}
PORTE_OPTS = ["Micro", "Pequeno", "Médio", "Grande"]
REGIAO_OPTS = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


@dataclass
class BusinessProfile:
    name: str
    weights: dict[str, float]
    preferred_clusters: tuple[int, ...]
    population_min: int
    population_max: int | None
    employed_min: int
    notes: list[str] = field(default_factory=list)


def _base_weights() -> dict[str, float]:
    return {f: 0.0 for f in FEATURES_ML}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def build_profile(
    natureza: str,
    macro: str,
    subtipo: str,
    porte: str,
    regions: list[str] | None,
    states: list[str] | None,
    population_min_extra: int,
    population_max_extra: int | None = None,
) -> BusinessProfile:
    w = _base_weights()
    notes: list[str] = []
    preferred: list[int] = [1, 2]

    if natureza == "Produto físico":
        w["employed_per_1000_inhabitants"] += 1.2
        w["active_companies_per_1000_inhabitants"] += 1.0
        w["avg_monthly_salary_brl"] += 0.6
    elif natureza == "Serviço":
        w["gdp_per_capita_estimated"] += 1.1
        w["avg_monthly_salary_brl"] += 1.0
        w["formal_employment_rate"] += 0.8
    else:
        for k in w:
            w[k] += 0.5

    if macro == "Comércio ao consumidor":
        w["density_per_km2"] += 1.3
        w["active_companies_per_1000_inhabitants"] += 1.2
        w["employed_per_1000_inhabitants"] += 0.8
        preferred = [2, 1]
    elif macro == "Indústria / transformação":
        w["employed_per_1000_inhabitants"] += 1.4
        w["avg_monthly_salary_brl"] += 1.0
        w["active_companies_per_1000_inhabitants"] += 0.9
        preferred = [2, 0]
    elif macro == "Serviços B2B":
        w["gdp_per_capita_estimated"] += 1.5
        w["avg_monthly_salary_brl"] += 1.2
        w["formal_employment_rate"] += 1.0
        preferred = [0, 2]
    elif macro == "Serviços ao consumidor":
        w["density_per_km2"] += 1.0
        w["gdp_per_capita_estimated"] += 0.9
        w["employed_per_1000_inhabitants"] += 0.7
        preferred = [0, 2]
    elif macro == "Logística e armazenagem":
        w["employed_per_1000_inhabitants"] += 1.1
        w["active_companies_per_1000_inhabitants"] += 1.0
        w["density_per_km2"] += 0.4
        preferred = [2, 1]

    if "Farmácia" in subtipo:
        w["gdp_per_capita_estimated"] += 0.15
    elif "Fábrica" in subtipo or "Metal" in subtipo:
        w["employed_per_1000_inhabitants"] += 0.2
    elif "Consultoria" in subtipo or "Tecnologia" in subtipo:
        w["gdp_per_capita_estimated"] += 0.25

    pop_min, emp_min = {
        "Micro": (15_000, 500),
        "Pequeno": (35_000, 2_000),
        "Médio": (80_000, 8_000),
        "Grande": (200_000, 25_000),
    }[porte]

    pop_min = max(pop_min, population_min_extra)
    pop_max = population_max_extra if population_max_extra and population_max_extra > 0 else None
    if pop_max is not None and pop_max < pop_min:
        pop_max = pop_min
    pop_range = f"entre ~{pop_min:,} e ~{pop_max:,} habitantes" if pop_max else f"com pelo menos ~{pop_min:,} habitantes"
    notes.append(
        f"Porte {porte.lower()}: buscamos municípios {pop_range} "
        f"e ~{emp_min:,} empregos formais (proxy de mercado e mão de obra)."
    )
    notes.append(
        "Subtipo ajusta levemente os pesos; comércio semelhante compartilha os mesmos drivers territoriais."
    )

    name = f"{macro} · {subtipo} · {porte}"
    weights = _normalize_weights({k: v for k, v in w.items() if k in FEATURES_ML})

    return BusinessProfile(
        name=name,
        weights=weights,
        preferred_clusters=tuple(preferred),
        population_min=pop_min,
        population_max=pop_max,
        employed_min=emp_min,
        notes=notes,
    )


def filter_municipalities(
    df: pd.DataFrame,
    profile: BusinessProfile,
    regions: list[str] | None,
    states: list[str] | None,
) -> pd.DataFrame:
    out = df[df["complete_record_flag"] == 1].copy()
    out = out[out["population_estimated"] >= profile.population_min]
    if profile.population_max is not None:
        out = out[out["population_estimated"] <= profile.population_max]
    out = out[out["employed_total"] >= profile.employed_min]
    if regions:
        out = out[out["region"].isin(regions)]
    if states:
        out = out[out["state"].isin(states)]
    return out


def score_municipalities(df: pd.DataFrame, profile: BusinessProfile) -> pd.DataFrame:
    if df.empty:
        return df
    scored = df.copy()
    parts: list[pd.Series] = []
    for feat, weight in profile.weights.items():
        if weight <= 0 or feat not in scored.columns:
            continue
        col = scored[feat]
        lo, hi = col.min(), col.max()
        if hi <= lo:
            norm = pd.Series(0.5, index=scored.index)
        else:
            norm = (col - lo) / (hi - lo)
        parts.append(norm * weight)
    scored["_score_base"] = sum(parts) if parts else 0.0
    cluster_bonus = scored["cluster_id"].isin(profile.preferred_clusters).astype(float) * 0.08
    scored["score_compatibilidade"] = (scored["_score_base"] + cluster_bonus).clip(0, 1)
    scored["score_pct"] = (scored["score_compatibilidade"] * 100).round(1)
    return scored.sort_values("score_compatibilidade", ascending=False)


def explain_row(row: pd.Series, national: pd.Series, profile: BusinessProfile) -> list[str]:
    lines: list[str] = []
    cid = int(row["cluster_id"]) if pd.notna(row.get("cluster_id")) else -1
    from src.scoring.labels import cluster_label

    if cid in profile.preferred_clusters:
        lines.append(f"{cluster_label(cid)} costuma combinar com este perfil de negócio.")
    else:
        lines.append(f"{cluster_label(cid)} é menos típico para o perfil; o score penaliza levemente.")
    for feat in profile.weights:
        if feat not in row.index or feat not in national.index:
            continue
        val, med = row[feat], national[feat]
        if pd.isna(val) or pd.isna(med) or med == 0:
            continue
        delta = (val / med - 1) * 100
        if abs(delta) >= 12:
            label = FEATURE_LABELS.get(feat, feat)
            direction = "acima" if delta > 0 else "abaixo"
            lines.append(f"{label}: {abs(delta):.0f}% {direction} da mediana nacional.")
        if len(lines) >= 5:
            break
    return lines[:5]
