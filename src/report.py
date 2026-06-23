"""
PDF report generation for the GES Dashboard.
Renders the current Overall Trend view (KPI summary + trend chart) and the
degree heatmap into a downloadable PDF, using reportlab for layout and
kaleido (pinned to 0.2.1, which doesn't require a separate Chrome install)
for converting Plotly figures to static images.
"""

import io
from datetime import datetime
from typing import Optional

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
)


def _fig_to_image(fig: go.Figure, width: int = 900, height: int = 480) -> io.BytesIO:
    """Render a Plotly figure to a PNG image in memory."""
    png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return io.BytesIO(png_bytes)


def generate_dashboard_pdf(
    *,
    mode_label: str,
    metric_label: str,
    year: int,
    kpi_rows: list,
    trend_fig: go.Figure,
    heatmap_fig: go.Figure,
    compare_fig: Optional[go.Figure] = None,
    compare_label: str = "",
) -> bytes:
    """
    Build a PDF report of the current dashboard view.

    kpi_rows: list of {"label": str, "value": str, "delta": str} dicts,
        one per KPI card currently shown.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"], fontSize=10,
        textColor=colors.HexColor("#6B7280"), spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"], fontSize=13,
        spaceBefore=16, spaceAfter=8,
    )

    story = []
    story.append(Paragraph("Graduate Employment Dashboard", title_style))
    generated_str = datetime.now().strftime("%d %b %Y, %H:%M")
    story.append(Paragraph(
        f"View: {mode_label} &middot; Metric: {metric_label} &middot; "
        f"Reference year: {year} &middot; Generated {generated_str}",
        subtitle_style,
    ))

    # ── KPI summary table ──
    if kpi_rows:
        story.append(Paragraph("Key Metrics", section_style))
        table_data = [["Metric", "Value", "YoY Change"]]
        for row in kpi_rows:
            table_data.append([row["label"], row["value"], row.get("delta", "—")])

        kpi_table = Table(table_data, colWidths=[6.5 * cm, 4 * cm, 4 * cm])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(kpi_table)

    # ── Trend chart ──
    story.append(Paragraph("Trend Over Time", section_style))
    trend_img_buf = _fig_to_image(trend_fig)
    story.append(RLImage(trend_img_buf, width=17 * cm, height=17 * cm * 480 / 900))
    story.append(Spacer(1, 8))

    # ── Heatmap ──
    story.append(Paragraph("Degree Heatmap by Category", section_style))
    heatmap_img_buf = _fig_to_image(heatmap_fig, width=900, height=600)
    story.append(RLImage(heatmap_img_buf, width=17 * cm, height=17 * cm * 600 / 900))

    # ── Compare Degrees chart (only if user visited that tab and built a chart) ──
    if compare_fig is not None:
        title_text = "Compare Degrees"
        if compare_label:
            title_text += f": {compare_label}"
        story.append(Paragraph(title_text, section_style))
        compare_img_buf = _fig_to_image(compare_fig, width=900, height=480)
        story.append(RLImage(compare_img_buf, width=17 * cm, height=17 * cm * 480 / 900))

    doc.build(story)
    buf.seek(0)
    return buf.read()
