"""
Chart factory for GES dashboard — wraps Plotly Express/Graph Objects.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from src.etl import METRIC_LABELS, RATE_METRICS

PALETTE = px.colors.qualitative.Set2
UNI_COLORS = {
    "NUS": "#003D7C",
    "NTU": "#B22222",
    "SMU": "#1F5C99",
    "SIT": "#2E7D32",
    "SUTD": "#6A1B9A",
    "SUSS": "#E65100",
}

CHART_THEME = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=13, color="#374151"),
)

# Fixed gradient midpoints (yellow point) per metric, so the green-yellow-red
# color scale is consistent across charts/years instead of re-centering on
# whatever the current data's min/max midpoint happens to be.
# Rate metrics are stored 0-1 internally but converted to 0-100 scale before
# plotting in both bar_chart() and category_heatmap(), so these are in
# "percent" units (0-100), matching dollar units for salary metrics.
_GRADIENT_MID_BY_METRIC: dict[str, float] = {
    "employment_rate_overall": 82.5,
    "employment_rate_ft_perm": 70.0,
}
_SALARY_GRADIENT_MID = 4250


def _gradient_mid(metric: str) -> float:
    return _GRADIENT_MID_BY_METRIC.get(metric, _SALARY_GRADIENT_MID)


def _make_colorscale(metric: str, cmin: float, cmax: float, vmid: float) -> list:
    """Skewed 5-stop colorscale placing yellow exactly at vmid within [cmin, cmax]."""
    span = cmax - cmin
    if span <= 0:
        return [[0.0, "#FDE047"], [1.0, "#FDE047"]]
    mid_pos = max(0.05, min(0.95, (vmid - cmin) / span))
    lo_pos  = mid_pos / 2
    hi_pos  = mid_pos + (1 - mid_pos) / 2
    return [
        [0.0,     "#B91C1C"],
        [lo_pos,  "#EF4444"],
        [mid_pos, "#FDE047"],
        [hi_pos,  "#4ADE80"],
        [1.0,     "#15803D"],
    ]

DEFAULT_LEGEND = dict(
    bgcolor="rgba(255,255,255,0.9)",
    bordercolor="#E5E7EB",
    borderwidth=1,
    font=dict(size=12),
)


def _y_range(series: pd.Series, is_rate: bool, pad_frac: float = 0.10):
    """
    Return a tight [min, max] y-axis range with a small padding.
    For rates, never goes below 0; allows a little headroom above 100 so
    lines/markers that hit the 100% ceiling don't render flush against the
    plot's top edge (which looked clipped/overflowing).
    """
    vals = series.dropna()
    if vals.empty:
        return None
    lo, hi = vals.min(), vals.max()
    span = max(hi - lo, 1e-6)
    if is_rate:
        # Always keep at least a few points of breathing room, even when the
        # data range is tiny or sits right at the 100% ceiling.
        pad = max(span * pad_frac, 3)
        y_min = max(lo - pad, 0)
        y_max = min(hi + pad, 105)
    else:
        pad = span * pad_frac
        y_min = lo - pad
        y_max = hi + pad
    return [round(y_min, 2), round(y_max, 2)]


def _fmt_metric(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ").title())


def _pct(val):
    """Format a rate value as percentage string."""
    return f"{val*100:.1f}%"


def line_chart(df: pd.DataFrame, degrees: list[str], metric: str,
               universities: list[str] = None,
               degree_universities: dict[str, list[str]] = None) -> go.Figure:
    """
    Time-series line chart. One line per (degree × university) combination.
    degrees: list of degree strings to overlay
    universities: global university filter applied to all degrees (None = all)
    degree_universities: optional per-degree override, e.g. {"Law": ["NUS", "SMU"]}.
        If a degree has an entry here (even empty/None meaning "all"), it takes
        precedence over the global `universities` filter for that degree.
    """
    fig = go.Figure()
    label = _fmt_metric(metric)
    is_rate = metric in RATE_METRICS
    degree_universities = degree_universities or {}

    color_idx = 0
    for deg in degrees:
        mask = df["degree"].str.lower() == deg.lower()
        subset = df[mask]

        # Per-degree university filter takes precedence over the global one
        if deg in degree_universities and degree_universities[deg]:
            subset = subset[subset["university"].isin(degree_universities[deg])]
        elif universities:
            subset = subset[subset["university"].isin(universities)]

        for uni in sorted(subset["university"].unique()):
            uni_data = subset[subset["university"] == uni].groupby("year")[metric].mean().reset_index()
            uni_data = uni_data.dropna(subset=[metric])
            if uni_data.empty:
                continue

            color = UNI_COLORS.get(uni, PALETTE[color_idx % len(PALETTE)])
            dash = "solid" if len(degrees) == 1 else ["solid", "dash", "dot", "dashdot"][color_idx % 4]
            line_name = f"{deg} — {uni}" if len(degrees) > 1 else uni

            y_vals = uni_data[metric] * 100 if is_rate else uni_data[metric]
            hover = [_pct(v / 100) if is_rate else f"${v:,.0f}" for v in y_vals]

            fig.add_trace(go.Scatter(
                x=uni_data["year"],
                y=y_vals,
                mode="lines+markers",
                name=line_name,
                line=dict(color=color, width=2.5, dash=dash),
                marker=dict(size=7),
                hovertemplate=f"<b>{line_name}</b><br>Year: %{{x}}<br>{label}: %{{customdata}}<extra></extra>",
                customdata=hover,
            ))
            color_idx += 1

    title = degrees[0] if len(degrees) == 1 else f"{len(degrees)} Degrees Compared"
    y_title = f"{label} (%)" if is_rate else label

    # Tight y-axis range
    all_y = [v for trace in fig.data for v in trace.y if v is not None]
    y_rng = _y_range(pd.Series(all_y), is_rate) if all_y else None

    fig.update_layout(
        **CHART_THEME,
        title=dict(text=title, font=dict(size=16, color="#111827")),
        xaxis=dict(title="Year", tickformat="d", gridcolor="#F3F4F6"),
        yaxis=dict(
            title=y_title,
            gridcolor="#F3F4F6",
            range=y_rng,
            ticksuffix="%" if is_rate else "",
        ),
        hovermode="x unified",
        legend=dict(
            orientation="v",
            yanchor="top", y=1.0,
            xanchor="left", x=1.01,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E5E7EB",
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=70, r=200, t=60, b=80),
    )
    return fig


def bar_chart(df: pd.DataFrame, degrees: list[str], metric: str,
              universities: list[str] = None, year: int = None,
              degree_universities: dict[str, list[str]] = None,
              show_median: bool = False, median_level: str = "degree",
              vmid: float = None) -> go.Figure:
    """
    Bar chart comparing degrees/universities for a given year (defaults to latest).
    Bars are colored with a gradient based on their value (low → high).

    universities: global university filter applied to all degrees (None = all)
    degree_universities: optional per-degree override, e.g. {"Law": ["NUS", "SMU"]}.
        If a degree has a non-empty entry here, it takes precedence over the
        global `universities` filter for that degree.
    show_median: if True, draw a dotted horizontal reference line for the
        median value of the chosen metric, in the same year.
    median_level: which median to draw when show_median is True --
        "degree" = median across all universities offering that same degree,
        "category" = median across all degrees in that degree's category,
        "overall" = median across all degrees in the dataset.
    """
    is_rate = metric in RATE_METRICS
    label = _fmt_metric(metric)
    degree_universities = degree_universities or {}

    if year is None:
        year = df["year"].max()

    year_df = df[df["year"] == year]

    rows = []
    for deg in degrees:
        mask = year_df["degree"].str.lower() == deg.lower()
        deg_df = year_df[mask]

        if deg in degree_universities and degree_universities[deg]:
            deg_df = deg_df[deg_df["university"].isin(degree_universities[deg])]
        elif universities:
            deg_df = deg_df[deg_df["university"].isin(universities)]

        sub = deg_df.groupby("university")[metric].mean().reset_index()
        sub["degree"] = deg
        rows.append(sub)

    if not rows:
        return go.Figure().update_layout(**CHART_THEME, title="No data found")

    plot_df = pd.concat(rows, ignore_index=True).dropna(subset=[metric])
    if is_rate:
        plot_df[metric] = plot_df[metric] * 100

    if plot_df.empty:
        return go.Figure().update_layout(**CHART_THEME, title="No data found")

    plot_df["label"] = plot_df.apply(
        lambda r: f"{r['degree']} ({r['university']})" if len(degrees) > 1 else r["university"], axis=1
    )
    plot_df = plot_df.sort_values(metric, ascending=False).reset_index(drop=True)
    plot_df["rank"] = [f"#{i+1}" for i in range(len(plot_df))]

    bar_vmid = vmid if vmid is not None else _gradient_mid(metric)
    if is_rate:
        bar_cmin, bar_cmax = 0.0, 100.0
    else:
        bar_spread = max(abs(plot_df[metric].max() - bar_vmid),
                         abs(plot_df[metric].min() - bar_vmid), 1)
        bar_cmin = bar_vmid - bar_spread
        bar_cmax = bar_vmid + bar_spread
    bar_colorscale = _make_colorscale(metric, bar_cmin, bar_cmax, bar_vmid)

    fig = go.Figure(go.Bar(
        x=plot_df["label"],
        y=plot_df[metric],
        text=plot_df["rank"],
        textposition="outside",
        textfont=dict(size=11, color="#374151", family="Inter, sans-serif"),
        marker=dict(
            color=plot_df[metric],
            colorscale=bar_colorscale,
            cmin=bar_cmin,
            cmax=bar_cmax,
            line=dict(color="rgba(0,0,0,0.05)", width=1),
            showscale=False,
        ),
        hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.1f}}{'%' if is_rate else ''}<extra></extra>",
    ))

    # ── Median reference line(s) ──
    # Drawn as subtle dotted horizontal lines so they're visible without
    # competing with the bars. One line per group at the chosen level
    # (e.g. one per selected degree if median_level="degree").
    if show_median:
        median_groups: list[tuple[str, float]] = []
        if median_level == "overall":
            val = year_df[metric].median()
            if pd.notna(val):
                median_groups.append(("Overall median", val))
        elif median_level == "category":
            sel_mask = year_df["degree"].str.lower().isin([d.lower() for d in degrees])
            cats = sorted(year_df.loc[sel_mask, "category"].dropna().unique().tolist())
            for cat in cats:
                val = year_df.loc[year_df["category"] == cat, metric].median()
                if pd.notna(val):
                    median_groups.append((f"{cat} median", val))
        else:  # "degree"
            for deg in degrees:
                deg_mask = year_df["degree"].str.lower() == deg.lower()
                val = year_df.loc[deg_mask, metric].median()
                if pd.notna(val):
                    median_groups.append((f"{deg} median", val))

        line_colors = ["#6366F1", "#EC4899", "#0EA5E9", "#F59E0B", "#14B8A6", "#8B5CF6"]
        for i, (line_label, val) in enumerate(median_groups):
            y_val = val * 100 if is_rate else val
            fig.add_hline(
                y=y_val,
                line_dash="dot",
                line_color=line_colors[i % len(line_colors)],
                line_width=1.5,
                opacity=0.75,
                annotation_text=line_label,
                annotation_position="top right",
                annotation_font=dict(size=10, color=line_colors[i % len(line_colors)]),
            )

    y_title = f"{label} (%)" if is_rate else label
    y_rng = _y_range(plot_df[metric], is_rate)

    fig.update_layout(
        **CHART_THEME,
        title=dict(text=f"{label} — {year}", font=dict(size=16, color="#111827")),
        xaxis=dict(
            tickangle=-40,
            gridcolor="#F3F4F6",
            tickfont=dict(size=11),
            automargin=True,
        ),
        yaxis=dict(
            title=y_title,
            gridcolor="#F3F4F6",
            range=y_rng,
            ticksuffix="%" if is_rate else "",
        ),
        margin=dict(l=70, r=30, t=60, b=140),
        showlegend=False,
    )
    return fig


def dashboard_overview(df: pd.DataFrame, metric: str) -> go.Figure:
    """Overall metric trend across all years (mean across all degrees)."""
    is_rate = metric in RATE_METRICS
    label = _fmt_metric(metric)

    agg = df.groupby("year")[metric].mean().reset_index().dropna(subset=[metric])
    y_vals = agg[metric] * 100 if is_rate else agg[metric]

    fig = go.Figure(go.Scatter(
        x=agg["year"],
        y=y_vals,
        mode="lines+markers",
        line=dict(color="#3B82F6", width=3),
        marker=dict(size=8, color="#3B82F6"),
        fill="tonexty",
        fillcolor="rgba(59,130,246,0.08)",
    ))

    y_title = f"{label} (%)" if is_rate else label
    y_rng = _y_range(y_vals, is_rate)

    fig.update_layout(
        **CHART_THEME,
        title=dict(text=f"Overall {label} Trend", font=dict(size=15, color="#111827")),
        xaxis=dict(title="Year", tickformat="d", gridcolor="#F3F4F6"),
        yaxis=dict(
            title=y_title,
            gridcolor="#F3F4F6",
            range=y_rng,
            ticksuffix="%" if is_rate else "",
        ),
        margin=dict(l=70, r=30, t=60, b=60),
    )
    return fig


def category_heatmap(df: pd.DataFrame, metric: str, year: int = None,
                     vmid: float = None) -> go.Figure:
    """
    TradingView-style treemap: degrees are grouped into category sections.
    Three levels deep — category → degree → university — so users can click
    into a degree's rectangle to zoom in and see each university's value for
    that degree individually. Colored by the selected metric on a diverging
    green→yellow→red scale (high=green, mid=yellow, low=red).
    """
    is_rate = metric in RATE_METRICS
    label = _fmt_metric(metric)

    if year is None:
        year = df["year"].max()

    year_df = df[df["year"] == year]
    if "category" not in year_df.columns:
        return go.Figure().update_layout(**CHART_THEME, title="No category data available")

    # Degree-level aggregate (for the category/degree nodes)
    deg_agg = (
        year_df.groupby(["category", "degree"])[metric]
        .mean()
        .dropna()
        .reset_index()
    )
    if deg_agg.empty:
        return go.Figure().update_layout(**CHART_THEME, title="No data found")

    # University-level detail (for the leaf nodes, one per degree x university)
    uni_agg = (
        year_df.groupby(["category", "degree", "university"])[metric]
        .mean()
        .dropna()
        .reset_index()
    )

    if is_rate:
        deg_agg[metric] = deg_agg[metric] * 100
        uni_agg[metric] = uni_agg[metric] * 100

    hm_vmid = vmid if vmid is not None else _gradient_mid(metric)
    if is_rate:
        hm_cmin, hm_cmax = 0.0, 100.0
    else:
        all_vals = pd.concat([deg_agg[metric], uni_agg[metric]]).dropna()
        hm_spread = max(abs(all_vals.max() - hm_vmid),
                        abs(all_vals.min() - hm_vmid), 1)
        hm_cmin = hm_vmid - hm_spread
        hm_cmax = hm_vmid + hm_spread
    hm_colorscale = _make_colorscale(metric, hm_cmin, hm_cmax, hm_vmid)

    # Use ids built from "category/degree/university" paths (like px.treemap
    # does internally) so each leaf has a globally-unique node id — using
    # plain labels alone is ambiguous whenever names repeat across branches,
    # and an ambiguous tree renders as empty.
    ids, labels, parents, values, colors, customtext, display_text = [], [], [], [], [], [], []

    def _wrap(s: str, max_chars: int = 16) -> str:
        """Insert <br> breaks at word boundaries so long names wrap onto
        multiple lines instead of Plotly auto-shrinking them to fit one."""
        words = s.split()
        lines, current = [], ""
        for w in words:
            candidate = f"{current} {w}".strip()
            if len(candidate) > max_chars and current:
                lines.append(current)
                current = w
            else:
                current = candidate
        if current:
            lines.append(current)
        return "<br>".join(lines)

    ROOT_ID = "All Degrees"
    ids.append(ROOT_ID)
    labels.append(ROOT_ID)
    parents.append("")
    values.append(0)
    colors.append(hm_vmid)
    customtext.append("")
    display_text.append(ROOT_ID)

    cat_means = deg_agg.groupby("category")[metric].mean()
    for cat, cat_mean in cat_means.items():
        cat_id = f"{ROOT_ID}::{cat}"
        ids.append(cat_id)
        labels.append(cat)
        parents.append(ROOT_ID)
        values.append(0)
        colors.append(cat_mean)
        customtext.append("")
        display_text.append(_wrap(cat, max_chars=20))

    for _, row in deg_agg.iterrows():
        val = row[metric]
        txt = f"{val:.1f}%" if is_rate else f"${val:,.0f}"
        cat_id = f"{ROOT_ID}::{row['category']}"
        deg_id = f"{cat_id}::{row['degree']}"
        ids.append(deg_id)
        labels.append(row["degree"])
        parents.append(cat_id)
        values.append(0)  # value comes from children (universities) below
        colors.append(val)
        customtext.append(txt)
        display_text.append(_wrap(row["degree"], max_chars=16))

    for _, row in uni_agg.iterrows():
        val = row[metric]
        txt = f"{val:.1f}%" if is_rate else f"${val:,.0f}"
        cat_id = f"{ROOT_ID}::{row['category']}"
        deg_id = f"{cat_id}::{row['degree']}"
        uni_id = f"{deg_id}::{row['university']}"
        ids.append(uni_id)
        labels.append(row["university"])
        parents.append(deg_id)
        values.append(1.0)
        colors.append(val)
        customtext.append(txt)
        display_text.append(row["university"])

    fig = go.Figure(go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        text=display_text,
        customdata=customtext,
        texttemplate="<b style='font-size:1em'>%{text}</b><br><span style='font-size:1.3em'>%{customdata}</span>",
        textfont=dict(size=24, color="white", family="Inter, sans-serif"),
        insidetextfont=dict(size=24, color="white", family="Inter, sans-serif"),
        outsidetextfont=dict(size=19, color="#111827", family="Inter, sans-serif"),
        textposition="middle center",
        marker=dict(
            colors=colors,
            colorscale=hm_colorscale,
            cmin=hm_cmin,
            cmax=hm_cmax,
            line=dict(width=2, color="#18181B"),
            showscale=True,
            colorbar=dict(
                title=dict(text=f"{label}{' (%)' if is_rate else ''}", side="right", font=dict(size=14, color="#374151")),
                thickness=18,
                outlinewidth=0,
                tickfont=dict(size=13),
            ),
        ),
        branchvalues="remainder",
        hovertemplate="<b>%{label}</b><br>" + label + ": %{customdata}<extra></extra>",
        pathbar=dict(visible=True, thickness=28, textfont=dict(size=15)),
        tiling=dict(packing="squarify", pad=1),
        # maxdepth=3 means: root + category + degree are shown initially
        # (root doesn't count as a visible ring). Universities (the 4th
        # level / 3rd ring) only become visible once the user clicks into
        # a degree, which shifts the effective root down one level.
        maxdepth=3,
    ))

    fig.update_layout(
        title=dict(text=f"{label} — Degrees by Category ({year})", font=dict(size=19, color="#111827")),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=15, color="#374151"),
        margin=dict(l=10, r=10, t=55, b=10),
        height=760,
    )
    return fig


def category_breakdown(df: pd.DataFrame, metric: str, year: int = None) -> go.Figure:
    """Bar chart of top/bottom degrees in a category for the latest year."""
    from src.etl import RATE_METRICS
    is_rate = metric in RATE_METRICS
    label = _fmt_metric(metric)

    if year is None:
        year = df["year"].max()

    agg = (
        df[df["year"] == year]
        .groupby("degree")[metric].mean()
        .dropna()
        .reset_index()
        .sort_values(metric, ascending=False)
    )

    if is_rate:
        agg[metric] = agg[metric] * 100

    # Top 6 + bottom 6 if > 12, else all
    if len(agg) > 12:
        plot_df = pd.concat([agg.head(6), agg.tail(6)])
    else:
        plot_df = agg

    n = len(plot_df)
    colors = (
        ["#10B981"] * min(6, n // 2 + n % 2) +
        ["#EF4444"] * min(6, n // 2)
        if len(agg) > 12
        else ["#3B82F6"] * n
    )

    fig = go.Figure(go.Bar(
        x=plot_df["degree"],
        y=plot_df[metric],
        marker_color=colors,
        hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.1f}}{'%' if is_rate else ''}<extra></extra>",
    ))

    y_title = f"{label} (%)" if is_rate else label
    y_rng = _y_range(plot_df[metric], is_rate)

    fig.update_layout(
        **CHART_THEME,
        title=dict(text=f"{label} by Degree ({year})", font=dict(size=15, color="#111827")),
        xaxis=dict(
            tickangle=-40,
            gridcolor="#F3F4F6",
            tickfont=dict(size=11),
            automargin=True,
        ),
        yaxis=dict(
            title=y_title,
            gridcolor="#F3F4F6",
            range=y_rng,
            ticksuffix="%" if is_rate else "",
        ),
        margin=dict(l=70, r=30, t=60, b=150),
        showlegend=False,
    )
    return fig


def degree_sparkline(df: pd.DataFrame, degree: str, metric: str,
                      universities: list[str] = None, n_years: int = 3) -> go.Figure:
    """
    Small sparkline showing one degree's trend for a metric over the most
    recent n_years (averaged across whichever universities are included).
    """
    mask = df["degree"].str.lower() == degree.lower()
    subset = df[mask]
    if universities:
        subset = subset[subset["university"].isin(universities)]

    is_rate = metric in RATE_METRICS
    agg = subset.groupby("year")[metric].mean().reset_index().dropna(subset=[metric])
    agg = agg.sort_values("year").tail(n_years)
    y = agg[metric] * 100 if is_rate else agg[metric]

    if agg.empty:
        fig = go.Figure()
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            height=50, showlegend=False,
        )
        return fig

    trend_up = len(y) >= 2 and y.iloc[-1] >= y.iloc[0]
    line_color = "#10B981" if trend_up else "#EF4444"
    fill_color = "rgba(16,185,129,0.10)" if trend_up else "rgba(239,68,68,0.10)"

    fig = go.Figure(go.Scatter(
        x=agg["year"], y=y,
        mode="lines+markers",
        line=dict(color=line_color, width=2.5),
        marker=dict(size=5, color=line_color),
        fill="tozeroy", fillcolor=fill_color,
    ))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=50, showlegend=False,
    )
    return fig


def metric_sparklines(df: pd.DataFrame) -> dict[str, go.Figure]:
    """Return a dict of small sparkline figures, one per metric."""
    figs = {}
    for metric, label in METRIC_LABELS.items():
        is_rate = metric in RATE_METRICS
        agg = df.groupby("year")[metric].mean().reset_index().dropna(subset=[metric])
        y = agg[metric] * 100 if is_rate else agg[metric]

        fig = go.Figure(go.Scatter(
            x=agg["year"], y=y,
            mode="lines", line=dict(color="#6366F1", width=2),
            fill="tonexty", fillcolor="rgba(99,102,241,0.1)",
        ))
        y_rng = _y_range(y, is_rate)
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, range=y_rng),
            height=60, showlegend=False,
        )
        figs[metric] = fig
    return figs
