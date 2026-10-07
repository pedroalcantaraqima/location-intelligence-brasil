from __future__ import annotations

from datetime import datetime, timezone
import html
import json

import pandas as pd

from src.utils.paths import DASHBOARDS, GOLD, OUTPUT_DATA

INPUT = GOLD / "municipal_gold_initial.csv"
OUTPUT = GOLD / "municipal_analytical_base.csv"
REPORT = DASHBOARDS / "sprint2_data_catalog.html"
SUMMARY = OUTPUT_DATA / "sprint2_summary.json"


INDICATORS = {
    "population_variation_pct": ("(population_estimated - census_population) / census_population * 100", "Variação entre população estimada e Censo 2022", "IBGE/SIDRA", "candidata"),
    "employed_per_1000_inhabitants": ("employed_total / population_estimated * 1000", "Empregados por mil habitantes", "IBGE/SIDRA + CEMPRE", "candidata"),
    "formal_employment_rate": ("employed_salaried / employed_total * 100", "Proporção de empregados assalariados", "CEMPRE", "candidata"),
    "local_units_per_company": ("local_units / active_companies", "Unidades locais por empresa ativa", "CEMPRE", "candidata"),
}


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator > 0))


def build_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["population_variation_pct"] = safe_divide(
        out["population_estimated"] - out["census_population"], out["census_population"]
    ) * 100
    out["employed_per_1000_inhabitants"] = safe_divide(
        out["employed_total"], out["population_estimated"]
    ) * 1000
    out["formal_employment_rate"] = safe_divide(
        out["employed_salaried"], out["employed_total"]
    ) * 100
    out["local_units_per_company"] = safe_divide(
        out["local_units"], out["active_companies"]
    )
    out["null_count"] = out.isna().sum(axis=1)
    out["complete_record_flag"] = (out["null_count"] == 0).astype(int)
    return out


def quality_checks(df: pd.DataFrame) -> list[dict[str, str]]:
    code = df["municipality_code"]
    numeric = df.select_dtypes(include="number")
    non_negative = [
        "population_estimated", "gdp_current_brl_thousand", "active_companies",
        "avg_monthly_salary_brl", "employed_salaried", "employed_total",
        "local_units", "wages_brl_thousand", "area_km2", "census_population",
        "density_per_km2", "gdp_per_capita_estimated",
        "active_companies_per_1000_inhabitants", "employed_per_1000_inhabitants",
        "formal_employment_rate", "local_units_per_company",
    ]
    invalid_negative = (df[non_negative] < 0).any().any()
    checks = [
        ("Chave municipal preenchida", str(not code.isna().any()), "PASS" if not code.isna().any() else "FAIL"),
        ("Chave municipal única", str(not code.duplicated().any()), "PASS" if not code.duplicated().any() else "FAIL"),
        ("Métricas não negativas", str(not invalid_negative), "PASS" if not invalid_negative else "FAIL"),
        ("Área territorial positiva", str((df["area_km2"].dropna() > 0).all()), "PASS" if (df["area_km2"].dropna() > 0).all() else "FAIL"),
        ("Pelo menos 99% dos registros completos", str(df["complete_record_flag"].mean() >= 0.99), "PASS" if df["complete_record_flag"].mean() >= 0.99 else "WARN"),
    ]
    return [{"check": a, "result": b, "status": c} for a, b, c in checks]


def catalog(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in df.columns:
        s = df[name]
        role = "identificador" if name == "municipality_code" else "contexto" if s.dtype == "object" else "indicador derivado" if name in INDICATORS else "indicador original"
        desc = INDICATORS.get(name, ("", name.replace("_", " ").capitalize(), "Gold Sprint 1", role))[1]
        source = INDICATORS.get(name, ("", "", "Gold Sprint 1", role))[2]
        rows.append({"variável": name, "descrição": desc, "tipo": str(s.dtype), "fonte": source, "nulos": int(s.isna().sum()), "cardinalidade": int(s.nunique(dropna=True)), "mínimo": s.min() if pd.api.types.is_numeric_dtype(s) else "—", "máximo": s.max() if pd.api.types.is_numeric_dtype(s) else "—", "papel": role})
    return pd.DataFrame(rows)


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def table(df: pd.DataFrame, max_rows: int = 100) -> str:
    view = df.head(max_rows).copy()
    for col in view.columns:
        view[col] = view[col].map(fmt)
    return view.to_html(index=False, classes="data-table", border=0, escape=True)


def build_html(df: pd.DataFrame, cat: pd.DataFrame, checks: list[dict[str, str]], corr: pd.DataFrame, generated: str) -> str:
    complete = int(df["complete_record_flag"].sum())
    status = "APTO PARA PRÉ-MODELAGEM" if all(c["status"] == "PASS" for c in checks) else "REVISAR QUALIDADE"
    nulls = df.isna().sum().sort_values(ascending=False).rename("nulos").reset_index().rename(columns={"index": "variável"})
    corr_view = corr.where((corr.abs() >= 0.80) & (corr.abs() < 1.0)).stack().reset_index()
    corr_view.columns = ["variável 1", "variável 2", "correlação"]
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Catálogo de Dados Sprint 2</title>
<style>body{{font-family:Inter,Arial,sans-serif;background:#f4f7fb;color:#1f2937;margin:0}}.wrap{{max-width:1280px;margin:0 auto;padding:32px}}header{{background:#102a43;color:white;padding:32px;border-radius:16px;margin-bottom:24px}}h1{{margin:0 0 8px}}h2{{color:#102a43;margin-top:32px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.card{{background:white;border-radius:12px;padding:18px;box-shadow:0 2px 8px #102a4314}}.value{{font-size:26px;font-weight:700;color:#0b7285}}.label{{font-size:13px;color:#64748b}}section{{background:white;border-radius:12px;padding:22px;margin:18px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th{{background:#d9eaf2;color:#102a43;text-align:left}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;vertical-align:top}}tr:nth-child(even){{background:#f8fafc}}.PASS{{color:#087f5b;font-weight:bold}}.WARN{{color:#b26a00;font-weight:bold}}.FAIL{{color:#c92a2a;font-weight:bold}}code{{background:#eef2f7;padding:2px 5px;border-radius:4px}}</style></head><body><div class="wrap">
<header><h1>Catálogo analítico e qualidade dos dados</h1><div>Sprint 2 · gerado em {html.escape(generated)}</div></header>
<div class="grid"><div class="card"><div class="label">Status</div><div class="value">{status}</div></div><div class="card"><div class="label">Municípios</div><div class="value">{len(df):,}</div></div><div class="card"><div class="label">Variáveis</div><div class="value">{len(df.columns)}</div></div><div class="card"><div class="label">Registros completos</div><div class="value">{complete:,}</div></div></div>
<section><h2>Objetivo</h2><p>Base municipal enriquecida com indicadores derivados, validações de qualidade e variáveis candidatas à análise multivariada e clusterização.</p><p><strong>Arquivo:</strong> <code>data/gold/municipal_analytical_base.csv</code></p></section>
<section><h2>Validações</h2>{table(pd.DataFrame(checks))}</section>
<section><h2>Catálogo de variáveis</h2>{table(cat, 200)}</section>
<section><h2>Nulos por variável</h2>{table(nulls)}</section>
<section><h2>Variáveis candidatas ao ML</h2>{table(pd.DataFrame([{"variável": n, "fórmula": v[0], "justificativa": v[1], "fonte": v[2]} for n, v in INDICATORS.items()]))}</section>
<section><h2>Correlações altas</h2><p>Pares com correlação absoluta igual ou superior a 0,80 devem ser revisados antes da modelagem.</p>{table(corr_view if not corr_view.empty else pd.DataFrame([{"resultado": "Nenhum par acima do limiar"}]))}</section>
</div></body></html>'''


def main() -> None:
    df = build_base(pd.read_csv(INPUT))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARDS.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    cat = catalog(df)
    checks = quality_checks(df)
    numeric = df.select_dtypes(include="number").drop(columns=["null_count", "complete_record_flag"], errors="ignore")
    corr = numeric.corr()
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    REPORT.write_text(build_html(df, cat, checks, corr, generated), encoding="utf-8")
    summary = {"generated_at": generated, "rows": len(df), "columns": len(df.columns), "complete_records": int(df["complete_record_flag"].sum()), "checks": checks, "candidate_variables": list(INDICATORS)}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Analytical base: {OUTPUT}")
    print(f"HTML report: {REPORT}")
    print(f"Rows={len(df)} | columns={len(df.columns)} | complete_records={int(df['complete_record_flag'].sum())}")
    print(f"Quality status: {'PASS' if all(c['status'] == 'PASS' for c in checks) else 'REVIEW'}")


if __name__ == "__main__":
    main()
