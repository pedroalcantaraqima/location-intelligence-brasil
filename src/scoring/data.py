"""Carregamento da base municipal para o app."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.utils.paths import GOLD


@st.cache_data(show_spinner=False)
def load_municipalities() -> pd.DataFrame:
    path = GOLD / "municipal_clustered_base.csv"
    if not path.exists():
        path = GOLD / "municipal_analytical_base.csv"
    df = pd.read_csv(path)
    if "cluster_id" not in df.columns:
        df["cluster_id"] = pd.NA
    return df


def municipality_choices(df: pd.DataFrame) -> list[tuple[str, int]]:
    opts = []
    for _, r in df.sort_values(["state", "municipality_name_ref"]).iterrows():
        label = f"{r['municipality_name_ref']} — {r['state']}"
        opts.append((label, int(r["municipality_code"])))
    return opts


def national_medians(df: pd.DataFrame) -> pd.Series:
    complete = df[df.get("complete_record_flag", 1) == 1]
    return complete.median(numeric_only=True)
