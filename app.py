"""
GES Dashboard — Graduate Employment Survey Explorer
"""

import streamlit as st
import pandas as pd

from src.etl import (
    load_master,
    get_all_degrees,
    get_all_universities,
    get_categories,
    filter_by_category,
    METRIC_LABELS,
    RATE_METRICS,
)
from src.charts import (
    line_chart,
    bar_chart,
    dashboard_overview,
    category_heatmap,
    metric_sparklines,
)

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="GES Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide sidebar entirely */
section[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* Background */
.stApp {
    background: #F5F7FA;
}

h1, h2, h3 { color: #111827; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent;
    border-bottom: 2px solid #E5E7EB;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px 8px 0 0;
    color: #6B7280;
    font-weight: 600;
    padding: 10px 22px;
    border: none;
    transition: color 0.15s;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #2563EB;
    background: #EFF6FF;
}
.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #2563EB !important;
    border-top: 2px solid #2563EB;
    margin-bottom: -2px;
}
.stTabs [data-baseweb="tab-panel"] {
    background: #FFFFFF;
    border-radius: 0 12px 12px 12px;
    padding: 24px 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04);
}
.stTabs [data-baseweb="tab-panel"] h1,
.stTabs [data-baseweb="tab-panel"] h2,
.stTabs [data-baseweb="tab-panel"] h3,
.stTabs [data-baseweb="tab-panel"] p,
.stTabs [data-baseweb="tab-panel"] label {
    color: #111827;
}

/* ── Metric cards ── */
.metric-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 18px 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 2px 8px rgba(0,0,0,0.04);
    min-height: 96px;
    transition: box-shadow 0.15s;
}
.metric-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.10); }
.metric-card .label {
    font-size: 11px;
    font-weight: 600;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.metric-card .value {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
    margin: 6px 0 0;
    letter-spacing: -0.5px;
}
.metric-card .delta {
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
}
.delta-up   { color: #059669; }
.delta-flat { color: #D97706; }
.delta-down { color: #DC2626; }
.metric-card.card-up   { border-left: 4px solid #10B981; }
.metric-card.card-flat { border-left: 4px solid #F59E0B; }
.metric-card.card-down { border-left: 4px solid #EF4444; }

/* ── Section headers ── */
.section-header {
    font-size: 17px;
    font-weight: 700;
    color: #111827;
    margin: 0 0 14px;
    padding-bottom: 10px;
    border-bottom: 2px solid #EEF0F4;
}

/* ── Dashboard title ── */
.dash-title {
    font-size: 26px;
    font-weight: 700;
    color: #111827;
    margin: 12px 0 4px;
    letter-spacing: -0.5px;
}
.dash-subtitle {
    font-size: 13px;
    color: #6B7280;
    margin-bottom: 20px;
    font-weight: 400;
}

/* ── Charts ── */
div[data-testid="stPlotlyChart"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ── Misc ── */
hr { border-color: #EEF0F4 !important; }

div[data-testid="stButton"] > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.15s;
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}
div[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 10px !important;
    background: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Data loading (cached)
# ─────────────────────────────────────────────
ETL_RULES_VERSION = "2024-06-fix-salary-gradient-v4"

@st.cache_data(show_spinner=False)
def get_data(_version: str = ETL_RULES_VERSION):
    return load_master()

df = get_data()
all_degrees      = get_all_degrees(df)
all_universities = get_all_universities(df)
all_metrics      = list(METRIC_LABELS.keys())
latest_year      = df["year"].max()

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def compute_kpi(data: pd.DataFrame, metric: str, year: int):
    cur       = data[data["year"] == year][metric].mean()
    prev_data = data[data["year"] == year - 1][metric]
    prev      = prev_data.mean() if not prev_data.empty else None
    return cur, prev


def render_kpi_card(col, lbl: str, metric: str, view_df: pd.DataFrame, year: int):
    cur, prev = compute_kpi(view_df, metric, year)
    is_r      = metric in RATE_METRICS

    if pd.isna(cur):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="label">{lbl}</div>'
                f'<div class="value">N/A</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        return

    val_str    = f"{cur*100:.1f}%" if is_r else f"${cur:,.0f}"
    delta_html = ""
    card_cls   = ""

    if prev is not None and not pd.isna(prev):
        delta    = cur - prev
        delta_str = f"{delta*100:+.1f}pp" if is_r else f"${delta:+,.0f}"
        is_flat  = (abs(delta) < 0.005) if is_r else (prev != 0 and abs(delta / prev) < 0.01)

        if is_flat:
            tier, arrow = "flat", "▬"
        elif delta > 0:
            tier, arrow = "up", "▲"
        else:
            tier, arrow = "down", "▼"

        card_cls   = f"card-{tier}"
        delta_html = f'<div class="delta delta-{tier}">{arrow} YoY {delta_str}</div>'

    with col:
        st.markdown(
            f'<div class="metric-card {card_cls}">'
            f'<div class="label">{lbl}</div>'
            f'<div class="value">{val_str}</div>'
            f'{delta_html}</div>',
            unsafe_allow_html=True,
        )


def polish_line_chart(fig, n_series: int):
    """Post-process a Plotly line chart for better readability with many series."""
    if n_series > 5:
        fig.update_traces(line=dict(width=1.5))
    fig.update_layout(
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="left",
            x=0,
            font=dict(size=10),
            traceorder="normal",
        ),
        margin=dict(b=120),
    )
    return fig

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
st.markdown(
    '<div class="dash-title">Graduate Employment Dashboard</div>',
    unsafe_allow_html=True,
)
years = sorted(df["year"].unique())
st.markdown(
    f'<div class="dash-subtitle">'
    f'Singapore GES data · NUS, NTU, SMU, SIT, SUTD &amp; SUSS · '
    f'{years[0]}–{years[-1]} · {len(df):,} records'
    f'</div>',
    unsafe_allow_html=True,
)

tab_overall, tab_heatmap, tab_compare = st.tabs(
    ["Overall Trend", "Degree Heatmap", "Compare Degrees"]
)

# ══════════════════════════════════════════════
# OVERALL TREND
# ══════════════════════════════════════════════
with tab_overall:

    # ── Filters ──────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])

    with col_f2:
        dash_metric = st.selectbox(
            "Metric",
            options=all_metrics,
            format_func=lambda m: METRIC_LABELS[m],
            key="dash_metric",
        )
    with col_f3:
        dash_year = st.select_slider(
            "Reference year",
            options=sorted(df["year"].unique()),
            value=latest_year,
            key="dash_year",
        )
    with col_f1:
        dash_mode = st.radio(
            "View mode",
            ["Overall", "By Category", "By University", "By Degree"],
            horizontal=True,
        )

    st.divider()

    # ── Build view_df ─────────────────────────
    is_rate = dash_metric in RATE_METRICS

    if dash_mode == "Overall":
        view_df = df

    elif dash_mode == "By Category":
        categories     = get_categories()
        dash_category  = col_f1.selectbox("Category", categories, key="dash_cat")
        view_df        = filter_by_category(df, dash_category)
        if view_df.empty:
            st.warning("No data found for this category.")
            st.stop()

    elif dash_mode == "By University":
        dash_university = col_f1.selectbox("University", all_universities, key="dash_university")
        view_df         = df[df["university"] == dash_university]
        if view_df.empty:
            st.warning("No data found for this university.")
            st.stop()

    else:  # By Degree
        dash_degree = col_f1.selectbox("Degree", all_degrees, key="dash_degrees")
        view_df     = df[df["degree"].str.lower() == dash_degree.lower()]
        if view_df.empty:
            st.warning("No data found.")
            st.stop()

    # ── KPI cards ────────────────────────────
    KPI_METRICS = [
        ("employment_rate_overall",  "Employment (Overall)"),
        ("employment_rate_ft_perm",  "Employment (FT Perm)"),
        ("gross_monthly_median",     "Gross Median Salary"),
        ("basic_monthly_median",     "Basic Median Salary"),
    ]
    kpi_cols = st.columns(4)
    for col, (metric, lbl) in zip(kpi_cols, KPI_METRICS):
        render_kpi_card(col, lbl, metric, view_df, dash_year)

    st.divider()

    # ── Trend chart + quick stats ─────────────
    chart_col, insight_col = st.columns([3, 1])

    with chart_col:
        st.markdown('<div class="section-header">Trend Over Time</div>', unsafe_allow_html=True)
        fig = dashboard_overview(view_df, dash_metric)
        st.plotly_chart(fig, use_container_width=True, key="dash_trend_chart")

    with insight_col:
        st.markdown('<div class="section-header">Quick Stats</div>', unsafe_allow_html=True)
        agg = view_df.groupby("year")[dash_metric].mean().dropna()
        if not agg.empty:
            peak_year  = agg.idxmax()
            peak_val   = agg.max()
            latest_val = agg.get(dash_year)
            mv  = peak_val * 100 if is_rate else peak_val
            fmt = f"{mv:.1f}%" if is_rate else f"${mv:,.0f}"
            st.metric("Peak Value", fmt, f"in {peak_year}")
            if latest_val is not None:
                lv = latest_val * 100 if is_rate else latest_val
                lf = f"{lv:.1f}%" if is_rate else f"${lv:,.0f}"
                st.metric(f"In {dash_year}", lf)
            st.metric("Years of Data", f"{agg.index.min()}–{agg.index.max()}")

    # ── Sparklines ───────────────────────────
    with st.expander("All Metrics at a Glance", expanded=False):
        sparks = metric_sparklines(view_df)
        cols   = st.columns(4)
        for i, (metric, spark_fig) in enumerate(sparks.items()):
            with cols[i % 4]:
                label   = METRIC_LABELS[metric]
                s_agg   = view_df.groupby("year")[metric].mean().dropna()
                if not s_agg.empty:
                    val   = s_agg.iloc[-1]
                    is_r  = metric in RATE_METRICS
                    v_str = f"{val*100:.1f}%" if is_r else f"${val:,.0f}"
                    st.markdown(f"**{label}**")
                    st.markdown(
                        f"<span style='font-size:18px;font-weight:700;'>{v_str}</span>",
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(spark_fig, use_container_width=True, key=f"spark_{metric}")

# ══════════════════════════════════════════════
# DEGREE HEATMAP
# ══════════════════════════════════════════════
with tab_heatmap:
    heat_col1, _ = st.columns([2, 2])
    with heat_col1:
        heatmap_metric = st.selectbox(
            "Heatmap metric",
            options=all_metrics,
            format_func=lambda m: METRIC_LABELS[m],
            key="heatmap_metric",
        )

    # Use the reference year from the Overall tab (falls back to latest_year)
    _ref_year = st.session_state.get("dash_year", latest_year)
    fig_heatmap = category_heatmap(df, heatmap_metric, year=_ref_year)
    st.plotly_chart(fig_heatmap, use_container_width=True, key="dash_heatmap_chart")

# ══════════════════════════════════════════════
# COMPARE DEGREES
# ══════════════════════════════════════════════
with tab_compare:

    # ── Restore from URL (one-time per session) ──
    if not st.session_state.get("_qp_applied", False):
        qp           = st.query_params
        degs_from_url = qp.get_all("cmp_deg") if "cmp_deg" in qp else []
        if degs_from_url:
            st.session_state["cmp_degrees"] = [d for d in degs_from_url if d in all_degrees]
        if qp.get("cmp_metric") in all_metrics:
            st.session_state["cmp_metric"] = qp["cmp_metric"]
        if "cmp_chart" in qp:
            st.session_state["cmp_chart_type"] = (
                "Bar (single year)" if qp["cmp_chart"] == "bar" else "Line (time series)"
            )
        if "cmp_yr" in qp:
            try:
                yr = int(qp["cmp_yr"])
                if yr in df["year"].unique():
                    st.session_state["cmp_year"] = yr
            except ValueError:
                pass
        st.session_state["_qp_applied"] = True

    # ── Top row ──────────────────────────────
    desc_col, reset_col = st.columns([5, 1])
    with desc_col:
        st.markdown("*Overlay multiple degrees and universities to compare trends side by side.*")
    with reset_col:
        if st.button("Reset filters", key="cmp_reset_btn", use_container_width=True):
            keys_to_clear = [
                k for k in st.session_state
                if k in ("cmp_chart_type", "cmp_metric", "cmp_year", "cmp_cat",
                         "cmp_degrees", "_cmp_last_loaded_cat")
                or k.startswith("cmp_uni_")
            ]
            for k in keys_to_clear:
                del st.session_state[k]
            st.query_params.clear()
            st.rerun()

    # ── Filters ──────────────────────────────
    f1, f2, f4 = st.columns([2, 2, 2])

    with f1:
        chart_type = st.radio(
            "Chart type",
            ["Line (time series)", "Bar (single year)"],
            horizontal=True,
            key="cmp_chart_type",
        )
    with f2:
        cmp_metric = st.selectbox(
            "Metric",
            options=all_metrics,
            format_func=lambda m: METRIC_LABELS[m],
            key="cmp_metric",
        )
    with f4:
        if "Bar" in chart_type:
            _yr_kw  = {} if "cmp_year" in st.session_state else {"value": latest_year}
            cmp_year = st.select_slider(
                "Year",
                options=sorted(df["year"].unique()),
                key="cmp_year",
                **_yr_kw,
            )

    # ── Median reference (bar only) ──────────
    cmp_show_median  = False
    cmp_median_level = "degree"
    if "Bar" in chart_type:
        med_col1, med_col2 = st.columns([1, 2])
        with med_col1:
            cmp_show_median = st.checkbox("Show median line", key="cmp_show_median")
        with med_col2:
            if cmp_show_median:
                cmp_median_level = st.radio(
                    "Median level",
                    ["degree", "category", "overall"],
                    format_func=lambda v: {
                        "degree":   "Within Degree",
                        "category": "Within Category",
                        "overall":  "Overall (all degrees)",
                    }[v],
                    horizontal=True,
                    key="cmp_median_level",
                    label_visibility="collapsed",
                )

    st.divider()

    # ── Category loader ───────────────────────
    cat_col, _ = st.columns([1, 3])
    with cat_col:
        st.markdown("### Or load by Category")
        cat_option = st.selectbox(
            "Load a category",
            ["— none —"] + get_categories(),
            key="cmp_cat",
            label_visibility="collapsed",
        )

    if cat_option != "— none —" and st.session_state.get("_cmp_last_loaded_cat") != cat_option:
        cat_df = filter_by_category(df, cat_option)
        st.session_state["cmp_degrees"]            = get_all_degrees(cat_df)
        st.session_state["_cmp_last_loaded_cat"]   = cat_option
        st.rerun()
    elif cat_option == "— none —":
        st.session_state["_cmp_last_loaded_cat"] = None

    # ── Degree selector ───────────────────────
    st.markdown("### Select Degrees to Compare")
    st.markdown("*Type to search — select multiple degrees to overlay them.*")

    cmp_degrees = st.multiselect(
        "Degrees",
        options=all_degrees,
        placeholder="Start typing a degree name…",
        key="cmp_degrees",
        label_visibility="collapsed",
    )

    if not cmp_degrees:
        st.info("Select one or more degrees above to generate a chart.")
    else:
        # Readability warning for line charts
        if "Line" in chart_type and len(cmp_degrees) > 8:
            st.warning(
                f"⚠️ {len(cmp_degrees)} degrees selected — charts with more than 8 lines "
                "can be hard to read. Consider narrowing your selection or switching to **Bar**."
            )

        # ── Per-degree university pickers ─────
        st.markdown("### Universities")
        st.markdown("*Leave blank to include all universities that offer the degree.*")

        degree_universities: dict[str, list[str]] = {}
        uni_cols = st.columns(min(len(cmp_degrees), 3))
        for i, deg in enumerate(cmp_degrees):
            deg_unis = sorted(
                df[df["degree"].str.lower() == deg.lower()]["university"].unique().tolist()
            )
            with uni_cols[i % len(uni_cols)]:
                chosen = st.multiselect(
                    deg,
                    options=deg_unis,
                    default=[],
                    placeholder="All universities",
                    key=f"cmp_uni_{deg}",
                )
                degree_universities[deg] = chosen

        st.divider()

        # ── Chart ────────────────────────────
        if "Line" in chart_type:
            cmp_fig = line_chart(
                df, cmp_degrees, cmp_metric,
                degree_universities=degree_universities,
            )
            # Improve readability
            n_series = sum(
                max(1, len(unis)) for unis in degree_universities.values()
            )
            cmp_fig = polish_line_chart(cmp_fig, n_series)
            st.plotly_chart(cmp_fig, use_container_width=True, key="cmp_line_chart")
        else:
            year_val = st.session_state.get("cmp_year", latest_year)
            cmp_fig  = bar_chart(
                df, cmp_degrees, cmp_metric,
                year=year_val,
                degree_universities=degree_universities,
                show_median=cmp_show_median,
                median_level=cmp_median_level,
            )
            st.plotly_chart(cmp_fig, use_container_width=True, key="cmp_bar_chart")

        # ── Raw data ─────────────────────────
        with st.expander("Raw Data", expanded=False):
            mask     = df["degree"].isin(cmp_degrees)
            table_df = df[mask].copy()

            keep_rows = pd.Series(True, index=table_df.index)
            for deg, unis in degree_universities.items():
                if unis:
                    deg_mask   = table_df["degree"].str.lower() == deg.lower()
                    keep_rows &= ~deg_mask | table_df["university"].isin(unis)
            table_df = table_df[keep_rows]

            for col in RATE_METRICS:
                if col in table_df.columns:
                    table_df[col] = table_df[col].apply(
                        lambda x: f"{x*100:.1f}%" if pd.notna(x) else ""
                    )

            st.dataframe(
                table_df.sort_values(["degree", "university", "year"]),
                use_container_width=True,
                hide_index=True,
            )
            csv = table_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                data=csv,
                file_name="ges_comparison.csv",
                mime="text/csv",
            )
