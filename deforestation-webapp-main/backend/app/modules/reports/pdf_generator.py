"""Professional PDF report generator using ReportLab.

Generates multi-page, print-ready PDF reports for ForestWatch intelligence
data.  Entry point: ``generate_report_pdf(report_data, output_path)``.

Layout
------
  1. Title page
  2. Table of contents
  3. Executive Summary
  4. Intelligence Events
  5. Regional Risk Analysis  (bar chart)
  6. Top Anomalies
  7. Weather Summary
  8. Historical Analysis      (bar chart)
  9. Land Cover Distribution  (pie chart)
 10. Notifications & Alerts
 11. System Status

The generator is fully synchronous.  Run it inside a thread-pool executor
when calling from async code.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("forestwatch.reports.pdf")

# ---------------------------------------------------------------------------
# Conditional import guard — ReportLab may not be installed in test envs
# ---------------------------------------------------------------------------
try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
_GREEN = "#2d5a27"
_LIGHT_GREEN = "#f4f5f2"
_MID_GREEN = "#eaece6"
_DARK = "#1a1e1a"
_MUTED = "#7b827b"
_RED = "#ef4444"
_ORANGE = "#f97316"
_YELLOW = "#eab308"
_SAFE = "#22c55e"
_BLUE = "#3b82f6"

_RISK_COLORS = {
    "Extreme": _RED,
    "High": _ORANGE,
    "Moderate": _YELLOW,
    "Low": _SAFE,
}

_COVER_COLORS = {
    "forest": "#1b4332",
    "near_forest": "#52b788",
    "agriculture": "#ffd166",
    "urban": "#ef476f",
    "water": "#118ab2",
    "unknown": "#9ca3af",
}

PAGE_W, PAGE_H = A4  # 595.27, 841.89 pts


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    green = HexColor(_GREEN)
    dark = HexColor(_DARK)
    muted = HexColor(_MUTED)

    def _add(name, parent_name="Normal", **kw):
        if name not in base:
            base.add(ParagraphStyle(name=name, parent=base[parent_name], **kw))
        return base[name]

    _add("FW_Title", "Title",
         fontName="Helvetica-Bold", fontSize=28, textColor=green,
         alignment=TA_CENTER, spaceAfter=6)
    _add("FW_Subtitle", "Normal",
         fontName="Helvetica", fontSize=13, textColor=muted,
         alignment=TA_CENTER, spaceAfter=4)
    _add("FW_CoverMeta", "Normal",
         fontName="Helvetica", fontSize=10, textColor=dark,
         alignment=TA_CENTER, spaceAfter=3)
    _add("FW_H1", "Heading1",
         fontName="Helvetica-Bold", fontSize=14, textColor=green,
         spaceBefore=14, spaceAfter=6)
    _add("FW_H2", "Heading2",
         fontName="Helvetica-Bold", fontSize=11, textColor=dark,
         spaceBefore=8, spaceAfter=4)
    _add("FW_Body", "Normal",
         fontName="Helvetica", fontSize=9, textColor=dark,
         leading=13, spaceAfter=4)
    _add("FW_Small", "Normal",
         fontName="Helvetica", fontSize=7.5, textColor=muted, leading=11)
    _add("FW_TH", "Normal",
         fontName="Helvetica-Bold", fontSize=8.5, textColor=white,
         alignment=TA_CENTER)
    _add("FW_TD", "Normal",
         fontName="Helvetica", fontSize=8.5, textColor=dark,
         alignment=TA_LEFT)
    _add("FW_TD_R", "Normal",
         fontName="Helvetica", fontSize=8.5, textColor=dark,
         alignment=TA_RIGHT)
    _add("FW_TOC", "Normal",
         fontName="Helvetica", fontSize=9.5, textColor=dark, leading=16)
    _add("FW_Badge", "Normal",
         fontName="Helvetica-Bold", fontSize=7.5, alignment=TA_CENTER)
    return base


def _hdr_cell(text, styles) -> "Paragraph":
    return Paragraph(text, styles["FW_TH"])


def _cell(text, styles, align="left") -> "Paragraph":
    s = styles["FW_TD"] if align == "left" else styles["FW_TD_R"]
    return Paragraph(str(text), s)


def _table_style(header_color=None) -> "TableStyle":
    hc = HexColor(header_color or _GREEN)
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), hc),
        ("TEXTCOLOR",  (0, 0), (-1, 0), white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor(_LIGHT_GREEN), white]),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 8),
        ("TOPPADDING",    (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("GRID",       (0, 0), (-1, -1), 0.4, HexColor(_MID_GREEN)),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ])


def _fmt_dt(dt: Any) -> str:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    return str(dt) if dt else "—"


def _fmt_date(dt: Any) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%d %b %Y")
    return str(dt) if dt else "—"


def _safe(val: Any, default="—") -> str:
    if val is None or val == "":
        return default
    return str(val)


def _pct(val: Any) -> str:
    try:
        return f"{float(val):.0%}"
    except Exception:
        return "—"


def _score(val: Any) -> str:
    try:
        return f"{float(val):.3f}"
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# Page decorations (header + footer)
# ---------------------------------------------------------------------------

def _make_on_page(title: str, generated_at: str):
    """Return a canvas callback for header/footer."""
    def _on_page(canvas, doc):
        canvas.saveState()
        green = HexColor(_GREEN)
        muted = HexColor(_MUTED)
        is_cover = doc.page == 1

        if not is_cover:
            # Header line
            canvas.setStrokeColor(HexColor(_MID_GREEN))
            canvas.setLineWidth(0.5)
            canvas.line(2 * cm, PAGE_H - 1.8 * cm, PAGE_W - 2 * cm, PAGE_H - 1.8 * cm)
            canvas.setFillColor(green)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.drawString(2 * cm, PAGE_H - 1.5 * cm, "ForestWatch Intelligence Platform")
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(muted)
            canvas.drawRightString(PAGE_W - 2 * cm, PAGE_H - 1.5 * cm, title)

        # Footer line
        canvas.setStrokeColor(HexColor(_MID_GREEN))
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, 1.5 * cm, PAGE_W - 2 * cm, 1.5 * cm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(2 * cm, 1.1 * cm, f"Generated: {generated_at}")
        canvas.drawRightString(PAGE_W - 2 * cm, 1.1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    return _on_page


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_title_page(rd: dict, styles) -> list:
    story = []
    story.append(Spacer(1, 3 * cm))

    # Brand block
    green = HexColor(_GREEN)
    report_type_label = {
        "daily": "Daily Intelligence Report",
        "weekly": "Weekly Intelligence Report",
        "monthly": "Monthly Intelligence Report",
        "on_demand": "On-Demand Intelligence Report",
    }.get(rd.get("report_type", "on_demand"), "Intelligence Report")

    story.append(Paragraph("ForestWatch", styles["FW_Title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="60%", thickness=2, color=green, hAlign="CENTER"))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(report_type_label, styles["FW_Subtitle"]))
    story.append(Spacer(1, 1.5 * cm))

    # Period table
    ps = _fmt_date(rd.get("period_start"))
    pe = _fmt_date(rd.get("period_end"))
    ga = _fmt_dt(rd.get("generated_at"))

    meta_data = [
        ["Reporting Period", f"{ps}  –  {pe}"],
        ["Generated At", ga],
        ["Classification", "OPERATIONAL"],
        ["Region", "Romania"],
    ]
    meta_table = Table(meta_data, colWidths=[5 * cm, 8 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), green),
        ("TEXTCOLOR", (1, 0), (1, -1), HexColor(_DARK)),
        ("ALIGN",     (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, HexColor(_MID_GREEN)),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3 * cm))

    # Badge
    summary = rd.get("summary") or {}
    active = summary.get("active_intel_events", "—")
    anomalies = summary.get("anomaly_count", "—")
    risk_region = summary.get("highest_risk_region", "—")

    badges = [
        [f"Active Events: {active}", f"Anomalies: {anomalies}", f"Highest Risk: {risk_region}"]
    ]
    badge_table = Table(badges, colWidths=[5.5 * cm, 4 * cm, 5.5 * cm])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), HexColor(_GREEN)),
        ("TEXTCOLOR",    (0, 0), (-1, -1), white),
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(badge_table)
    return story


def _build_toc(styles) -> list:
    story = [Paragraph("Table of Contents", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.4 * cm))

    sections = [
        ("Executive Summary", "3"),
        ("Intelligence Events", "4"),
        ("Regional Risk Analysis", "5"),
        ("Top Anomalies", "6"),
        ("Weather Summary", "7"),
        ("Historical Analysis", "8"),
        ("Land Cover Distribution", "9"),
        ("Notifications & Alerts", "10"),
        ("System Status", "11"),
    ]
    for title, pg in sections:
        dots = "." * max(1, 70 - len(title) - len(pg))
        story.append(Paragraph(
            f"<font name='Helvetica'>{title}</font>"
            f"<font name='Helvetica' color='{_MUTED}'> {dots} </font>"
            f"<font name='Helvetica-Bold'>{pg}</font>",
            styles["FW_TOC"],
        ))
    return story


def _build_executive_summary(rd: dict, styles) -> list:
    story = [Paragraph("Executive Summary", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    summary = rd.get("summary") or {}
    overview = rd.get("overview") or {}

    metrics = [
        [_hdr_cell("Metric", styles), _hdr_cell("Value", styles)],
        [_cell("Total Forest Events", styles), _cell(_safe(overview.get("total_events", 0)), styles)],
        [_cell("Open Events", styles), _cell(_safe(overview.get("open_events", 0)), styles)],
        [_cell("Active Intelligence Events", styles), _cell(_safe(summary.get("active_intel_events", 0)), styles)],
        [_cell("Resolved Intelligence Events", styles), _cell(_safe(summary.get("resolved_intel_events", 0)), styles)],
        [_cell("Anomalies Detected", styles), _cell(_safe(summary.get("anomaly_count", 0)), styles)],
        [_cell("Highest Risk Region", styles), _cell(_safe(summary.get("highest_risk_region")), styles)],
        [_cell("Highest Risk Score", styles), _cell(_score(summary.get("highest_risk_score")), styles)],
        [_cell("Average Event Confidence", styles),
         _cell(_pct(overview.get("average_confidence", 0)), styles)],
    ]
    t = Table(metrics, colWidths=[9 * cm, 6 * cm])
    t.setStyle(_table_style())
    story.append(t)

    # Narrative paragraph
    active = summary.get("active_intel_events", 0)
    risk_r = summary.get("highest_risk_region") or "unknown"
    risk_s = summary.get("highest_risk_score")
    risk_txt = f"{float(risk_s):.2f}" if risk_s is not None else "unknown"
    ps = _fmt_date(rd.get("period_start"))
    pe = _fmt_date(rd.get("period_end"))

    story.append(Spacer(1, 0.4 * cm))
    narrative = (
        f"During the reporting period {ps} – {pe}, ForestWatch recorded "
        f"<b>{active}</b> active intelligence events across Romanian regions. "
        f"The highest fire risk concentration was observed in <b>{risk_r}</b> "
        f"(score: {risk_txt}). "
        "All figures reflect data captured by the automated ingestion pipeline "
        "and classified through the deterministic risk assessment engine."
    )
    story.append(Paragraph(narrative, styles["FW_Body"]))
    return story


def _build_intelligence_events(rd: dict, styles) -> list:
    story = [Paragraph("Intelligence Events", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    events = rd.get("intelligence_events") or {}
    active_list = events.get("active", [])
    resolved_list = events.get("resolved", [])

    # Active events
    story.append(Paragraph(f"Active Events ({len(active_list)})", styles["FW_H2"]))
    if active_list:
        rows = [[
            _hdr_cell("Region", styles),
            _hdr_cell("Type", styles),
            _hdr_cell("Severity", styles),
            _hdr_cell("Escalation", styles),
            _hdr_cell("Trend", styles),
            _hdr_cell("Priority", styles),
        ]]
        for ev in active_list[:25]:
            rows.append([
                _cell(_safe(ev.get("region")), styles),
                _cell(_safe(ev.get("event_type", ev.get("type", "—"))), styles),
                _cell(_safe(ev.get("severity", "—")), styles),
                _cell(_safe(ev.get("escalation_level", "—")), styles),
                _cell(_safe(ev.get("trend", "—")), styles),
                _cell(_score(ev.get("priority_score", ev.get("priority"))), styles, "right"),
            ])
        t = Table(rows, colWidths=[3.5*cm, 3*cm, 2.2*cm, 2.5*cm, 2.3*cm, 2*cm])
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No active intelligence events in this period.", styles["FW_Body"]))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Resolved Events: <b>{len(resolved_list)}</b> events were resolved during this period.",
        styles["FW_Body"],
    ))
    return story


def _build_risk_analysis(rd: dict, styles) -> list:
    story = [Paragraph("Regional Risk Analysis", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    risk = rd.get("risk") or {}
    regions = risk.get("regions", [])

    if regions:
        # Table
        rows = [[
            _hdr_cell("Region", styles),
            _hdr_cell("Risk Score", styles),
            _hdr_cell("Level", styles),
            _hdr_cell("Anomalies", styles),
        ]]
        for r in regions[:20]:
            level = r.get("risk_level", "—")
            level_color = _RISK_COLORS.get(level, _MUTED)
            level_para = Paragraph(
                f'<font color="{level_color}"><b>{level}</b></font>',
                styles["FW_TD"],
            )
            rows.append([
                _cell(_safe(r.get("region")), styles),
                _cell(_score(r.get("risk_score")), styles, "right"),
                level_para,
                _cell(_safe(r.get("anomaly_count", "—")), styles, "right"),
            ])
        t = Table(rows, colWidths=[5.5*cm, 3*cm, 3.5*cm, 3.5*cm])
        t.setStyle(_table_style())
        story.append(t)

        # Bar chart
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Risk Score Distribution — Top Regions", styles["FW_H2"]))
        chart_drawing = _make_risk_chart(regions)
        if chart_drawing:
            story.append(chart_drawing)
    else:
        story.append(Paragraph("No risk data available for this period.", styles["FW_Body"]))

    return story


def _make_risk_chart(regions: list) -> "Drawing | None":
    try:
        top = sorted(regions, key=lambda r: float(r.get("risk_score") or 0), reverse=True)[:8]
        if not top:
            return None

        drawing = Drawing(420, 190)
        chart = VerticalBarChart()
        chart.x = 55
        chart.y = 40
        chart.height = 120
        chart.width = 340
        chart.data = [[float(r.get("risk_score") or 0) for r in top]]
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 1.0
        chart.valueAxis.valueStep = 0.25
        chart.valueAxis.labels.fontSize = 7
        chart.categoryAxis.categoryNames = [
            (r.get("region") or "?")[:10] for r in top
        ]
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.categoryAxis.labels.angle = 30
        chart.categoryAxis.labels.dy = -5
        chart.categoryAxis.labels.fontSize = 7
        chart.bars[0].fillColor = HexColor(_GREEN)
        drawing.add(chart)
        return drawing
    except Exception as exc:
        logger.warning("Risk chart failed: %s", exc)
        return None


def _build_anomalies(rd: dict, styles) -> list:
    story = [Paragraph("Top Anomalies", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    anomalies_data = rd.get("anomalies") or {}
    anomalies = anomalies_data.get("anomalies", [])

    if anomalies:
        rows = [[
            _hdr_cell("Region", styles),
            _hdr_cell("Anomaly Score", styles),
            _hdr_cell("Deviation", styles),
            _hdr_cell("Severity", styles),
            _hdr_cell("Status", styles),
        ]]
        for a in anomalies[:20]:
            rows.append([
                _cell(_safe(a.get("region")), styles),
                _cell(_score(a.get("anomaly_score", a.get("score"))), styles, "right"),
                _cell(_score(a.get("deviation_from_baseline", a.get("deviation"))), styles, "right"),
                _cell(_safe(a.get("severity", "—")), styles),
                _cell(_safe(a.get("status", "active")), styles),
            ])
        t = Table(rows, colWidths=[4.5*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm])
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No anomalies detected in this period.", styles["FW_Body"]))

    return story


def _build_weather(rd: dict, styles) -> list:
    story = [Paragraph("Weather Summary", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    weather = rd.get("weather") or {}
    regions = weather.get("regions", [])

    if regions:
        rows = [[
            _hdr_cell("Region", styles),
            _hdr_cell("Temp (°C)", styles),
            _hdr_cell("Humidity (%)", styles),
            _hdr_cell("Wind (km/h)", styles),
            _hdr_cell("Precip (mm)", styles),
            _hdr_cell("Updated", styles),
        ]]
        for r in regions:
            rows.append([
                _cell(_safe(r.get("region")), styles),
                _cell(f"{r.get('temperature', '—')}", styles, "right"),
                _cell(f"{r.get('humidity', '—')}", styles, "right"),
                _cell(f"{r.get('wind_speed', '—')}", styles, "right"),
                _cell(f"{r.get('precipitation', '—')}", styles, "right"),
                _cell(_fmt_dt(r.get("updated_at")), styles),
            ])
        t = Table(rows, colWidths=[3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("Weather data not available for this period.", styles["FW_Body"]))

    return story


def _build_historical(rd: dict, styles) -> list:
    story = [Paragraph("Historical Analysis", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    daily = rd.get("daily_activity") or {}
    days_list = daily.get("days", [])

    if days_list:
        story.append(Paragraph("Daily Activity — Last 30 Days", styles["FW_H2"]))
        chart_drawing = _make_activity_chart(days_list)
        if chart_drawing:
            story.append(chart_drawing)

    # Monthly table
    monthly = rd.get("monthly_summary") or {}
    months = monthly.get("months", [])
    if months:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Monthly Summary", styles["FW_H2"]))
        rows = [[
            _hdr_cell("Month", styles),
            _hdr_cell("Events", styles),
            _hdr_cell("Anomalies", styles),
            _hdr_cell("Forest Events", styles),
        ]]
        for m in months[-12:]:
            rows.append([
                _cell(_safe(m.get("month")), styles),
                _cell(_safe(m.get("events", 0)), styles, "right"),
                _cell(_safe(m.get("anomalies", 0)), styles, "right"),
                _cell(_safe(m.get("forest_events", 0)), styles, "right"),
            ])
        t = Table(rows, colWidths=[4*cm, 3*cm, 3*cm, 5.5*cm])
        t.setStyle(_table_style())
        story.append(t)

    if not days_list and not months:
        story.append(Paragraph("No historical data available.", styles["FW_Body"]))

    # Regional history
    reg_hist = rd.get("regional_history") or []
    if reg_hist:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Regional 30-Day Comparison", styles["FW_H2"]))
        rows = [[
            _hdr_cell("Region", styles),
            _hdr_cell("Last 30d", styles),
            _hdr_cell("Prev 30d", styles),
            _hdr_cell("Change %", styles),
            _hdr_cell("Trend", styles),
        ]]
        for r in reg_hist[:15]:
            chg = r.get("change_percent", 0)
            chg_color = _RED if chg > 10 else (_SAFE if chg < -10 else _DARK)
            chg_para = Paragraph(
                f'<font color="{chg_color}">{chg:+.1f}%</font>',
                styles["FW_TD_R"],
            )
            rows.append([
                _cell(_safe(r.get("region")), styles),
                _cell(_safe(r.get("events_last_30d", 0)), styles, "right"),
                _cell(_safe(r.get("events_previous_30d", 0)), styles, "right"),
                chg_para,
                _cell(_safe(r.get("trend", "—")), styles),
            ])
        t = Table(rows, colWidths=[4*cm, 2.5*cm, 2.5*cm, 2.5*cm, 4*cm])
        t.setStyle(_table_style())
        story.append(t)

    return story


def _make_activity_chart(days_list: list) -> "Drawing | None":
    try:
        # Use every-3rd-day sample for readability (max 10 bars)
        sample = days_list[::3][-10:]
        if not sample:
            return None

        drawing = Drawing(420, 180)
        chart = VerticalBarChart()
        chart.x = 45
        chart.y = 40
        chart.height = 110
        chart.width = 350
        chart.data = [
            [int(d.get("events", 0)) for d in sample],
            [int(d.get("anomalies", 0)) for d in sample],
        ]
        max_val = max(
            (max(chart.data[0], default=0), max(chart.data[1], default=0)),
        )
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(max_val + 2, 5)
        chart.valueAxis.labels.fontSize = 7
        chart.categoryAxis.categoryNames = [d.get("date", "")[-5:] for d in sample]
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.angle = 30
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.bars[0].fillColor = HexColor(_GREEN)
        chart.bars[1].fillColor = HexColor(_ORANGE)
        drawing.add(chart)
        return drawing
    except Exception as exc:
        logger.warning("Activity chart failed: %s", exc)
        return None


def _build_land_cover(rd: dict, styles) -> list:
    story = [Paragraph("Land Cover Distribution", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    lc = rd.get("land_cover") or {}
    dist = lc.get("distribution") or lc.get("by_class") or {}

    if dist:
        # Side-by-side: pie chart + table
        chart_drawing = _make_land_cover_chart(dist)

        rows = [[_hdr_cell("Land Cover Type", styles), _hdr_cell("Count", styles)]]
        total = sum(dist.values()) or 1
        for k, v in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            rows.append([
                _cell(k.replace("_", " ").title(), styles),
                _cell(f"{v}  ({v / total:.0%})", styles, "right"),
            ])

        table_fl = Table(rows, colWidths=[5*cm, 3.5*cm])
        table_fl.setStyle(_table_style())

        if chart_drawing:
            combined = Table([[chart_drawing, table_fl]], colWidths=[9*cm, 8.5*cm])
            combined.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(combined)
        else:
            story.append(table_fl)
    else:
        story.append(Paragraph("Land cover data not available.", styles["FW_Body"]))

    return story


def _make_land_cover_chart(dist: dict) -> "Drawing | None":
    try:
        items = [(k, v) for k, v in dist.items() if v > 0]
        if not items:
            return None

        labels, values = zip(*items)
        drawing = Drawing(200, 170)
        pie = Pie()
        pie.x = 30
        pie.y = 30
        pie.width = 130
        pie.height = 130
        pie.data = list(values)
        pie.labels = [lbl[:8] for lbl in labels]
        pie.slices.strokeWidth = 0.5
        pie.slices.strokeColor = white
        pie.sideLabels = 1
        for i, lbl in enumerate(labels):
            pie.slices[i].fillColor = HexColor(_COVER_COLORS.get(lbl, "#9ca3af"))
        drawing.add(pie)
        return drawing
    except Exception as exc:
        logger.warning("Land cover chart failed: %s", exc)
        return None


def _build_notifications(rd: dict, styles) -> list:
    story = [Paragraph("Notifications & Alerts", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    notifs = rd.get("notifications") or []
    if notifs:
        rows = [[
            _hdr_cell("Provider", styles),
            _hdr_cell("Event Type", styles),
            _hdr_cell("Region", styles),
            _hdr_cell("Status", styles),
            _hdr_cell("Sent At", styles),
        ]]
        for n in notifs[:20]:
            ok = n.get("success", True)
            status_color = _SAFE if ok else _RED
            status_para = Paragraph(
                f'<font color="{status_color}"><b>{"OK" if ok else "FAIL"}</b></font>',
                styles["FW_TD"],
            )
            rows.append([
                _cell(_safe(n.get("provider")), styles),
                _cell(_safe(n.get("event_type")), styles),
                _cell(_safe(n.get("region")), styles),
                status_para,
                _cell(_fmt_dt(n.get("sent_at")), styles),
            ])
        t = Table(rows, colWidths=[2.5*cm, 3.5*cm, 3*cm, 1.8*cm, 4.7*cm])
        t.setStyle(_table_style())
        story.append(t)

        success = sum(1 for n in notifs if n.get("success", True))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            f"Total notifications: <b>{len(notifs)}</b> — "
            f"Success: <b>{success}</b>, "
            f"Failed: <b>{len(notifs) - success}</b>.",
            styles["FW_Body"],
        ))
    else:
        story.append(Paragraph("No notifications recorded for this period.", styles["FW_Body"]))

    return story


def _build_hotspots(rd: dict, styles) -> list:
    story = [Paragraph("Hotspot Rankings", styles["FW_H2"])]
    story.append(Spacer(1, 0.2 * cm))

    hotspots = rd.get("hotspots") or []
    if hotspots:
        rows = [[
            _hdr_cell("Rank", styles),
            _hdr_cell("Region", styles),
            _hdr_cell("All-Time Detections", styles),
            _hdr_cell("Avg Priority", styles),
            _hdr_cell("Highest Severity", styles),
        ]]
        for i, h in enumerate(hotspots[:15], 1):
            rows.append([
                _cell(str(i), styles, "right"),
                _cell(_safe(h.get("region")), styles),
                _cell(_safe(h.get("detections", 0)), styles, "right"),
                _cell(_score(h.get("average_priority")), styles, "right"),
                _cell(_safe(h.get("highest_severity", "—")), styles),
            ])
        t = Table(rows, colWidths=[1.5*cm, 4.5*cm, 3.5*cm, 3*cm, 3*cm])
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No hotspot data available.", styles["FW_Body"]))

    return story


def _build_system_status(rd: dict, styles) -> list:
    story = [Paragraph("System Status", styles["FW_H1"])]
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(_MID_GREEN)))
    story.append(Spacer(1, 0.3 * cm))

    runs = rd.get("ingestion_runs") or []
    if runs:
        story.append(Paragraph("Recent Ingestion Runs", styles["FW_H2"]))
        rows = [[
            _hdr_cell("Source", styles),
            _hdr_cell("Status", styles),
            _hdr_cell("Events Fetched", styles),
            _hdr_cell("Inserted", styles),
            _hdr_cell("Duration (s)", styles),
            _hdr_cell("Started At", styles),
        ]]
        for run in runs[:10]:
            ok = run.get("status") == "success"
            st_color = _SAFE if ok else _RED
            st_para = Paragraph(
                f'<font color="{st_color}"><b>{run.get("status", "—").upper()}</b></font>',
                styles["FW_TD"],
            )
            rows.append([
                _cell(_safe(run.get("source")), styles),
                st_para,
                _cell(_safe(run.get("events_fetched", 0)), styles, "right"),
                _cell(_safe(run.get("events_inserted", 0)), styles, "right"),
                _cell(_safe(run.get("duration_seconds", "—")), styles, "right"),
                _cell(_fmt_dt(run.get("started_at")), styles),
            ])
        t = Table(rows, colWidths=[2.5*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm, 4*cm])
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No ingestion run data available.", styles["FW_Body"]))

    story.append(Spacer(1, 0.5 * cm))
    story += _build_hotspots(rd, styles)
    return story


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report_pdf(report_data: dict, output_path: str) -> None:
    """Generate a professional PDF report and write it to *output_path*.

    This function is synchronous.  Call from ``asyncio.run_in_executor``
    when invoked from async code.

    Args:
        report_data: Dict returned by ``ReportService.gather_report_data``.
        output_path: Absolute or relative path for the output PDF file.

    Raises:
        RuntimeError: When ReportLab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install 'reportlab>=4.2.0'"
        )

    report_type = report_data.get("report_type", "on_demand")
    title_label = {
        "daily": "Daily Intelligence Report",
        "weekly": "Weekly Intelligence Report",
        "monthly": "Monthly Intelligence Report",
        "on_demand": "On-Demand Intelligence Report",
    }.get(report_type, "Intelligence Report")

    generated_at = _fmt_dt(report_data.get("generated_at"))

    styles = _styles()
    on_page = _make_on_page(title_label, generated_at)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=f"ForestWatch — {title_label}",
        author="ForestWatch Intelligence Platform",
        subject="Environmental Monitoring Report",
    )

    story: list = []

    # 1 — Cover
    story += _build_title_page(report_data, styles)
    story.append(PageBreak())

    # 2 — TOC
    story += _build_toc(styles)
    story.append(PageBreak())

    # 3 — Executive Summary
    story += _build_executive_summary(report_data, styles)
    story.append(PageBreak())

    # 4 — Intelligence Events
    story += _build_intelligence_events(report_data, styles)
    story.append(PageBreak())

    # 5 — Risk Analysis
    story += _build_risk_analysis(report_data, styles)
    story.append(PageBreak())

    # 6 — Top Anomalies
    story += _build_anomalies(report_data, styles)
    story.append(PageBreak())

    # 7 — Weather
    story += _build_weather(report_data, styles)
    story.append(PageBreak())

    # 8 — Historical
    story += _build_historical(report_data, styles)
    story.append(PageBreak())

    # 9 — Land Cover
    story += _build_land_cover(report_data, styles)
    story.append(PageBreak())

    # 10 — Notifications
    story += _build_notifications(report_data, styles)
    story.append(PageBreak())

    # 11 — System Status + Hotspots
    story += _build_system_status(report_data, styles)

    try:
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    except Exception as exc:
        logger.exception("PDF build failed: %s", exc)
        raise
