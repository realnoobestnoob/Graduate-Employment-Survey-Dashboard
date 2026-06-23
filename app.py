"""
GES Dashboard — Graduate Employment Survey Explorer
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.etl import (
    load_master,
    ingest_new_file,
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
from src.report import generate_dashboard_pdf

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="GES Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Background image (base64-embedded so no separate static-file serving
# config is needed)
# ─────────────────────────────────────────────
import base64
from pathlib import Path


@st.cache_data(show_spinner=False)
def _load_bg_b64() -> str:
    bg_path = Path(__file__).parent / "graduation_bg.png"
    if not bg_path.exists():
        return ""
    return base64.b64encode(bg_path.read_bytes()).decode()


_BG_B64 = _load_bg_b64()

# ─────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}

/* Background image with dark overlay for readability */
.stApp {{
    background:
        linear-gradient(rgba(15,23,42,0.72), rgba(15,23,42,0.78)),
        url("data:image/png;base64,{_BG_B64}");
    background-size: cover;
    background-position: center top;
    background-attachment: fixed;
}}

/* Page title needs to read on the dark photo bg; bordered containers below
   sit on a white background so their own text stays the default dark color. */
h1, h2, h3 {{
    color: #F9FAFB;
}}
.st-key-section_overall_trend h1, .st-key-section_overall_trend h2, .st-key-section_overall_trend h3,
.st-key-section_heatmap h1, .st-key-section_heatmap h2, .st-key-section_heatmap h3,
.st-key-section_compare_degrees h1, .st-key-section_compare_degrees h2, .st-key-section_compare_degrees h3 {{
    color: #111827;
}}

/* Tabs — segments overall trend / heatmap / compare into clearly separated
   views over the background photo. Tab panel content gets a white backing
   so text and charts stay readable against the photo wallpaper. */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    background: rgba(255,255,255,0.85);
    border-radius: 10px 10px 0 0;
    color: #111827;
    font-weight: 600;
    padding: 10px 20px;
}}
.stTabs [aria-selected="true"] {{
    background: rgba(255,255,255,0.97) !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background: rgba(255,255,255,0.97);
    border-radius: 0 12px 12px 12px;
    padding: 20px 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}}
.stTabs [data-baseweb="tab-panel"] h1,
.stTabs [data-baseweb="tab-panel"] h2,
.stTabs [data-baseweb="tab-panel"] h3,
.stTabs [data-baseweb="tab-panel"] p,
.stTabs [data-baseweb="tab-panel"] label {{
    color: #111827;
}}

/* Metric cards */
.metric-card {{
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    min-height: 92px;
}}
.metric-card .label {{
    font-size: 11px;
    font-weight: 600;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.metric-card .value {{
    font-size: 26px;
    font-weight: 700;
    color: #111827;
    margin: 4px 0 0;
}}
.metric-card .delta {{
    font-size: 12px;
    margin-top: 2px;
}}
.delta-up {{ color: #047857; }}
.delta-flat {{ color: #B45309; }}
.delta-down {{ color: #B91C1C; }}

.metric-card.card-up {{ border-left: 4px solid #10B981; }}
.metric-card.card-flat {{ border-left: 4px solid #F59E0B; }}
.metric-card.card-down {{ border-left: 4px solid #EF4444; }}

/* Section headers */
.section-header {{
    font-size: 18px;
    font-weight: 700;
    color: #111827;
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #F3F4F6;
}}

/* Dashboard title banner — sits directly on the photo bg */
.dash-title {{
    font-size: 30px;
    font-weight: 700;
    color: #FFFFFF;
    text-shadow: 0 2px 8px rgba(0,0,0,0.5);
    margin: 8px 0 4px;
}}
.dash-subtitle {{
    font-size: 14px;
    color: #E2E8F0;
    text-shadow: 0 1px 4px rgba(0,0,0,0.4);
    margin-bottom: 8px;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: #F9FAFB;
    border-right: 1px solid #E5E7EB;
}}
section[data-testid="stSidebar"] * {{
    color: #111827 !important;
}}

/* Upload area */
.upload-hint {{
    font-size: 13px;
    color: #9CA3AF;
    margin-top: 4px;
}}

div[data-testid="stPlotlyChart"] {{
    border-radius: 10px;
    overflow: hidden;
}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Data loading (cached)
# ─────────────────────────────────────────────
# Bump this whenever src/etl.py's canonicalisation/categorisation rules
# change, so Streamlit's cache can never silently serve data computed under
# an older rule set after the file has been replaced.
ETL_RULES_VERSION = "2024-06-fix-salary-gradient-v4"


@st.cache_data(show_spinner=False)
def get_data(_version: str = ETL_RULES_VERSION):
    return load_master()


def refresh_data():
    st.cache_data.clear()


# ─────────────────────────────────────────────
# Load data (must be before sidebar so PDF button can access df/overall_vmids)
# ─────────────────────────────────────────────
df = get_data()
all_degrees = get_all_degrees(df)
all_universities = get_all_universities(df)
all_metrics = list(METRIC_LABELS.keys())
latest_year = df["year"].max()

_latest_df = df[df["year"] == latest_year]
_rate_set = set(RATE_METRICS)
overall_vmids: dict[str, float] = {}
for _m in all_metrics:
    _v = _latest_df[_m].mean()
    if pd.notna(_v):
        overall_vmids[_m] = float(_v * 100) if _m in _rate_set else float(_v)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## GES Dashboard")
    st.markdown("*Graduate Employment Survey Explorer*")
    st.divider()

    st.markdown("### Upload New Data")

    if "is_owner" not in st.session_state:
        st.session_state["is_owner"] = False

    if not st.session_state["is_owner"]:
        pw = st.text_input("Owner password", type="password", key="owner_pw_input")
        if st.button("Unlock upload"):
            if pw and pw == st.secrets.get("owner_password", ""):
                st.session_state["is_owner"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    if st.session_state["is_owner"]:
        uploaded = st.file_uploader(
            "Upload GES CSV",
            type=["csv"],
            help="Upload a new GES CSV to merge into the dataset.",
        )
        if uploaded:
            with st.spinner("Processing..."):
                try:
                    df_new, added = ingest_new_file(uploaded)
                    refresh_data()
                    st.success(f"Added {added} new row(s).")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown('<p class="upload-hint">Format: year, university, school, degree, metrics…</p>', unsafe_allow_html=True)
    st.divider()

    years = sorted(df["year"].unique())
    st.markdown(f"**Dataset:** {len(df):,} records · {years[0]}–{years[-1]}")
    st.markdown(f"**Universities:** {', '.join(sorted(df['university'].unique()))}")

    st.divider()
    st.markdown("### Export")
    if st.button("Generate PDF Report", key="pdf_gen_btn", use_container_width=True):
        inputs = st.session_state.get("_pdf_inputs")
        if inputs is None:
            st.warning("Load the Overall Trend tab first.")
        else:
            with st.spinner("Generating PDF..."):
                pdf_heatmap_fig = category_heatmap(
                    df, inputs["metric_key"],
                    year=inputs["year"],
                    vmid=overall_vmids.get(inputs["metric_key"]),
                )
                pdf_bytes = generate_dashboard_pdf(
                    mode_label=inputs["mode_label"],
                    metric_label=inputs["metric_label"],
                    year=inputs["year"],
                    kpi_rows=inputs["kpi_rows"],
                    trend_fig=inputs["trend_fig"],
                    heatmap_fig=pdf_heatmap_fig,
                    compare_fig=st.session_state.get("_cmp_fig"),
                    compare_label=st.session_state.get("_cmp_degrees_label", ""),
                )
            st.session_state["_pdf_bytes"] = pdf_bytes
            st.session_state["_pdf_ready"] = True

    if st.session_state.get("_pdf_ready"):
        st.download_button(
            "⬇ Download PDF",
            data=st.session_state["_pdf_bytes"],
            file_name=f"ges_dashboard_{st.session_state['_pdf_inputs']['year']}.pdf",
            mime="application/pdf",
            key="pdf_download_btn",
        )


# ══════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════
st.markdown('<div class="dash-title">Graduate Employment Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="dash-subtitle">Explore employment outcomes across NUS, NTU, SMU, SIT, SUTD, and SUSS</div>', unsafe_allow_html=True)

tab_overall, tab_heatmap, tab_compare = st.tabs(["Overall Trend", "Degree Heatmap", "Compare Degrees"])

with tab_overall:

    # ── Filters ──────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])

    with col_f1:
        dash_mode = st.radio(
            "View mode",
            ["Overall", "By Category", "By Degree"],
            horizontal=True,
        )

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

    st.divider()

    # ── KPI cards ────────────────────────────
    is_rate = dash_metric in RATE_METRICS


    def compute_kpi(data, metric, year):
        cur = data[data["year"] == year][metric].mean()
        prev_year = year - 1
        prev_data = data[data["year"] == prev_year][metric]
        prev = prev_data.mean() if not prev_data.empty else None
        return cur, prev


    if dash_mode == "Overall":
        view_df = df
    elif dash_mode == "By Category":
        categories = get_categories()
        dash_category = col_f1.selectbox("Category", categories, key="dash_cat")
        view_df = filter_by_category(df, dash_category)
        if view_df.empty:
            st.warning("No data found for this category.")
            st.stop()
    else:
        dash_degrees = col_f1.multiselect(
            "Degree(s) — select multiple to compare",
            all_degrees,
            default=all_degrees[:1],
            key="dash_degrees",
            placeholder="Start typing a degree name…",
        )
        if not dash_degrees:
            st.info("Select one or more degrees to view the dashboard.")
            st.stop()
        view_df = df[df["degree"].str.lower().isin([d.lower() for d in dash_degrees])]
        if view_df.empty:
            st.warning("No data found.")
            st.stop()

    # KPI row
    kpi_cols = st.columns(4)
    kpi_metrics = [
        "employment_rate_overall",
        "employment_rate_ft_perm",
        "gross_monthly_median",
        "basic_monthly_median",
    ]
    kpi_labels = ["Employment (Overall)", "Employment (FT Perm)", "Gross Median Salary", "Basic Median Salary"]
    pdf_kpi_rows = []  # collected for the "Download Dashboard PDF" button below

    for col, metric, lbl in zip(kpi_cols, kpi_metrics, kpi_labels):
        cur, prev = compute_kpi(view_df, metric, dash_year)
        if pd.isna(cur):
            with col:
                st.markdown(
                    f'<div class="metric-card"><div class="label">{lbl}</div>'
                    f'<div class="value">N/A</div></div>',
                    unsafe_allow_html=True,
                )
            pdf_kpi_rows.append({"label": lbl, "value": "N/A", "delta": "—"})
            continue

        is_r = metric in RATE_METRICS
        val_str = f"{cur*100:.1f}%" if is_r else f"${cur:,.0f}"

        delta_html = ""
        card_cls = ""
        pdf_delta_str = "—"
        if prev is not None and not pd.isna(prev):
            delta = cur - prev
            delta_str = f"{delta*100:+.1f}pp" if is_r else f"${delta:+,.0f}"
            pdf_delta_str = f"YoY {delta_str}"

            # "Flat" band: a rate change under 0.5pp, or a dollar change under
            # 1% of the previous value, counts as little-to-no change (yellow)
            # rather than a hard up/down (green/red).
            is_flat = (abs(delta) < 0.005) if is_r else (prev != 0 and abs(delta / prev) < 0.01)

            if is_flat:
                tier, arrow = "flat", "▬"
            elif delta > 0:
                tier, arrow = "up", "▲"
            else:
                tier, arrow = "down", "▼"

            card_cls = f"card-{tier}"
            delta_html = f'<div class="delta delta-{tier}">{arrow} YoY {delta_str}</div>'

        pdf_kpi_rows.append({"label": lbl, "value": val_str, "delta": pdf_delta_str})

        with col:
            st.markdown(
                f'<div class="metric-card {card_cls}"><div class="label">{lbl}</div>'
                f'<div class="value">{val_str}</div>{delta_html}</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Main chart ───────────────────────────
    chart_col, insight_col = st.columns([3, 1])

    with chart_col:
        st.markdown('<div class="section-header">Trend Over Time</div>', unsafe_allow_html=True)
        if dash_mode == "By Degree":
            fig = line_chart(view_df, dash_degrees, dash_metric)
        else:
            fig = dashboard_overview(view_df, dash_metric)
        st.plotly_chart(fig, use_container_width=True, key="dash_trend_chart")

    with insight_col:
        st.markdown('<div class="section-header">Quick Stats</div>', unsafe_allow_html=True)
        agg = view_df.groupby("year")[dash_metric].mean().dropna()
        if not agg.empty:
            peak_year = agg.idxmax()
            peak_val = agg.max()
            latest_val = agg.get(dash_year, None)

            mv = peak_val * 100 if is_rate else peak_val
            fmt = f"{mv:.1f}%" if is_rate else f"${mv:,.0f}"
            st.metric("Peak Value", fmt, f"in {peak_year}")

            if latest_val is not None:
                lv = latest_val * 100 if is_rate else latest_val
                lf = f"{lv:.1f}%" if is_rate else f"${lv:,.0f}"
                st.metric(f"In {dash_year}", lf)

            st.metric("Years of Data", f"{agg.index.min()}–{agg.index.max()}")

    # Persist everything the sidebar PDF button needs
    st.session_state["_pdf_inputs"] = dict(
        mode_label=dash_mode,
        metric_key=dash_metric,
        metric_label=METRIC_LABELS[dash_metric],
        year=dash_year,
        kpi_rows=pdf_kpi_rows,
        trend_fig=fig,
    )

    # ── All metrics sparklines ────────────────
    with st.expander("All Metrics at a Glance", expanded=False):
        sparks = metric_sparklines(view_df)
        cols = st.columns(4)
        for i, (metric, fig) in enumerate(sparks.items()):
            with cols[i % 4]:
                label = METRIC_LABELS[metric]
                agg = view_df.groupby("year")[metric].mean().dropna()
                if not agg.empty:
                    val = agg.iloc[-1]
                    is_r = metric in RATE_METRICS
                    val_str = f"{val*100:.1f}%" if is_r else f"${val:,.0f}"
                    st.markdown(f"**{label}**")
                    st.markdown(f"<span style='font-size:18px;font-weight:700;'>{val_str}</span>", unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True, key=f"spark_{metric}")


# ══════════════════════════════════════════════
# HEATMAP SECTION
# ══════════════════════════════════════════════
with tab_heatmap:

    heat_col1, heat_col2 = st.columns([2, 2])
    with heat_col1:
        heatmap_metric = st.selectbox(
            "Heatmap metric",
            options=all_metrics,
            format_func=lambda m: METRIC_LABELS[m],
            key="heatmap_metric",
        )

    fig_heatmap = category_heatmap(df, heatmap_metric, year=dash_year)
    st.plotly_chart(fig_heatmap, use_container_width=True, key="dash_heatmap_chart")



# ══════════════════════════════════════════════
# COMPARE DEGREES (merged from former Comparison tab)
# ══════════════════════════════════════════════
with tab_compare:
    # ── Restore a bookmarked/shared comparison from the URL (one-time per
    # browser session, so it doesn't keep overriding later user changes) ──
    if not st.session_state.get("_qp_applied", False):
        qp = st.query_params
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

    top_row1, top_row2, top_row3 = st.columns([3, 1, 1])
    with top_row1:
        st.markdown("*Overlay multiple degrees and universities to compare trends side by side.*")
    with top_row2:
        if st.button("Save comparison", key="cmp_save_btn", use_container_width=True):
            saved_degrees = st.session_state.get("cmp_degrees", [])
            if not saved_degrees:
                st.warning("Select at least one degree before saving.")
            else:
                st.query_params["cmp_deg"] = saved_degrees
                st.query_params["cmp_metric"] = st.session_state.get("cmp_metric", all_metrics[0])
                st.query_params["cmp_chart"] = (
                    "bar" if "Bar" in st.session_state.get("cmp_chart_type", "Line (time series)") else "line"
                )
                st.query_params["cmp_yr"] = str(st.session_state.get("cmp_year", latest_year))
                st.success("Saved — copy the URL from your browser's address bar to bookmark or share this exact comparison.")
    with top_row3:
        if st.button("Reset all filters", key="cmp_reset_btn", use_container_width=True):
            # Clear every Compare Degrees widget key, including the dynamic
            # per-degree university pickers (cmp_uni_<degree>), so the tab
            # returns to its initial empty state.
            keys_to_clear = [
                k for k in st.session_state.keys()
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
            _year_kwargs = {} if "cmp_year" in st.session_state else {"value": latest_year}
            cmp_year = st.select_slider(
                "Year",
                options=sorted(df["year"].unique()),
                key="cmp_year",
                **_year_kwargs,
            )

    # ── Median reference line (bar chart only) ──
    cmp_show_median = False
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
                    format_func=lambda v: {"degree": "Within Degree (all universities)",
                                            "category": "Within Category",
                                            "overall": "Overall (all degrees)"}[v],
                    horizontal=True,
                    key="cmp_median_level",
                    label_visibility="collapsed",
                )

    st.divider()

    # ── Category loader (must run BEFORE the multiselect widget) ──
    # We set st.session_state["cmp_degrees"] directly (the widget's own key)
    # before the multiselect is instantiated below -- this is the officially
    # supported way to pre-set a widget's value. We deliberately do NOT pass
    # a `default=` to the multiselect at all, so there is no ambiguity about
    # default vs. session-state precedence across reruns (which previously
    # caused the chart to appear to reset/go blank when the user changed the
    # metric or chart type right after loading a category).
    cat_col, _ = st.columns([1, 3])
    with cat_col:
        st.markdown("### Or by Category")
        cat_option = st.selectbox(
            "Load a category",
            ["— none —"] + get_categories(),
            key="cmp_cat",
            label_visibility="collapsed",
        )
        if cat_option != "— none —" and st.session_state.get("_cmp_last_loaded_cat") != cat_option:
            cat_df = filter_by_category(df, cat_option)
            cat_degrees = get_all_degrees(cat_df)
            st.session_state["cmp_degrees"] = cat_degrees
            st.session_state["_cmp_last_loaded_cat"] = cat_option
            st.rerun()
        elif cat_option == "— none —":
            st.session_state["_cmp_last_loaded_cat"] = None

    # ── Degree selector with autocomplete ────
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
        # ── Per-degree university pickers ────────
        st.markdown("### Universities")
        st.markdown("*Pick which universities to include for each degree (leave blank for all that offer it).*")

        degree_universities: dict[str, list[str]] = {}
        uni_cols = st.columns(min(len(cmp_degrees), 3))
        for i, deg in enumerate(cmp_degrees):
            deg_unis = sorted(df[df["degree"].str.lower() == deg.lower()]["university"].unique().tolist())
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

        # ── Render chart ─────────────────────────
        if "Line" in chart_type:
            cmp_fig = line_chart(df, cmp_degrees, cmp_metric, degree_universities=degree_universities)
            st.plotly_chart(cmp_fig, use_container_width=True, key="cmp_line_chart")
        else:
            year_val = st.session_state.get("cmp_year", latest_year)
            cmp_fig = bar_chart(
                df, cmp_degrees, cmp_metric, year=year_val,
                degree_universities=degree_universities,
                show_median=cmp_show_median,
                median_level=cmp_median_level,
            )
            st.plotly_chart(cmp_fig, use_container_width=True, key="cmp_bar_chart")

        # ── Data table ───────────────────────────
        with st.expander("Raw Data", expanded=False):
            mask = df["degree"].isin(cmp_degrees)
            table_df = df[mask].copy()

            # Apply per-degree university filters
            keep_rows = pd.Series(True, index=table_df.index)
            for deg, unis in degree_universities.items():
                if unis:
                    deg_mask = table_df["degree"].str.lower() == deg.lower()
                    keep_rows &= ~deg_mask | table_df["university"].isin(unis)
            table_df = table_df[keep_rows]

            # Format rates as percentages
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

