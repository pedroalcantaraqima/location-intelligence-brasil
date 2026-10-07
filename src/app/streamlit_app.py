"""Location Intelligence Brasil — pré-seleção territorial e comparação de municípios."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from src.scoring.data import load_municipalities, municipality_choices, national_medians
from src.scoring.labels import CLUSTER_SUMMARY, COMPARE_METRICS, FEATURE_LABELS, cluster_label
from src.scoring.profiles import (
    MACRO_OPTS,
    NATUREZA_OPTS,
    PORTE_OPTS,
    REGIAO_OPTS,
    SUBTIPOS,
    build_profile,
    explain_row,
    filter_municipalities,
    score_municipalities,
)

st.set_page_config(
    page_title="Location Intelligence Brasil",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #fafafa; }
    h1, h2, h3 { color: #1a1a1a; font-weight: 600; }
    .app-header { margin-bottom: 0.25rem; }
    .app-sub { color: #5c5c5c; font-size: 0.95rem; margin-bottom: 1.5rem; }
    .disclaimer {
        background: #f0f4f8; border-left: 3px solid #94a3b8;
        padding: 0.75rem 1rem; border-radius: 4px; font-size: 0.85rem; color: #475569;
        margin: 1rem 0;
    }
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<p class="app-header"><h1>Location Intelligence Brasil</h1></p>', unsafe_allow_html=True)
st.markdown(
    '<p class="app-sub">Pré-seleção de municípios com dados públicos do IBGE e segmentação territorial (clusters). '
    "Não substitui estudo de ponto comercial, concorrência ou viabilidade financeira.</p>",
    unsafe_allow_html=True,
)

df_all = load_municipalities()
national = national_medians(df_all)
ufs = sorted(df_all["state"].dropna().unique())

tab_perfil, tab_compare = st.tabs(["Perfil da empresa", "Comparar municípios"])

with tab_perfil:
    st.subheader("Defina o perfil pretendido")
    c1, c2 = st.columns(2)
    with c1:
        natureza = st.selectbox("1. Natureza", NATUREZA_OPTS)
        macro = st.selectbox("2. Setor principal", MACRO_OPTS)
        subtipo = st.selectbox("3. Tipo de negócio", SUBTIPOS[macro])
    with c2:
        porte = st.selectbox("4. Porte inicial pretendido", PORTE_OPTS)
        regioes = st.multiselect("5. Regiões (opcional)", REGIAO_OPTS)
        estados = st.multiselect("5. Estados (opcional)", ufs)
        pop_min_col, pop_max_col = st.columns(2)
        with pop_min_col:
            pop_extra = st.number_input(
                "Pop. mínima (opcional)",
                min_value=0,
                max_value=15_000_000,
                value=0,
                step=5_000,
                help="0 = só o mínimo do porte. Some ao filtro automático.",
            )
        with pop_max_col:
            pop_max_raw = st.text_input(
                "Pop. máxima (opcional)",
                value="",
                placeholder="Vazio = sem limite",
                help="Ex.: 500000. Deixe em branco para não limitar o tamanho máximo.",
            )

    top_n = st.slider("Quantidade de municípios no ranking", 10, 50, 20, 5)
    run = st.button("Calcular ranking", type="primary")

    if run:
        pop_max_parsed: int | None = None
        if pop_max_raw.strip():
            try:
                pop_max_parsed = int(pop_max_raw.replace(".", "").replace(",", "").strip())
                if pop_max_parsed <= 0:
                    st.error("População máxima deve ser um número positivo ou deixe o campo vazio.")
                    st.stop()
            except ValueError:
                st.error("População máxima inválida. Use apenas números ou deixe vazio.")
                st.stop()
        profile = build_profile(
            natureza, macro, subtipo, porte, regioes or None, estados or None,
            int(pop_extra), pop_max_parsed,
        )
        filtered = filter_municipalities(df_all, profile, regioes or None, estados or None)
        if filtered.empty:
            st.session_state.pop("perfil_ranking", None)
            st.warning(
                "Nenhum município passou nos filtros. Afrouxe região, porte ou faixa de população."
            )
        else:
            ranked = score_municipalities(filtered, profile)
            st.session_state["perfil_ranking"] = {
                "ranked": ranked,
                "profile": profile,
                "eligible": len(filtered),
            }

    ranking = st.session_state.get("perfil_ranking")
    if ranking:
        profile = ranking["profile"]
        ranked = ranking["ranked"]
        top = ranked.head(top_n)
        st.success(f"Perfil: **{profile.name}** — {ranking['eligible']:,} municípios elegíveis.")
        for note in profile.notes:
            st.caption(note)

        show = top.copy()
        show["cluster_id"] = show["cluster_id"].astype(int) + 1
        display_cols = [
            "municipality_name_ref",
            "state",
            "cluster_id",
            "score_pct",
            "population_estimated",
            "gdp_per_capita_estimated",
            "density_per_km2",
        ]
        table = show[display_cols].rename(
            columns={
                "municipality_name_ref": "Município",
                "state": "UF",
                "cluster_id": "Cluster (1–3)",
                "score_pct": "Compatibilidade (%)",
                "population_estimated": "População",
                "gdp_per_capita_estimated": "PIB per capita",
                "density_per_km2": "Densidade",
            }
        )
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.subheader("Detalhe do município selecionado")
        labels = [f"{r['municipality_name_ref']} — {r['state']}" for _, r in top.iterrows()]
        pick = st.selectbox("Município no ranking", labels, key="rank_pick")
        row = top.iloc[labels.index(pick)]
        cid = int(row["cluster_id"])
        st.markdown(f"**{cluster_label(cid)}** — {CLUSTER_SUMMARY.get(cid, '')}")
        for line in explain_row(row, national, profile):
            st.markdown(f"- {line}")

    st.markdown(
        '<div class="disclaimer">Os scores combinam indicadores municipais (pesos do perfil) '
        "e afinidade com clusters do modelo não supervisionado. Trata-se de apoio à decisão, não garantia de sucesso.</div>",
        unsafe_allow_html=True,
    )

with tab_compare:
    st.subheader("Explorar e comparar municípios")
    choices = municipality_choices(df_all)
    code_map = {label: code for label, code in choices}
    labels_only = [c[0] for c in choices]
    default_a = next((i for i, s in enumerate(labels_only) if s.startswith("São Paulo —")), 0)
    default_b = next((i for i, s in enumerate(labels_only) if s.startswith("Campinas —")), min(1, len(labels_only) - 1))

    col_a, col_b = st.columns(2)
    with col_a:
        label_a = st.selectbox("Município A", labels_only, index=default_a)
    with col_b:
        label_b = st.selectbox("Município B", labels_only, index=default_b)

    def row_for(code: int) -> pd.Series:
        return df_all.loc[df_all["municipality_code"] == code].iloc[0]

    ra = row_for(code_map[label_a])
    rb = row_for(code_map[label_b])

    for title, row in [(label_a, ra), (label_b, rb)]:
        cid = int(row["cluster_id"]) if pd.notna(row.get("cluster_id")) else None
        st.markdown(f"### {title}")
        if cid is not None:
            st.markdown(f"**{cluster_label(cid)}** — {CLUSTER_SUMMARY.get(cid, '')}")

    st.markdown("#### Indicadores lado a lado")
    rows = []
    for key in COMPARE_METRICS:
        if key not in ra.index:
            continue
        va, vb = ra[key], rb[key]
        med = national.get(key, float("nan"))
        label = FEATURE_LABELS.get(key, key)
        rows.append(
            {
                "Indicador": label,
                "A": va,
                "B": vb,
                "Mediana nacional": med,
            }
        )
    cmp_df = pd.DataFrame(rows)

    def fmt_num(x):
        if pd.isna(x):
            return "—"
        if abs(x) >= 1000:
            return f"{x:,.0f}".replace(",", ".")
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    view = cmp_df.copy()
    for col in ("A", "B", "Mediana nacional"):
        view[col] = view[col].map(fmt_num)
    st.dataframe(view, use_container_width=True, hide_index=True)

    st.markdown("#### Diferenças relevantes (A vs B)")
    for key in COMPARE_METRICS:
        if key not in ra.index:
            continue
        va, vb = float(ra[key]), float(rb[key])
        if vb == 0:
            continue
        delta = (va / vb - 1) * 100
        if abs(delta) >= 15:
            label = FEATURE_LABELS.get(key, key)
            more = "maior" if delta > 0 else "menor"
            st.markdown(f"- **{label}:** A é {abs(delta):.0f}% {more} que B.")

    st.markdown(
        '<div class="disclaimer">Comparação baseada na mesma base municipal integrada (IBGE). '
        "Clusters refletem o modelo de segmentação da Sprint 3.</div>",
        unsafe_allow_html=True,
    )
