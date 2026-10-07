from __future__ import annotations

from datetime import datetime, timezone
import html
import json
import os

import numpy as np
import pandas as pd

# Avoid a platform-specific core-detection warning in constrained environments.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

from src.utils.paths import DASHBOARDS, GOLD, OUTPUT_DATA, ROOT

INPUT = GOLD / "municipal_analytical_base.csv"
CLUSTERED = GOLD / "municipal_clustered_base.csv"
METRICS = OUTPUT_DATA / "sprint3_cluster_metrics.csv"
REPORT = DASHBOARDS / "sprint3_model_report.html"
SUMMARY = OUTPUT_DATA / "sprint3_model_summary.json"

FEATURES = {
    "gdp_per_capita_estimated": "capacidade econômica por habitante",
    "density_per_km2": "concentração territorial e urbana",
    "active_companies_per_1000_inhabitants": "dinamismo empresarial relativo",
    "employed_per_1000_inhabitants": "intensidade de emprego formal",
    "avg_monthly_salary_brl": "renda média do trabalho formal",
    "formal_employment_rate": "proporção de emprego assalariado",
}
LOG_FEATURES = set(FEATURES) - {"formal_employment_rate"}
COLORS = ["#0077b6", "#e76f51", "#2a9d8f", "#8338ec", "#f4a261", "#264653", "#d62828", "#588157"]


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float | str]]]:
    raw = df[list(FEATURES)].copy()
    complete = raw.notna().all(axis=1)
    used = raw.loc[complete].copy()
    transformations: dict[str, dict[str, float | str]] = {}
    for column in FEATURES:
        low, high = used[column].quantile([0.01, 0.99])
        used[column] = used[column].clip(lower=low, upper=high)
        transformation = "winsorização P1–P99"
        if column in LOG_FEATURES:
            used[column] = np.log1p(used[column])
            transformation += " + log1p"
        transformations[column] = {
            "tratamento": transformation,
            "p1": float(low),
            "p99": float(high),
        }
    scaled = pd.DataFrame(StandardScaler().fit_transform(used), index=used.index, columns=used.columns)
    return scaled, complete.to_frame("complete"), transformations


def evaluate_kmeans(scaled: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    rows: list[dict[str, float | int]] = []
    for k in range(3, 9):
        base = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(scaled)
        stability = [
            adjusted_rand_score(base, KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(scaled))
            for seed in (7, 21, 99)
        ]
        rows.append({
            "k": k,
            "silhouette": silhouette_score(scaled, base),
            "calinski_harabasz": calinski_harabasz_score(scaled, base),
            "davies_bouldin": davies_bouldin_score(scaled, base),
            "stability_ari": float(np.mean(stability)),
        })
    metrics = pd.DataFrame(rows)
    metrics["rank_silhouette"] = metrics["silhouette"].rank(ascending=False, method="min")
    metrics["rank_calinski"] = metrics["calinski_harabasz"].rank(ascending=False, method="min")
    metrics["rank_davies"] = metrics["davies_bouldin"].rank(ascending=True, method="min")
    metrics["rank_stability"] = metrics["stability_ari"].rank(ascending=False, method="min")
    metrics["rank_mean"] = metrics[["rank_silhouette", "rank_calinski", "rank_davies", "rank_stability"]].mean(axis=1)
    selected_k = int(metrics.sort_values(["rank_mean", "silhouette"], ascending=[True, False]).iloc[0]["k"])
    return metrics, selected_k


def profile_clusters(df: pd.DataFrame, used_index: pd.Index, labels: np.ndarray) -> pd.DataFrame:
    profiled = df.loc[used_index, ["municipality_code", "municipality_name_ref", "state", *FEATURES]].copy()
    profiled["cluster_id"] = labels
    medians = profiled.groupby("cluster_id")[list(FEATURES)].median().round(2)
    sizes = profiled.groupby("cluster_id").size().rename("municipalities")
    result = medians.join(sizes).reset_index()
    return profiled, result


def describe_profile(row: pd.Series, overall: pd.Series) -> str:
    highlights = []
    for col in FEATURES:
        delta = (row[col] / overall[col] - 1) * 100
        if abs(delta) >= 15:
            direction = "acima" if delta > 0 else "abaixo"
            highlights.append(f"{col} {abs(delta):.0f}% {direction} da mediana nacional")
    return "; ".join(highlights[:3]) if highlights else "perfil próximo às medianas nacionais nas variáveis selecionadas"


def table(frame: pd.DataFrame, max_rows: int = 100) -> str:
    view = frame.head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda value: f"{value:,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
    return view.to_html(index=False, border=0, classes="data-table", escape=True)


def scatter_svg(scores: pd.DataFrame, labels: np.ndarray, point_info: pd.DataFrame) -> str:
    width, height, pad = 860, 420, 45
    x, y = scores["PC1"], scores["PC2"]
    def scale(values: pd.Series, size: int) -> pd.Series:
        span = values.max() - values.min() or 1
        return pad + (values - values.min()) / span * (size - 2 * pad)
    xs, ys = scale(x, width), height - scale(y, height)
    circles = "".join(
        f'<circle class="data-point" cx="{cx:.1f}" cy="{cy:.1f}" r="2.8" fill="{COLORS[int(label) % len(COLORS)]}" fill-opacity="0.62" '
        f'data-city="{html.escape(str(info.municipality_name_ref), quote=True)}" '
        f'data-state="{html.escape(str(info.state), quote=True)}" data-cluster="{int(label)}" '
        f'data-pc1="{score_1:.3f}" data-pc2="{score_2:.3f}" tabindex="0">'
        f'<title>{html.escape(str(info.municipality_name_ref))} ({html.escape(str(info.state))}) · Cluster {int(label)} · PC1 {score_1:.3f} · PC2 {score_2:.3f}</title></circle>'
        for cx, cy, label, score_1, score_2, (_, info) in zip(xs, ys, labels, scores["PC1"], scores["PC2"], point_info.iterrows())
    )
    legend = "".join(f'<span><i style="background:{COLORS[k % len(COLORS)]}"></i>Cluster {k}</span>' for k in sorted(set(labels)))
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="PCA dos municípios por cluster"><line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#94a3b8"/><line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#94a3b8"/>{circles}<text x="{width/2}" y="{height-10}" text-anchor="middle">Componente principal 1</text><text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle">Componente principal 2</text></svg><div class="legend">{legend}</div><div id="pca-tooltip" class="pca-tooltip" role="status"></div>'


def build_html(metrics: pd.DataFrame, selected_k: int, profiles: pd.DataFrame, scores: pd.DataFrame, labels: np.ndarray, point_info: pd.DataFrame, transformations: dict[str, dict[str, float | str]], explained: list[float], generated: str, included: int, excluded: int) -> str:
    overall = profiles[list(FEATURES)].median()
    profile_copy = profiles.copy()
    profile_copy["interpretação relativa"] = profile_copy.apply(lambda row: describe_profile(row, overall), axis=1)
    transform_df = pd.DataFrame([{"variável": key, **value} for key, value in transformations.items()])
    metrics_view = metrics[["k", "silhouette", "calinski_harabasz", "davies_bouldin", "stability_ari", "rank_mean"]]
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Sprint 3 Modelo de Clusters</title><style>
body{{font-family:Inter,Arial,sans-serif;background:#f4f7fb;color:#1e293b;margin:0}}.wrap{{max-width:1280px;margin:auto;padding:32px}}header{{background:#102a43;color:#fff;padding:32px;border-radius:16px}}h1{{margin:0 0 8px}}h2{{color:#102a43;margin-top:0}}section{{background:#fff;border-radius:12px;padding:22px;margin-top:20px;overflow:auto}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:20px}}.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 8px #102a4314}}.label{{font-size:13px;color:#64748b}}.value{{font-size:26px;font-weight:700;color:#0b7285}}table{{border-collapse:collapse;width:100%;font-size:12px}}th{{background:#d9eaf2;color:#102a43;text-align:left}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;vertical-align:top}}tr:nth-child(even){{background:#f8fafc}}svg{{width:100%;height:auto;background:#fff}}.data-point{{cursor:pointer}}.data-point:hover,.data-point:focus{{stroke:#102a43;stroke-width:1.5;fill-opacity:1;outline:none}}.legend span{{display:inline-flex;align-items:center;margin:8px 14px 0 0;font-size:13px}}.legend i{{width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:5px}}.pca-legend{{background:#eef6f9;border-left:4px solid #0b7285;padding:14px 16px;margin:12px 0;line-height:1.6}}.pca-tooltip{{display:none;position:fixed;z-index:10;max-width:240px;background:#102a43;color:#fff;padding:10px 12px;border-radius:8px;font-size:13px;line-height:1.45;pointer-events:none;box-shadow:0 4px 12px #102a4366}}code{{background:#eef2f7;padding:2px 5px;border-radius:4px}}</style></head><body><div class="wrap">
<header><h1>Avaliação multivariada e agrupamentos municipais</h1><div>Sprint 3 · gerado em {html.escape(generated)}</div></header>
<div class="grid"><div class="card"><div class="label">Municípios incluídos</div><div class="value">{included:,}</div></div><div class="card"><div class="label">Excluídos por nulos</div><div class="value">{excluded:,}</div></div><div class="card"><div class="label">Clusters selecionados</div><div class="value">{selected_k}</div></div><div class="card"><div class="label">Variância PCA 2D</div><div class="value">{sum(explained):.1%}</div></div></div>
<section><h2>Decisão analítica</h2><p>Foram comparadas configurações de 3 a 8 clusters por coesão, separação, estabilidade entre sementes e interpretabilidade. O valor selecionado foi <strong>k={selected_k}</strong>. Os grupos descrevem perfis municipais semelhantes; não representam recomendação automática de abertura de negócio.</p></section>
<section><h2>Variáveis e tratamento</h2><p>Variáveis: {', '.join(f'<code>{html.escape(v)}</code>' for v in FEATURES)}.</p>{table(transform_df)}</section>
<section><h2>Comparação de configurações</h2><p>Silhouette e Calinski-Harabasz: quanto maior, melhor. Davies-Bouldin: quanto menor, melhor. Estabilidade: concordância média entre execuções com sementes diferentes.</p>{table(metrics_view)}</section>
<section><h2>Visualização PCA</h2><p>Os dois componentes explicam {explained[0]:.1%} e {explained[1]:.1%} da variância, respectivamente. O gráfico é diagnóstico e não substitui a avaliação das métricas.</p><div class="pca-legend"><strong>Componente Principal 1 (PC1) — eixo X:</strong> empresas por mil habitantes, empregos por mil habitantes, PIB per capita e salário médio.<br><strong>Componente Principal 2 (PC2) — eixo Y:</strong> taxa de formalização do emprego e densidade demográfica.<br>Os componentes são combinações matemáticas das variáveis padronizadas; o sentido positivo ou negativo dos eixos pode ser invertido sem alterar o modelo.</div><p><strong>Como interpretar os pontos:</strong> cada ponto representa um município e a cor indica o cluster. Municípios próximos têm perfis mais semelhantes. Passe o mouse sobre um ponto para ver nome, UF, cluster e coordenadas PC1/PC2.</p>{scatter_svg(scores, labels, point_info)}</section>
<section><h2>Perfis dos clusters</h2><p>Os valores são medianas das variáveis originais, para facilitar interpretação de negócio.</p>{table(profile_copy)}</section>
<section><h2>Limitações</h2><ul><li>Fontes utilizam períodos de referência distintos: PIB 2021, Censo 2022 e CEMPRE/População 2024.</li><li>Os dados são agregados por município e não incluem ponto comercial, concorrência ou faturamento.</li><li>Os clusters organizam perfis territoriais; a aderência a um segmento deve ser definida por critérios de negócio em etapa posterior.</li></ul></section>
</div><script>
const tooltip = document.getElementById('pca-tooltip');
document.querySelectorAll('.data-point').forEach((point) => {{
  const show = (event) => {{
    tooltip.innerHTML = `<strong>${{point.dataset.city}}</strong> (${{point.dataset.state}})<br>Cluster: ${{point.dataset.cluster}}<br>PC1: ${{point.dataset.pc1}}<br>PC2: ${{point.dataset.pc2}}`;
    tooltip.style.display = 'block';
    tooltip.style.left = `${{event.clientX + 14}}px`;
    tooltip.style.top = `${{event.clientY + 14}}px`;
  }};
  point.addEventListener('mouseenter', show);
  point.addEventListener('mousemove', show);
  point.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
  point.addEventListener('focus', (event) => show(event));
  point.addEventListener('blur', () => {{ tooltip.style.display = 'none'; }});
}});
</script></body></html>'''


def main() -> None:
    df = pd.read_csv(INPUT)
    scaled, complete, transformations = prepare_features(df)
    metrics, selected_k = evaluate_kmeans(scaled)
    labels = KMeans(n_clusters=selected_k, n_init=20, random_state=42).fit_predict(scaled)
    profiled, profiles = profile_clusters(df, scaled.index, labels)
    output = df.copy()
    output["cluster_id"] = pd.Series(labels, index=scaled.index, dtype="Int64")
    pca = PCA(n_components=2, random_state=42)
    scores = pd.DataFrame(pca.fit_transform(scaled), index=scaled.index, columns=["PC1", "PC2"])
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    DASHBOARDS.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA.mkdir(parents=True, exist_ok=True)
    output.to_csv(CLUSTERED, index=False)
    metrics.to_csv(METRICS, index=False)
    point_info = df.loc[scores.index, ["municipality_name_ref", "state"]]
    REPORT.write_text(build_html(metrics, selected_k, profiles, scores, labels, point_info, transformations, list(pca.explained_variance_ratio_), generated, len(scaled), int((~complete["complete"]).sum())), encoding="utf-8")
    summary = {"generated_at": generated, "input": str(INPUT.relative_to(ROOT)), "rows_included": len(scaled), "rows_excluded": int((~complete["complete"]).sum()), "features": FEATURES, "selected_k": selected_k, "pca_explained_variance_ratio": list(pca.explained_variance_ratio_), "metrics": metrics.to_dict(orient="records"), "transformations": transformations}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Clustered base: {CLUSTERED}")
    print(f"HTML report: {REPORT}")
    print(f"Included={len(scaled)} | excluded={int((~complete['complete']).sum())} | selected_k={selected_k}")


if __name__ == "__main__":
    main()
