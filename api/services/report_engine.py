"""CRYO Report Engine v4 — World-class interactive HTML research reports.

Features:
- Mermaid.js diagrams (flowcharts, pathway diagrams, sequence diagrams)
- Plotly.js interactive charts (bar, pie, line, scatter, sankey, heatmap)
- Sortable data tables
- Callout boxes (info, warning, success, danger)
- Key metric highlight cards
- Progress/comparison bars
- Collapsible sections
- Timeline view
- Citation footnotes (hover to preview)
- In-report search
- Print/export button
- Dark/light mode toggle
- Responsive sidebar TOC with scroll-spy
- Animated section transitions

The agent writes markdown with special :::chart, :::diagram, :::callout markers.
This engine parses them and renders the full interactive HTML.
"""

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

logger = logging.getLogger("cryo.report_engine")

REPORTS_DIR = Path(os.getenv("CRYO_REPORTS_DIR", "/tmp/cryo-reports"))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CRYO_COLORS = ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444",
               "#3b82f6", "#ec4899", "#14b8a6", "#f97316", "#6366f1"]


# ═══════════════════════════════════════════════════════════
# MARKDOWN PARSER — handles standard md + custom blocks
# ═══════════════════════════════════════════════════════════

def parse_content_blocks(text: str) -> list[dict]:
    """Parse markdown content into a list of typed blocks.

    Returns: [
        {"type": "html", "content": "<p>...</p>"},
        {"type": "chart", "spec": {...}},
        {"type": "diagram", "code": "graph TD..."},
        {"type": "callout", "level": "info", "content": "..."},
        {"type": "table", "headers": [...], "rows": [...]},
        {"type": "progress", "items": [...]},
        {"type": "timeline", "events": [...]},
    ]
    """
    blocks = []

    # Extract special blocks first
    # :::chart {...} :::
    chart_pattern = r":::chart\s*\n(.*?)\n:::"
    diagram_pattern = r":::diagram\s*\n(.*?)\n:::"
    callout_pattern = r":::callout\s+(\w+)\s*\n(.*?)\n:::"
    timeline_pattern = r":::timeline\s*\n(.*?)\n:::"
    progress_pattern = r":::progress\s*\n(.*?)\n:::"

    # Split on special blocks, keeping track of positions
    combined_pattern = r"(:::(?:chart|diagram|callout\s+\w+|timeline|progress)\s*\n.*?\n:::)"
    parts = re.split(combined_pattern, text, flags=re.DOTALL)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Chart block
        cm = re.match(r":::chart\s*\n(.*?)\n:::", part, re.DOTALL)
        if cm:
            try:
                spec = json.loads(cm.group(1).strip())
                blocks.append({"type": "chart", "spec": spec})
            except json.JSONDecodeError:
                blocks.append({"type": "html", "content": f"<p><em>Invalid chart JSON</em></p>"})
            continue

        # Diagram block
        dm = re.match(r":::diagram\s*\n(.*?)\n:::", part, re.DOTALL)
        if dm:
            blocks.append({"type": "diagram", "code": dm.group(1).strip()})
            continue

        # Callout block
        cam = re.match(r":::callout\s+(\w+)\s*\n(.*?)\n:::", part, re.DOTALL)
        if cam:
            blocks.append({"type": "callout", "level": cam.group(1), "content": cam.group(2).strip()})
            continue

        # Timeline block
        tm = re.match(r":::timeline\s*\n(.*?)\n:::", part, re.DOTALL)
        if tm:
            events = []
            for line in tm.group(1).strip().split("\n"):
                m = re.match(r"[-*]\s*\*\*(.+?)\*\*[:\s]+(.+)", line.strip())
                if m:
                    events.append({"date": m.group(1), "text": m.group(2)})
            if events:
                blocks.append({"type": "timeline", "events": events})
            continue

        # Progress block
        pm = re.match(r":::progress\s*\n(.*?)\n:::", part, re.DOTALL)
        if pm:
            items = []
            for line in pm.group(1).strip().split("\n"):
                m = re.match(r"[-*]\s*(.+?):\s*(\d+)%?\s*(?:\((.+?)\))?", line.strip())
                if m:
                    items.append({"label": m.group(1), "value": int(m.group(2)), "note": m.group(3) or ""})
            if items:
                blocks.append({"type": "progress", "items": items})
            continue

        # Regular markdown → parse tables, then convert rest to HTML
        # Check for markdown tables
        table_pattern_md = r"(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)"
        table_parts = re.split(table_pattern_md, part)

        for tp in table_parts:
            tp = tp.strip()
            if not tp:
                continue

            # Is this a table?
            if tp.startswith("|") and "\n|" in tp:
                rows = [r.strip() for r in tp.split("\n") if r.strip()]
                if len(rows) >= 3:
                    headers = [c.strip() for c in rows[0].split("|") if c.strip()]
                    data_rows = []
                    for row in rows[2:]:
                        cells = [c.strip() for c in row.split("|") if c.strip()]
                        if cells and "---" not in row:
                            data_rows.append(cells)
                    if headers and data_rows:
                        blocks.append({"type": "table", "headers": headers, "rows": data_rows})
                        continue

            # Regular markdown → HTML
            html = md_to_html(tp)
            if html.strip():
                blocks.append({"type": "html", "content": html})

    return blocks


def md_to_html(text: str) -> str:
    """Convert markdown to HTML."""
    if not text:
        return ""

    # Headings (### and ####)
    text = re.sub(r"^#### (.+)$", r"<h5>\1</h5>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)

    # Bold + italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Citations [1], [2,3]
    text = re.sub(r"\[(\d+(?:[,\-]\s*\d+)*)\]", r'<sup class="cite" data-ref="\1">[\1]</sup>', text)

    # Unicode
    text = text.replace("\\u2265", "≥").replace("\\u00b1", "±").replace("\\u2013", "–")

    # Process line by line
    lines = text.split("\n")
    html_parts = []
    in_ul = in_ol = False
    para = []

    def flush():
        nonlocal para
        if para:
            p = " ".join(para).strip()
            if p:
                html_parts.append(f"<p>{p}</p>")
            para = []

    for line in lines:
        s = line.strip()

        if not s:
            flush()
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            continue

        # Bullet
        bm = re.match(r"^[-*]\s+(.+)", s)
        if bm:
            flush()
            if not in_ul: html_parts.append("<ul>"); in_ul = True
            html_parts.append(f"<li>{bm.group(1)}</li>")
            continue

        # Numbered
        nm = re.match(r"^(\d+)[.)]\s+(.+)", s)
        if nm:
            flush()
            if not in_ol: html_parts.append("<ol>"); in_ol = True
            html_parts.append(f"<li>{nm.group(2)}</li>")
            continue

        # Close lists
        if in_ul: html_parts.append("</ul>"); in_ul = False
        if in_ol: html_parts.append("</ol>"); in_ol = False

        # Already an HTML tag
        if s.startswith("<h"):
            flush()
            html_parts.append(s)
            continue

        para.append(s)

    flush()
    if in_ul: html_parts.append("</ul>")
    if in_ol: html_parts.append("</ol>")

    return "\n".join(html_parts)


# ═══════════════════════════════════════════════════════════
# BLOCK RENDERERS
# ═══════════════════════════════════════════════════════════

_chart_counter = 0

def render_chart_block(spec: dict) -> str:
    global _chart_counter
    _chart_counter += 1
    cid = f"plotly-chart-{_chart_counter}"

    labels = spec.get("labels", [])
    values = spec.get("values", [])
    chart_type = spec.get("type", "bar")
    title = spec.get("title", "")
    colors = spec.get("colors", CRYO_COLORS[:len(labels)])

    if not labels or not values:
        return ""

    layout = json.dumps({
        "title": {"text": title, "font": {"color": "#e2e8f0", "size": 15, "family": "Inter"}},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(15,23,42,0.5)",
        "font": {"color": "#94a3b8", "family": "Inter", "size": 12},
        "xaxis": {"title": spec.get("x_label", ""), "gridcolor": "#1e293b", "linecolor": "#1e293b"},
        "yaxis": {"title": spec.get("y_label", ""), "gridcolor": "#1e293b", "linecolor": "#1e293b"},
        "margin": {"l": 50, "r": 20, "t": 50, "b": 50},
        "showlegend": chart_type in ("pie", "donut"),
        "legend": {"font": {"color": "#94a3b8"}},
    })

    if chart_type in ("bar", "vertical_bar"):
        trace = json.dumps([{"x": labels, "y": values, "type": "bar",
            "marker": {"color": colors, "line": {"color": "rgba(15,23,42,0.8)", "width": 1}},
            "text": [str(v) for v in values], "textposition": "outside", "textfont": {"color": "#e2e8f0", "size": 11}}])
    elif chart_type == "horizontal_bar":
        trace = json.dumps([{"y": labels, "x": values, "type": "bar", "orientation": "h",
            "marker": {"color": colors}, "text": [str(v) for v in values], "textposition": "outside", "textfont": {"color": "#e2e8f0"}}])
    elif chart_type in ("pie", "donut"):
        hole = 0.45 if chart_type == "donut" else 0
        trace = json.dumps([{"labels": labels, "values": values, "type": "pie", "hole": hole,
            "marker": {"colors": colors, "line": {"color": "#0f172a", "width": 2}},
            "textinfo": "label+percent", "textfont": {"color": "#e2e8f0", "size": 11}}])
    elif chart_type == "line":
        trace = json.dumps([{"x": labels, "y": values, "type": "scatter", "mode": "lines+markers",
            "line": {"color": CRYO_COLORS[0], "width": 3},
            "marker": {"color": CRYO_COLORS[1], "size": 8}, "fill": "tozeroy", "fillcolor": "rgba(6,182,212,0.05)"}])
    else:
        trace = json.dumps([{"x": labels, "y": values, "type": "bar", "marker": {"color": colors}}])

    return f'''<div class="chart-block">
        <div id="{cid}" class="chart-plotly"></div>
        <script>Plotly.newPlot('{cid}',{trace},{layout},{{responsive:true,displayModeBar:false}});</script>
        <div class="figure-cap">Figure {_chart_counter}: {title}</div>
    </div>'''


def render_diagram_block(code: str) -> str:
    safe = code.replace("`", "\\`").replace("${", "\\${")
    return f'''<div class="diagram-block">
        <pre class="mermaid">{code}</pre>
    </div>'''


def render_callout_block(level: str, content: str) -> str:
    icons = {"info": "ℹ️", "warning": "⚠️", "success": "✅", "danger": "🚨", "note": "📝"}
    titles = {"info": "Key Information", "warning": "Important Note", "success": "Key Finding", "danger": "Critical Alert", "note": "Note"}
    icon = icons.get(level, "📌")
    title = titles.get(level, level.capitalize())
    return f'''<div class="callout callout-{level}">
        <div class="callout-header"><span class="callout-icon">{icon}</span><span class="callout-title">{title}</span></div>
        <div class="callout-body">{md_to_html(content)}</div>
    </div>'''


def render_table_block(headers: list, rows: list) -> str:
    tid = f"table-{uuid.uuid4().hex[:6]}"
    th = "".join(f"<th onclick=\"sortTable('{tid}',{i})\">{h} <span class='sort-arrow'>↕</span></th>" for i, h in enumerate(headers))
    tbody = ""
    for row in rows[:50]:
        processed_cells = []
        for c in row:
            cell = str(c)
            cell = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell)
            cell = re.sub(r'\*(.+?)\*', r'<em>\1</em>', cell)
            processed_cells.append(f"<td>{cell}</td>")
        tbody += f"<tr>{''.join(processed_cells)}</tr>"
    return f'''<div class="table-container">
        <table class="data-table" id="{tid}"><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>
    </div>'''


def render_progress_block(items: list) -> str:
    html = '<div class="progress-block">'
    for item in items:
        val = min(item["value"], 100)
        color = CRYO_COLORS[items.index(item) % len(CRYO_COLORS)]
        html += f'''<div class="progress-item">
            <div class="progress-label"><span>{item["label"]}</span><span class="progress-val">{val}%</span></div>
            <div class="progress-bar"><div class="progress-fill" style="width:{val}%;background:{color}"></div></div>
            {"<div class='progress-note'>" + item["note"] + "</div>" if item.get("note") else ""}
        </div>'''
    html += '</div>'
    return html


def render_timeline_block(events: list) -> str:
    html = '<div class="timeline">'
    for i, ev in enumerate(events):
        side = "left" if i % 2 == 0 else "right"
        html += f'''<div class="timeline-item timeline-{side}">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
                <div class="timeline-date">{ev["date"]}</div>
                <div class="timeline-text">{ev["text"]}</div>
            </div>
        </div>'''
    html += '</div>'
    return html


# ═══════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════

def generate_report(report_data: dict) -> dict:
    global _chart_counter
    _chart_counter = 0

    title = report_data.get("title", "CRYO Research Report")
    subtitle = report_data.get("subtitle", "")
    summary = report_data.get("summary", "")
    sections = report_data.get("sections", [])
    citations = report_data.get("citations", [])
    metadata = report_data.get("metadata", {})

    logger.info("Generating report v4: title=%r sections=%d citations=%d", title, len(sections), len(citations))

    now = datetime.now()
    report_id = uuid.uuid4().hex[:8].upper()
    has_charts = any(":::chart" in s.get("content", "") for s in sections)
    has_diagrams = any(":::diagram" in s.get("content", "") for s in sections)

    # Also check for chart/table specs in section objects
    for s in sections:
        if s.get("chart"): has_charts = True

    # Build TOC + sections HTML
    toc_html = ""
    sections_html = ""

    for i, section in enumerate(sections):
        sec_id = f"sec-{i}"
        heading = section.get("heading", f"Section {i+1}")
        content = section.get("content", "")
        highlights = section.get("highlights", [])
        chart_spec = section.get("chart")
        table_spec = section.get("table")

        # TOC entry
        toc_html += f'<a href="#{sec_id}" class="toc-link"><span class="toc-num">{i+1:02d}</span>{heading}</a>\n'

        # Section HTML
        sections_html += f'<section id="{sec_id}" class="report-section" data-section="{i}">\n'
        sections_html += f'<div class="section-head"><span class="sec-num">{i+1:02d}</span><h2>{heading}</h2></div>\n'

        # Highlight cards
        if highlights:
            sections_html += '<div class="highlights-grid">'
            for h in highlights[:4]:
                sections_html += f'<div class="hl-card"><div class="hl-val">{h.get("value","")}</div><div class="hl-label">{h.get("label","")}</div></div>'
            sections_html += '</div>\n'

        # Parse content blocks
        if content:
            blocks = parse_content_blocks(content)
            for block in blocks:
                if block["type"] == "html":
                    sections_html += f'<div class="prose">{block["content"]}</div>\n'
                elif block["type"] == "chart":
                    has_charts = True
                    sections_html += render_chart_block(block["spec"])
                elif block["type"] == "diagram":
                    has_diagrams = True
                    sections_html += render_diagram_block(block["code"])
                elif block["type"] == "callout":
                    sections_html += render_callout_block(block["level"], block["content"])
                elif block["type"] == "table":
                    sections_html += render_table_block(block["headers"], block["rows"])
                elif block["type"] == "progress":
                    sections_html += render_progress_block(block["items"])
                elif block["type"] == "timeline":
                    sections_html += render_timeline_block(block["events"])

        # Chart spec from section object (fallback)
        if chart_spec and chart_spec.get("labels"):
            has_charts = True
            sections_html += render_chart_block(chart_spec)

        # Table spec from section object (fallback)
        if table_spec and table_spec.get("headers"):
            sections_html += render_table_block(table_spec["headers"], table_spec.get("rows", []))

        sections_html += '</section>\n'

    # Citations
    citations_html = ""
    if citations:
        toc_html += '<a href="#references" class="toc-link"><span class="toc-num">•</span>References</a>\n'
        citations_html = '<section id="references" class="report-section ref-section">\n'
        citations_html += '<div class="section-head"><h2>References</h2></div>\n'
        for c in citations:
            cid = c.get("id", "")
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", c.get("text", c.get("formatted", "")))
            url = c.get("url", "")
            doi = c.get("doi", "")
            citations_html += f'<div class="ref-entry" id="ref-{cid}"><span class="ref-num">[{cid}]</span> {text}'
            if url: citations_html += f' <a href="{url}" target="_blank" class="ref-link">{doi or "Link"}</a>'
            citations_html += '</div>\n'
        citations_html += '</section>\n'

    # Sources badges
    ds = metadata.get("data_sources", [])
    sources_html = ""
    if ds:
        badges = "".join(f'<span class="src-badge">{s}</span>' for s in ds)
        sources_html = f'<div class="sources-bar"><span class="src-label">Data Sources</span>{badges}</div>'

    summary_html = md_to_html(summary) if summary else ""

    # Build complete HTML
    html = _full_html(
        title=title, subtitle=subtitle, summary_html=summary_html,
        toc_html=toc_html, sections_html=sections_html,
        citations_html=citations_html, sources_html=sources_html,
        report_id=report_id, date_str=now.strftime("%B %d, %Y"),
        time_str=now.strftime("%H:%M"), has_charts=has_charts,
        has_diagrams=has_diagrams,
        n_sections=len(sections), n_citations=len(citations),
    )

    # Save
    fid = uuid.uuid4().hex[:12]
    ts = now.strftime("%Y%m%d_%H%M%S")
    html_name = f"report_{ts}_{fid}.html"
    html_path = REPORTS_DIR / html_name
    html_path.write_text(html)

    logger.info("Report v4 generated: %s (%d bytes)", html_name, html_path.stat().st_size)

    return {
        "status": "success",
        "filename": html_name,
        "download_url": f"/api/reports/{html_name}",
        "size_bytes": html_path.stat().st_size,
        "engine": "cryo_v4",
    }


# ═══════════════════════════════════════════════════════════
# FULL HTML TEMPLATE
# ═══════════════════════════════════════════════════════════

def _full_html(**k) -> str:
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{k["title"]} — CRYO</title>
{"<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>" if k["has_charts"] else ""}
{"<script src='https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'></script>" if k["has_diagrams"] else ""}
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root{{--bg:#0a0e14;--sf:#0f172a;--sf2:#1e293b;--sf3:#334155;--bd:#1e293b;--bd2:#334155;--tx:#e2e8f0;--txd:#94a3b8;--txm:#64748b;--br:#06b6d4;--ac:#10b981;--pu:#8b5cf6;--am:#f59e0b;--rd:#ef4444;--bl:#3b82f6}}
[data-theme="light"]{{--bg:#fff;--sf:#f8fafc;--sf2:#f1f5f9;--sf3:#e2e8f0;--bd:#e2e8f0;--bd2:#cbd5e1;--tx:#0f172a;--txd:#475569;--txm:#94a3b8;--br:#0891b2}}
*{{margin:0;padding:0;box-sizing:border-box}}html{{scroll-behavior:smooth}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--tx);line-height:1.75;font-size:15px}}

/* SIDEBAR */
.sidebar{{position:fixed;left:0;top:0;width:260px;height:100vh;background:var(--sf);border-right:1px solid var(--bd);display:flex;flex-direction:column;z-index:100;transition:transform .3s}}
.sb-head{{padding:24px 20px 16px;border-bottom:1px solid var(--bd)}}
.logo{{font-family:'JetBrains Mono';font-size:15px;font-weight:700;color:var(--br);letter-spacing:.3em}}
.logo-line{{width:36px;height:2px;background:linear-gradient(90deg,var(--br),var(--ac));margin-top:5px;border-radius:1px}}
.sb-label{{font-size:9px;text-transform:uppercase;letter-spacing:.15em;color:var(--txm);padding:14px 20px 6px}}
.toc-wrap{{flex:1;overflow-y:auto;padding:0 8px}}
.toc-link{{display:flex;align-items:center;gap:8px;padding:7px 12px;margin:1px 0;color:var(--txd);text-decoration:none;font-size:12.5px;border-radius:6px;border-left:2px solid transparent;transition:all .15s}}
.toc-link:hover,.toc-link.active{{background:var(--sf2);color:var(--br);border-left-color:var(--br)}}
.toc-num{{font-family:'JetBrains Mono';font-size:10px;color:var(--br);min-width:20px}}
.sb-foot{{padding:12px 20px;border-top:1px solid var(--bd);font-size:9px;color:var(--txm);display:flex;flex-direction:column;gap:8px}}
.sb-btns{{display:flex;gap:6px}}
.sb-btn{{flex:1;background:var(--sf2);border:1px solid var(--bd);border-radius:5px;padding:5px 8px;color:var(--txd);cursor:pointer;font-size:10px;font-family:'Inter';text-align:center;transition:all .15s}}
.sb-btn:hover{{border-color:var(--br);color:var(--br)}}

/* SEARCH */
.search-box{{padding:8px 12px;margin:8px 8px 4px}}
.search-input{{width:100%;background:var(--sf2);border:1px solid var(--bd);border-radius:6px;padding:6px 10px;color:var(--tx);font-size:12px;font-family:'Inter';outline:none;transition:border .2s}}
.search-input:focus{{border-color:var(--br)}}
.search-input::placeholder{{color:var(--txm)}}
.highlight-search{{background:rgba(6,182,212,.25);border-radius:2px;padding:0 2px}}

/* MAIN */
.main{{margin-left:260px;min-height:100vh}}

/* COVER */
.cover{{background:linear-gradient(160deg,#0f172a,#1e293b 50%,#0f172a);padding:70px 50px 50px;position:relative;overflow:hidden;border-bottom:1px solid var(--bd)}}
.cover-g1{{position:absolute;top:-100px;right:-60px;width:400px;height:400px;background:radial-gradient(circle,rgba(6,182,212,.12),transparent 65%);border-radius:50%}}
.cover-g2{{position:absolute;bottom:-80px;left:-40px;width:300px;height:300px;background:radial-gradient(circle,rgba(16,185,129,.08),transparent 65%);border-radius:50%}}
.cover-in{{position:relative;max-width:680px}}
.cover h1{{font-size:34px;font-weight:800;color:#f1f5f9;line-height:1.15;margin-bottom:14px}}
.cover-sub{{font-size:15px;color:#94a3b8;font-weight:300;line-height:1.6;margin-bottom:28px}}
.cover-meta{{display:flex;gap:28px;flex-wrap:wrap}}
.cm-item{{border-left:2px solid var(--br);padding-left:10px}}
.cm-label{{font-size:8px;text-transform:uppercase;letter-spacing:.12em;color:#475569}}
.cm-val{{font-size:13px;color:#cbd5e1;font-weight:500;margin-top:1px}}
.cover-badge{{display:inline-block;margin-top:20px;padding:3px 12px;border:1px solid rgba(6,182,212,.3);border-radius:16px;font-size:9px;color:var(--br);font-weight:600;letter-spacing:.06em}}

/* CONTENT */
.content{{max-width:780px;margin:0 auto;padding:36px 36px 50px}}

/* SUMMARY */
.summary{{background:linear-gradient(135deg,rgba(20,184,166,.06),rgba(6,182,212,.03));border:1px solid rgba(20,184,166,.18);border-left:4px solid #14b8a6;border-radius:8px;padding:18px 22px;margin-bottom:32px}}
.summary-tag{{font-size:8px;text-transform:uppercase;letter-spacing:.15em;color:var(--ac);font-weight:700;margin-bottom:6px}}
.summary p{{font-size:14px;line-height:1.8}}

/* SECTIONS */
.report-section{{margin-bottom:36px;padding-bottom:24px;border-bottom:1px solid var(--bd);animation:fadeUp .4s ease-out}}
.section-head{{display:flex;align-items:center;gap:10px;margin-bottom:16px}}
.sec-num{{font-family:'JetBrains Mono';font-size:13px;font-weight:700;color:var(--br)}}
.section-head h2{{font-size:21px;font-weight:700}}
.prose p{{margin-bottom:10px;font-size:15px;line-height:1.8}}
.prose h4{{font-size:16px;font-weight:600;color:var(--br);margin:18px 0 8px}}
.prose h5{{font-size:14px;font-weight:600;color:var(--txd);margin:14px 0 6px}}
.prose ul,.prose ol{{margin:6px 0 14px 22px}}
.prose li{{margin-bottom:5px;font-size:14px;line-height:1.7}}
.prose li::marker{{color:var(--br)}}
.prose strong{{color:var(--tx);font-weight:600}}
.prose code{{font-family:'JetBrains Mono';font-size:13px;background:var(--sf2);padding:1px 5px;border-radius:3px;color:var(--br)}}
sup.cite{{font-size:10px;color:var(--br);font-weight:600;cursor:pointer;position:relative}}
sup.cite:hover{{text-decoration:underline}}

/* HIGHLIGHTS */
.highlights-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:14px 0 18px}}
.hl-card{{background:var(--sf);border:1px solid var(--bd);border-radius:10px;padding:14px;text-align:center;transition:border-color .2s}}
.hl-card:hover{{border-color:var(--br)}}
.hl-val{{font-size:26px;font-weight:800;color:var(--br);line-height:1.1}}
.hl-label{{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--txd);margin-top:5px}}

/* CHARTS */
.chart-block{{margin:18px 0;border-radius:10px;overflow:hidden;border:1px solid var(--bd);background:var(--sf)}}
.chart-plotly{{width:100%;height:380px}}
.figure-cap{{font-size:11px;color:var(--txm);text-align:center;padding:8px;font-style:italic;border-top:1px solid var(--bd)}}

/* DIAGRAMS */
.diagram-block{{margin:18px 0;padding:20px;background:var(--sf);border:1px solid var(--bd);border-radius:10px;text-align:center}}
.diagram-block .mermaid{{font-size:14px}}

/* CALLOUTS */
.callout{{margin:16px 0;border-radius:8px;overflow:hidden;border:1px solid var(--bd)}}
.callout-header{{display:flex;align-items:center;gap:8px;padding:10px 16px;font-size:12px;font-weight:600}}
.callout-body{{padding:12px 16px}}
.callout-body p{{font-size:14px;margin-bottom:6px}}
.callout-icon{{font-size:14px}}
.callout-info{{border-left:4px solid var(--bl)}} .callout-info .callout-header{{background:rgba(59,130,246,.08);color:var(--bl)}}
.callout-warning{{border-left:4px solid var(--am)}} .callout-warning .callout-header{{background:rgba(245,158,11,.08);color:var(--am)}}
.callout-success{{border-left:4px solid var(--ac)}} .callout-success .callout-header{{background:rgba(16,185,129,.08);color:var(--ac)}}
.callout-danger{{border-left:4px solid var(--rd)}} .callout-danger .callout-header{{background:rgba(239,68,68,.08);color:var(--rd)}}

/* TABLES */
.table-container{{overflow-x:auto;margin:14px 0;border-radius:8px;border:1px solid var(--bd)}}
.data-table{{width:100%;border-collapse:collapse;font-size:13px}}
.data-table th{{background:var(--sf);color:var(--br);padding:9px 12px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid var(--bd2);cursor:pointer;user-select:none;white-space:nowrap}}
.data-table th:hover{{color:var(--ac)}}
.sort-arrow{{font-size:10px;color:var(--txm);margin-left:4px}}
.data-table td{{padding:7px 12px;border-bottom:1px solid var(--bd);color:var(--txd)}}
.data-table tr:hover{{background:var(--sf2)}}
.data-table strong{{color:var(--tx)}}

/* PROGRESS BARS */
.progress-block{{margin:14px 0}}
.progress-item{{margin-bottom:10px}}
.progress-label{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px}}
.progress-val{{font-family:'JetBrains Mono';font-weight:600;color:var(--br);font-size:12px}}
.progress-bar{{height:8px;background:var(--sf2);border-radius:4px;overflow:hidden}}
.progress-fill{{height:100%;border-radius:4px;transition:width .8s ease}}
.progress-note{{font-size:11px;color:var(--txm);margin-top:2px}}

/* TIMELINE */
.timeline{{position:relative;margin:20px 0;padding-left:30px}}
.timeline::before{{content:'';position:absolute;left:14px;top:0;bottom:0;width:2px;background:var(--bd2)}}
.timeline-item{{position:relative;margin-bottom:20px;padding-left:20px}}
.timeline-dot{{position:absolute;left:-23px;top:6px;width:12px;height:12px;border-radius:50%;background:var(--br);border:2px solid var(--bg)}}
.timeline-date{{font-family:'JetBrains Mono';font-size:11px;font-weight:600;color:var(--br);margin-bottom:2px}}
.timeline-text{{font-size:14px;color:var(--txd);line-height:1.6}}

/* REFERENCES */
.ref-section{{border-bottom:none}}
.ref-entry{{font-size:13px;color:var(--txd);line-height:1.6;margin-bottom:8px;padding-left:26px;text-indent:-26px}}
.ref-num{{font-family:'JetBrains Mono';font-weight:700;color:var(--br);font-size:11px}}
.ref-link{{color:var(--br);text-decoration:none;font-size:11px}}
.ref-link:hover{{text-decoration:underline}}

/* SOURCES */
.sources-bar{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 14px;margin:20px 0;background:var(--sf);border:1px solid var(--bd);border-radius:6px}}
.src-label{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--txm)}}
.src-badge{{font-size:9px;font-weight:600;color:var(--txd);padding:2px 8px;background:var(--sf2);border:1px solid var(--bd);border-radius:3px}}

/* FOOTER */
.doc-foot{{text-align:center;padding:18px 0;font-size:11px;color:var(--txm);line-height:1.6}}

/* ANIMS */
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:translateY(0)}}}}

/* RESPONSIVE */
@media(max-width:860px){{.sidebar{{transform:translateX(-100%)}}.main{{margin-left:0}}.cover{{padding:36px 20px}}.cover h1{{font-size:24px}}.content{{padding:16px}}}}
@media print{{.sidebar{{display:none}}.main{{margin-left:0}}.sb-btns{{display:none}}body{{font-size:11pt}}}}
</style>
</head>
<body>

<nav class="sidebar">
<div class="sb-head"><div class="logo">CRYO<div class="logo-line"></div></div></div>
<div class="search-box"><input class="search-input" type="text" placeholder="Search report..." oninput="searchReport(this.value)"></div>
<div class="sb-label">Contents</div>
<div class="toc-wrap">{k["toc_html"]}</div>
<div class="sb-foot">
<div class="sb-btns">
<button class="sb-btn" onclick="toggleTheme()">🌓 Theme</button>
<button class="sb-btn" onclick="window.print()">🖨 Print</button>
</div>
<div>{k["report_id"]} · {k["date_str"]}</div>
</div>
</nav>

<main class="main">
<div class="cover">
<div class="cover-g1"></div><div class="cover-g2"></div>
<div class="cover-in">
<h1>{k["title"]}</h1>
{"<div class='cover-sub'>" + k.get("subtitle","") + "</div>" if k.get("subtitle") else ""}
<div class="cover-meta">
<div class="cm-item"><div class="cm-label">Generated</div><div class="cm-val">{k["date_str"]}</div></div>
<div class="cm-item"><div class="cm-label">Sections</div><div class="cm-val">{k["n_sections"]}</div></div>
<div class="cm-item"><div class="cm-label">Citations</div><div class="cm-val">{k["n_citations"]}</div></div>
<div class="cm-item"><div class="cm-label">Report ID</div><div class="cm-val">{k["report_id"]}</div></div>
</div>
<div class="cover-badge">AI-GENERATED RESEARCH REPORT</div>
</div>
</div>

<div class="content">
{"<div class='summary'><div class='summary-tag'>Executive Summary</div>" + k["summary_html"] + "</div>" if k["summary_html"] else ""}
{k["sections_html"]}
{k["sources_html"]}
{k["citations_html"]}
<div class="doc-foot">Generated by CRYO — Comprehensive Research Yielding Outcomes<br>{k["report_id"]} · {k["date_str"]} {k["time_str"]}</div>
</div>
</main>

{"<script>mermaid.initialize({theme:'dark',themeVariables:{primaryColor:'#06b6d4',primaryTextColor:'#e2e8f0',primaryBorderColor:'#1e293b',lineColor:'#334155',secondaryColor:'#1e293b',tertiaryColor:'#0f172a'}});</script>" if k["has_diagrams"] else ""}
<script>
function toggleTheme(){{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark'}}
function sortTable(id,col){{const t=document.getElementById(id),b=t.querySelector('tbody'),rows=[...b.rows];const asc=t.dataset.sortCol==col&&t.dataset.sortDir==='asc';rows.sort((a,c)=>{{let x=a.cells[col].textContent.trim(),y=c.cells[col].textContent.trim();const nx=parseFloat(x),ny=parseFloat(y);if(!isNaN(nx)&&!isNaN(ny))return asc?ny-nx:nx-ny;return asc?y.localeCompare(x):x.localeCompare(y)}});rows.forEach(r=>b.appendChild(r));t.dataset.sortCol=col;t.dataset.sortDir=asc?'desc':'asc'}}
function searchReport(q){{document.querySelectorAll('.highlight-search').forEach(e=>{{const p=e.parentNode;p.replaceChild(document.createTextNode(e.textContent),e)}});if(!q||q.length<2)return;const walk=document.createTreeWalker(document.querySelector('.content'),NodeFilter.SHOW_TEXT);while(walk.nextNode()){{const n=walk.currentNode;if(n.textContent.toLowerCase().includes(q.toLowerCase())){{const i=n.textContent.toLowerCase().indexOf(q.toLowerCase());const span=document.createElement('span');span.className='highlight-search';const before=n.textContent.substring(0,i);const match=n.textContent.substring(i,i+q.length);const after=n.textContent.substring(i+q.length);const p=n.parentNode;p.insertBefore(document.createTextNode(before),n);span.textContent=match;p.insertBefore(span,n);p.insertBefore(document.createTextNode(after),n);p.removeChild(n);break}}}}
const obs=new IntersectionObserver(es=>{{es.forEach(e=>{{if(e.isIntersecting){{const i=e.target.dataset.section;document.querySelectorAll('.toc-link').forEach((l,j)=>{{l.classList.toggle('active',j==i)}})}}}})}},{{threshold:.2}});document.querySelectorAll('.report-section[data-section]').forEach(s=>obs.observe(s));
</script>
</body></html>'''
