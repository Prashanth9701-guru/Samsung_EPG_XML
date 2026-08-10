"""
Summary_report.py
-----------------
Generates a polished HTML summary report strictly from the finalised Excel
report file (source of truth).  Never reads Validation_Output directly.

Public API
----------
    summary_report_writer(excel_path: str) -> str
        Reads the Excel file at *excel_path*, builds the HTML summary, writes
        it to the same directory, and returns the HTML file path.

Filename format
---------------
    Summary-report_<json_name>_<excel_report_basename>.html
"""

import ast
import base64
import io
import os
import re
import html as _html
from collections import defaultdict, OrderedDict
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, Alignment

#from Input import JSON_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_NORM = {
    'passed': 'Passed', 'passes': 'Passed',
    'failed': 'Failed',
    'not tested': 'Not Tested',
    'observation': 'Observation',
}


def _norm(status):
    return _STATUS_NORM.get(str(status).strip().lower(), str(status).strip())


def _module_overall(rows):
    """
    Priority:
        Failed            – any Failed row present
        Passed with caveats – no Failed, but Not Tested or Observation present
        Passed            – all rows are Passed
    """
    statuses = {_norm(r['Status']) for r in rows}
    if 'Failed' in statuses:
        return 'Failed'
    if 'Not Tested' in statuses or 'Observation' in statuses:
        return 'Passed with caveats'
    return 'Passed'


def _cls(status):
    return {
        'Passed':             'passed',
        'Failed':             'failed',
        'Not Tested':         'nt',
        'Observation':        'obs',
        'Passed with caveats': 'caveats',
    }.get(status, 'nt')


def _esc(v):
    return _html.escape(str(v)) if v is not None else ''


def _truncate(text, limit=400):
    t = str(text).strip()
    return t[:limit] + ' …' if len(t) > limit else t


#def _json_name():
    """Derive a short identifier from the JSON_URL (or file path)."""
    #try:
        #return os.path.splitext(os.path.basename(JSON_URL.rstrip('/')))[0]
    #except Exception:
        #return 'feed'


# ---------------------------------------------------------------------------
# CSS  (plain string — kept separate to avoid f-string brace-escaping issues)
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
               'Helvetica Neue', Arial, sans-serif;
  background: #F1F5F9; color: #1E293B; line-height: 1.6; font-size: 14px;
}

/* ── Hero ── */
.hero {
  background: linear-gradient(140deg, #0F172A 0%, #1E293B 55%, #1a3a5c 100%);
  padding: 52px 48px 44px; color: #fff;
}
.hero-inner        { max-width: 1080px; margin: 0 auto; }
.hero-eyebrow      { font-size: 11px; text-transform: uppercase; letter-spacing: 2px;
                     color: #64748B; margin-bottom: 12px; font-weight: 600; }
.hero-title        { font-size: 32px; font-weight: 800; letter-spacing: -.5px; }
.hero-meta         { font-size: 13px; color: #94A3B8; margin-top: 10px;
                     display: flex; flex-wrap: wrap; gap: 20px; align-items: center; }
.hero-meta span    { display: flex; align-items: center; gap: 6px; }
.hero-pill         { display: inline-flex; align-items: center; gap: 9px;
                     margin-top: 22px; border-radius: 30px; padding: 8px 20px;
                     font-size: 13px; font-weight: 700; letter-spacing: .2px;
                     border: 1px solid transparent; }
.hero-dot          { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }

/* ── Layout ── */
.container { max-width: 1080px; margin: 0 auto; padding: 36px 24px 52px; }

/* ── Base card ── */
.card {
  background: #fff; border-radius: 14px; padding: 26px 30px;
  box-shadow: 0 1px 2px rgba(0,0,0,.06), 0 6px 24px rgba(0,0,0,.06);
  margin-bottom: 24px;
}
.card-label { font-size: 11px; font-weight: 700; text-transform: uppercase;
              letter-spacing: 1.2px; color: #94A3B8; margin-bottom: 18px; }

/* ── Inputs ── */
.input-grid              { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }
.input-item label        { display: block; font-size: 11px; text-transform: uppercase;
                           letter-spacing: .8px; color: #94A3B8; font-weight: 700; }
.input-item .val         { display: block; font-size: 13px; font-weight: 500; color: #1E293B;
                           margin-top: 5px; word-break: break-all; }

/* ── KPI row ── */
.kpi-grid    { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px;
               margin-bottom: 32px; }
.kpi-card    { background: #fff; border-radius: 14px; padding: 22px 14px 20px; text-align: center;
               box-shadow: 0 1px 2px rgba(0,0,0,.06), 0 5px 18px rgba(0,0,0,.06); }
.kpi-value   { font-size: 40px; font-weight: 800; line-height: 1.1; }
.kpi-label   { font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
               color: #64748B; margin-top: 7px; font-weight: 700; }
.kpi-sub     { font-size: 11px; color: #94A3B8; margin-top: 3px; }

/* ── Status badges ── */
.badge         { display: inline-block; padding: 3px 11px; border-radius: 20px;
                 font-size: 11px; font-weight: 700; letter-spacing: .3px;
                 border: 1px solid transparent; white-space: nowrap; }
.badge-passed  { color: #166534; background: #DCFCE7; border-color: #86EFAC; }
.badge-failed  { color: #991B1B; background: #FEE2E2; border-color: #FCA5A5; }
.badge-nt      { color: #1E40AF; background: #DBEAFE; border-color: #93C5FD; }
.badge-obs     { color: #854D0E; background: #FEF9C3; border-color: #FDE68A; }
.badge-caveats { color: #92400E; background: #FEF3C7; border-color: #FCD34D; }

/* ── Module cards ── */
.module-card          { background: #fff; border-radius: 14px; overflow: hidden;
                        margin-bottom: 14px;
                        box-shadow: 0 1px 2px rgba(0,0,0,.06), 0 5px 18px rgba(0,0,0,.06); }
.module-card.bar-passed  { border-left: 5px solid #22C55E; }
.module-card.bar-failed  { border-left: 5px solid #EF4444; }
.module-card.bar-nt      { border-left: 5px solid #3B82F6; }
.module-card.bar-obs     { border-left: 5px solid #F59E0B; }
.module-card.bar-caveats { border-left: 5px solid #F59E0B; }

.module-header  { display: flex; align-items: center; justify-content: space-between;
                  padding: 18px 24px; border-bottom: 1px solid #F8FAFC; }
.module-name    { font-size: 15px; font-weight: 700; }
.module-meta-r  { display: flex; align-items: center; gap: 12px; }
.check-count    { font-size: 12px; color: #94A3B8; font-weight: 500; }

.module-body    { padding: 18px 24px 20px; }

/* ── Stat pills ── */
.stats-row  { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.stat-pill  { display: inline-flex; align-items: center; gap: 6px;
              padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; }
.stat-dot   { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

/* ── Progress bar ── */
.prog-wrap  { background: #F1F5F9; border-radius: 8px; height: 5px; overflow: hidden; }
.prog-fill  { height: 100%; border-radius: 8px; }
.prog-label { font-size: 11px; color: #94A3B8; text-align: right; margin-top: 5px; }

/* ── Scenario details ── */
details         { margin-top: 12px; border-radius: 8px; overflow: hidden; }
details summary { cursor: pointer; font-size: 11px; font-weight: 700;
                  text-transform: uppercase; letter-spacing: .7px; padding: 9px 14px;
                  display: flex; align-items: center; gap: 8px;
                  user-select: none; list-style: none; }
details summary::-webkit-details-marker { display: none; }
.sum-failed { background: #FEF2F2; color: #991B1B; }
.sum-obs    { background: #FFFBEB; color: #92400E; }
.sum-nt     { background: #EFF6FF; color: #1E40AF; }
.chevron    { font-size: 9px; transition: transform .18s ease; flex-shrink: 0; }
details[open] .chevron { transform: rotate(90deg); }

.sc-list         { list-style: none; padding: 0 0 4px 0; }
.sc-list li      { padding: 9px 16px 9px 14px; font-size: 13px; border-left: 3px solid; }
.sc-list li + li { border-top: 1px solid transparent; }
.sc-list li.fail { background: #FFF8F8; border-color: #FCA5A5; }
.sc-list li.obs  { background: #FFFEF5; border-color: #FDE68A; }
.sc-list li.nt   { background: #F5F9FF; border-color: #93C5FD; }
.sc-name   { font-weight: 600; color: #1E293B; }
.sc-result { font-size: 11.5px; color: #64748B; margin-top: 3px;
             word-break: break-word; white-space: pre-wrap; line-height: 1.5; }

/* ── Failure Summary ── */
.fs-list         { margin-top: 4px; }
.fs-item         { border-radius: 8px; overflow: hidden; margin-bottom: 6px; }
.fs-summary      { display: flex; align-items: center; gap: 8px; padding: 10px 14px;
                   background: #FFF8F8; cursor: pointer; user-select: none; list-style: none; }
.fs-summary::-webkit-details-marker { display: none; }
.fs-sc-name      { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: #1E293B; }
.fs-id-badge     { flex-shrink: 0; background: #FEE2E2; color: #991B1B;
                   border: 1px solid #FCA5A5; border-radius: 20px;
                   padding: 2px 10px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.fs-ids-body     { padding: 8px 16px 10px 36px; font-size: 12px; color: #475569;
                   background: #FFF2F2; border-left: 3px solid #FCA5A5;
                   word-break: break-all; line-height: 1.6; }
.fs-none         { font-size: 13px; color: #94A3B8; font-style: italic; }

/* ── Failure Summary table ── */
.fs-table          { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px;
                     table-layout: fixed; }
.fs-table th       { padding: 9px 12px; text-align: left; font-size: 11px; font-weight: 700;
                     text-transform: uppercase; letter-spacing: .8px; color: #64748B;
                     background: #F8FAFC; border-bottom: 2px solid #E2E8F0; }
.fs-table th.fs-col-id     { text-align: center; width: 18%; }
.fs-table th.fs-col-field  { width: 14%; }
.fs-table th.fs-col-issues { width: 68%; }
.fs-table td       { padding: 9px 12px; border-bottom: 1px solid #F1F5F9; vertical-align: top;
                     overflow-wrap: anywhere; }
.fs-table td.fs-col-id    { text-align: left; font-weight: 700; color: #991B1B;
                             font-size: 12px; font-family: 'Courier New', monospace;
                             word-break: break-all; white-space: normal; max-width: 0; }
.fs-table td.fs-col-field { color: #475569; font-weight: 600;
                             word-break: break-word; max-width: 0; }
.fs-table td.fs-col-issues { color: #1E293B; word-break: break-word; white-space: normal;
                             line-height: 1.6; max-width: 0; }
.fs-table tr:last-child td { border-bottom: none; }
.fs-table tbody tr:hover td { background: #FFF8F8; }

/* ── Coverage card ── */
.cov-grid   { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.cov-section { }
.cov-title  { font-size: 12px; font-weight: 700; text-transform: uppercase;
               letter-spacing: .8px; color: #475569; margin-bottom: 12px;
               display: flex; align-items: center; gap: 8px; }
.cov-title-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cov-table  { width: 100%; border-collapse: collapse; font-size: 12px; }
.cov-table td { padding: 5px 8px; border-bottom: 1px solid #F1F5F9; }
.cov-table td:first-child { color: #64748B; font-weight: 500; width: 60%; }
.cov-table td:last-child  { font-weight: 700; text-align: right; color: #1E293B; }
.cov-reasons { margin-top: 10px; }
.cov-reasons-label { font-size: 11px; font-weight: 600; color: #94A3B8;
                     text-transform: uppercase; letter-spacing: .6px; margin-bottom: 6px; }
.cov-reason-pill { display: inline-flex; align-items: center; gap: 5px; margin: 2px 3px 2px 0;
                   padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
                   background: #FEE2E2; color: #991B1B; border: 1px solid #FCA5A5; }
.cov-skip-pill  { background: #FEF9C3; color: #854D0E; border-color: #FDE68A; }
.cov-none { font-size: 12px; color: #94A3B8; font-style: italic; }

/* ── Open Report button ── */
.open-report-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; background: #1E293B; color: #fff !important;
  border-radius: 10px; font-size: 13px; font-weight: 700; letter-spacing: .3px;
  text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,.18);
  transition: background .15s ease, box-shadow .15s ease;
}
.open-report-btn:hover { background: #334155; box-shadow: 0 4px 14px rgba(0,0,0,.22); }
.btn-row { text-align: right; margin-bottom: 22px; }

/* ── Module blurb ── */
.mod-blurb {
  background: #F8FAFC; border-radius: 8px; padding: 11px 14px;
  margin-bottom: 14px; font-size: 13px; line-height: 1.65;
  border: 1px solid #E2E8F0;
}
.mod-blurb-item { display: block; }
.mod-blurb-item + .mod-blurb-item { margin-top: 4px; }

/* ── Section heading ── */
.section-head { font-size: 11px; font-weight: 700; text-transform: uppercase;
                letter-spacing: 1.2px; color: #94A3B8;
                margin-bottom: 14px; margin-top: 4px; }

/* ── Footer ── */
.footer { text-align: center; padding: 36px 24px 28px; color: #94A3B8; font-size: 12px;
          border-top: 1px solid #E2E8F0; margin-top: 8px; }
.footer strong { color: #64748B; }

@media (max-width: 720px) {
  .kpi-grid   { grid-template-columns: repeat(2, 1fr); }
  .input-grid { grid-template-columns: 1fr; }
  .hero       { padding: 32px 20px 28px; }
  .container  { padding: 20px 16px; }
}

/* ── Download button ── */
.dl-btn { display:inline-block; margin-left:14px; padding:4px 14px; font-size:12px;
          font-weight:600; color:#fff; background:#3B82F6; border:none; border-radius:6px;
          cursor:pointer; vertical-align:middle; line-height:1.6; }
.dl-btn:hover { background:#2563EB; }
"""

# ---------------------------------------------------------------------------
# HTML component builders
# ---------------------------------------------------------------------------

# def _kpi_card(value, label, color, border_top, sub=''):
#     sub_html = f'<div class="kpi-sub">{_esc(sub)}</div>' if sub else ''
#     return (
#         f'<div class="kpi-card" style="border-top:3px solid {border_top};">'
#         f'<div class="kpi-value" style="color:{color};">{value}</div>'
#         f'<div class="kpi-label">{label}</div>'
#         f'{sub_html}'
#         f'</div>'
#     )


def _stat_pill(count, label, dot, text, bg):
    return (
        f'<span class="stat-pill" style="background:{bg};color:{text};">'
        f'<span class="stat-dot" style="background:{dot};"></span>'
        f'{count} {label}</span>'
    )


def _scenario_li(row, css_class):
    actual = _truncate(row.get('Actual Result', '') or '')
    actual_html = f'<div class="sc-result">{_esc(actual)}</div>' if actual else ''
    return (
        f'<li class="{css_class}">'
        f'<div class="sc-name">{_esc(row.get("Scenario", ""))}</div>'
        f'{actual_html}'
        f'</li>'
    )


def _detail_section(items, label, css_class, sum_cls, open_attr=''):
    if not items:
        return ''
    lis = ''.join(_scenario_li(r, css_class) for r in items)
    return (
        f'<details {open_attr}>'
        f'<summary class="{sum_cls}">'
        f'<span class="chevron">&#9658;</span>'
        f'&nbsp;{len(items)} {label}'
        f'</summary>'
        f'<ul class="sc-list">{lis}</ul>'
        f'</details>'
    )


def _module_blurb(rows, overall, mc):
    """Short stakeholder-friendly summary shown at the top of each module body."""
    parts = []

    if mc['Failed'] > 0:
        parts.append(
            f'<span class="mod-blurb-item" style="color:#991B1B;font-weight:700;">'
            f'&#10007;&nbsp;{mc["Failed"]} check(s) failed</span>'
        )

    if overall == 'Passed with caveats':
        caveat_parts = []
        if mc['Not Tested'] > 0:
            caveat_parts.append(f'{mc["Not Tested"]} not tested')
        if mc['Observation'] > 0:
            caveat_parts.append(f'{mc["Observation"]} observation(s)')
        parts.append(
            f'<span class="mod-blurb-item" style="color:#92400E;font-weight:600;">'
            f'&#9432;&nbsp;{", ".join(caveat_parts)} &mdash; optional checks, no blocking failures.</span>'
        )

    if overall == 'Passed':
        parts.append(
            '<span class="mod-blurb-item" style="color:#166534;font-weight:600;">'
            '&#10003;&nbsp;All checks passed.</span>'
        )

    # Grouped not-tested reasons (top 3 unique patterns)
    nt_rows = [r for r in rows if _norm(r['Status']) == 'Not Tested']
    if nt_rows:
        reason_counts = defaultdict(int)
        for r in nt_rows:
            raw = str(r.get('Actual Result', '') or '').strip()
            # Use first 80 chars as the reason key to group similar messages
            key = raw[:80] + ('…' if len(raw) > 80 else '')
            if key:
                reason_counts[key] += 1
        if reason_counts:
            top = sorted(reason_counts.items(), key=lambda x: -x[1])[:3]
            reasons_html = '&nbsp;&middot;&nbsp;'.join(
                f'{_esc(r)} <em>({c})</em>' for r, c in top
            )
            parts.append(
                f'<span class="mod-blurb-item" style="font-size:12px;color:#64748B;">'
                f'&#9702;&nbsp;Not-tested reasons: {reasons_html}</span>'
            )

    if not parts:
        return ''
    return '<div class="mod-blurb">' + ''.join(parts) + '</div>'


def _module_card(mod_name, rows):
    overall  = _module_overall(rows)
    bar_cls  = f'bar-{_cls(overall)}'

    mc = defaultdict(int)
    for r in rows:
        mc[_norm(r['Status'])] += 1

    pills = (
        _stat_pill(mc['Passed'],     'Passed',      '#22C55E', '#166534', '#DCFCE7') +
        _stat_pill(mc['Failed'],     'Failed',      '#EF4444', '#991B1B', '#FEE2E2') +
        _stat_pill(mc['Not Tested'], 'Not Tested',  '#3B82F6', '#1E40AF', '#DBEAFE') +
        _stat_pill(mc['Observation'], 'Observation','#F59E0B', '#854D0E', '#FEF9C3')
    )

    fail_rows = [r for r in rows if _norm(r['Status']) == 'Failed']
    obs_rows  = [r for r in rows if _norm(r['Status']) == 'Observation']
    nt_rows   = [r for r in rows if _norm(r['Status']) == 'Not Tested']

    details_html = (
        _detail_section(fail_rows, 'Failed',       'fail', 'sum-failed', 'open') +
        _detail_section(obs_rows,  'Observations', 'obs',  'sum-obs') +
        _detail_section(nt_rows,   'Not Tested',   'nt',   'sum-nt')
    )

    pass_pct   = int(mc['Passed'] / len(rows) * 100) if rows else 0
    prog_color = '#22C55E' if pass_pct >= 80 else ('#F59E0B' if pass_pct >= 50 else '#EF4444')

    blurb = _module_blurb(rows, overall, mc)

    return (
        f'<div class="module-card {bar_cls}">'
        f'<div class="module-header">'
        f'<span class="module-name">{_esc(mod_name)}</span>'
        f'<div class="module-meta-r">'
        f'<span class="check-count">{len(rows)} checks</span>'
        f'<span class="badge badge-{_cls(overall)}">{_esc(overall)}</span>'
        f'</div>'
        f'</div>'
        f'<div class="module-body">'
        f'{blurb}'
        f'<div class="stats-row">{pills}</div>'
        f'<div class="prog-wrap">'
        f'<div class="prog-fill" style="width:{pass_pct}%;background:{prog_color};"></div>'
        f'</div>'
        f'<div class="prog-label">{pass_pct}% passed</div>'
        f'{details_html}'
        f'</div>'
        f'</div>'
    )

# ---------------------------------------------------------------------------
# Excel reader
# ---------------------------------------------------------------------------

def _read_excel(excel_path):
    """Read the Excel report and return a list of row dicts."""
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h is not None else '' for h in rows[0]]
    data = []
    for row in rows[1:]:
        d = {headers[i]: (row[i] if row[i] is not None else '') for i in range(len(headers))}
        data.append(d)
    return data

# ---------------------------------------------------------------------------
# Failure Summary helpers
# ---------------------------------------------------------------------------

_ID_SKIP_WORDS = frozenset([
    'true', 'false', 'none', 'null', 'nan', 'ok', 'not', 'tested',
    'passed', 'failed', 'observation', 'error', 'type', 'format',
    'string', 'status', 'code', 'available', '',
])


def _extract_ids(actual_result):
    """
    Conservative extraction of asset IDs from an Actual Result string.

    Strategies (in order):
      1. Content inside {} and [] — handles set literals and dict key-value pairs.
         For dict-like items (containing ':'), only the part before ':' is kept.
      2. Explicit  id=<value>  or  asset_id=<value>  patterns anywhere in the text.

    Returns a set of ID strings (deduplicated).
    """
    if not actual_result:
        return set()

    text = str(actual_result)
    ids = set()

    # Strategy 1: extract items from {} / [] blocks
    for block_m in re.finditer(r'[{\[](.*?)[}\]]', text, re.DOTALL):
        block_content = block_m.group(1)
        for token in block_content.split(','):
            token = token.strip()
            # Dict entry — take the key (before the first ':')
            if ':' in token:
                token = token.split(':', 1)[0].strip()
            # Strip surrounding quotes and whitespace
            token = token.strip("'\" \t\n\r")
            if token and token.lower() not in _ID_SKIP_WORDS:
                if re.match(r'^[A-Za-z0-9][\w\-]*$', token):
                    ids.add(token)

    # Strategy 2: explicit id= / asset_id= patterns
    for m in re.finditer(
        r'\b(?:asset_id|id)\s*=\s*[\'"]?([A-Za-z0-9][\w\-]*)[\'"]?',
        text, re.IGNORECASE
    ):
        candidate = m.group(1)
        if candidate.lower() not in _ID_SKIP_WORDS:
            ids.add(candidate)

    return ids


# Words that appear as dict *values* in node-validation results and must never
# be mistaken for asset IDs or module labels.
_FIELD_SKIP_WORDS = frozenset([
    'rating', 'genres', 'movies', 'tvspecials', 'tvspecial',
    'series', 'episodes', 'episode', 'shortformvideos', 'shortformvideo',
    'language', 'thumbnail', 'title', 'description', 'tags',
    'type', 'format', 'status', 'code', 'available', '',
])


# ---------------------------------------------------------------------------
# Scenario exclusion list  (HTML rendering only — Excel is never modified)
# ---------------------------------------------------------------------------

_EXCLUDED_SCENARIOS = frozenset([
    # 'Validate quality of the Branded Thumbnail',
    # 'Validate Title treatment of Branded Thumbnail',
    # 'Validate Channel_Level_Title Language',
    # 'Validate Content_Level Language is matching with Channel_Level Language',
    # 'Validate Channel_Long_Description Language is matching with Channel_Level_Language',
    # 'Validate Channel_Short_Description Language is matching with Channel_Level_Language',
    # 'Validate Title treatment of Channel_Thumbnail',
    # 'Validate quality of the Episode_Thumbnail',
    # 'Validate Title treatment of Episode_Thumbnail',
    # 'Validate quality of the Series_Thumbnail',
    # 'Validate Title treatment of Series_Thumbnail',
    # 'Validate Series_Short_Description Language is matching with Channel_Level_Language',
    # 'Validate quality of the Movie_Thumbnail',
    # 'Validate Title treatment of Movie_Thumbnail',
    # 'Validate Movie_Short_Description Language is matching with Channel_Level_Language',
    # 'Validate quality of the shortFormVideos_Thumbnail',
    # 'Validate Title treatment of shortFormVideos_Thumbnail',
    # 'Validate quality of the tvSpecials_Thumbnail',
    # 'Validate Title treatment of tvSpecials_Thumbnail',
    # 'Validate tvSpecials_Short_Description Language is matching with Channel_Level_Language',
])


def _filter_rows(rows):
    """Return rows with excluded scenarios removed (HTML rendering only)."""
    return [
        r for r in rows
        if str(r.get('Scenario', '') or '').strip() not in _EXCLUDED_SCENARIOS
    ]


def _parse_asset_ids_column(text):
    """
    Parse the 'Asset IDs' column value into a set of display identifiers.

    Priority (asset IDs first, module label fallback):
      1. Real asset IDs — dict keys that contain at least one digit and match
         an alphanumeric/hyphen identifier pattern, e.g. m54745, BellMedia-2931555-S3E12.
      2. Module labels — if no real asset IDs are found, the dict key is treated
         as a module-level label (multi-word or contains "Nodes").
         Duplicate trailing "Nodes" is normalised:
           "JSON Nodes Nodes"       → "JSON Nodes"
           "Live Feeds Nodes Nodes" → "Live Feeds Nodes"

    Plain comma-separated values (no braces) are also supported as a fallback
    for simple "id1, id2" lists produced by the new reporting schema.

    Returns a set of strings (deduplicated).
    """
    if not text:
        return set()

    raw_keys = []

    # Extract top-level dict keys: the segment before the first ':' inside each
    # outermost { } that does not itself contain { or } before the colon.
    # This correctly handles both:
    #   {'m54745': ['rating', 'rating']},{'m54629': ['rating']}
    #   {JSON Nodes Nodes : {'movies', 'tvSpecials'}}
    for m in re.finditer(r'\{([^{}:]*?)\s*:', text):
        key = m.group(1).strip().strip("'\" \t{}[]")
        if key:
            raw_keys.append(key)

    # Fallback: plain comma-separated list with no brace-dict structure
    if not raw_keys and '{' not in text and '[' not in text:
        for token in re.split(r'[,\n]+', text):
            token = token.strip()
            if ':' in token:
                token = token.split(':', 1)[0].strip()
            token = token.strip("'\" \t")
            if token:
                raw_keys.append(token)

    asset_ids = []
    module_labels = []

    for key in raw_keys:
        if not key:
            continue
        key_norm = key.lower().replace(' ', '').replace('_', '')
        if key_norm in _FIELD_SKIP_WORDS or key_norm in _ID_SKIP_WORDS:
            continue

        # Real asset ID: single word (no spaces), alphanumeric/hyphens, contains a digit
        if re.match(r'^[A-Za-z0-9][\w\-]*$', key) and re.search(r'\d', key):
            asset_ids.append(key)
        # Module label: multi-word phrase or contains "Nodes" keyword
        elif ' ' in key or re.search(r'\bNodes?\b', key, re.IGNORECASE):
            label = re.sub(r'\bNodes\b\s+\bNodes\b', 'Nodes', key, flags=re.IGNORECASE).strip()
            module_labels.append(label)
        # Single-word, no digit — only include if it survived the skip-word filter
        elif re.match(r'^[A-Za-z0-9][\w\-]*$', key):
            asset_ids.append(key)

    # Priority: return real asset IDs; fall back to module labels
    result = asset_ids if asset_ids else module_labels

    # Deduplicate while preserving first-seen order, then return as a set
    seen: set = set()
    out = []
    for item in result:
        if item not in seen:
            seen.add(item)
            out.append(item)

    return set(out)


# ---------------------------------------------------------------------------
# Module label cleanup for Failure Summary column 2
# ---------------------------------------------------------------------------

_MODULE_CLEAN_MAP = [
    (re.compile(r'JSON\s+Nodes',                              re.IGNORECASE), 'JSON'),
    (re.compile(r'Live\s+Feeds?\s+Nodes',                     re.IGNORECASE), 'Live Feed'),
    (re.compile(r'Series\s+Nodes',                            re.IGNORECASE), 'Series'),
    (re.compile(r'Episodes?\s+Nodes',                         re.IGNORECASE), 'Episodes'),
    (re.compile(r'Schedule\s+Nodes',                          re.IGNORECASE), 'Schedule'),
    (re.compile(r'Content[_\s]+Nodes',                        re.IGNORECASE), 'Content'),
    (re.compile(r'Movies?\s+Nodes',                           re.IGNORECASE), 'Movies'),
    (re.compile(r'TV[_\s]+Specials?\s+Nodes',                 re.IGNORECASE), 'TV Specials'),
    (re.compile(r'Short[_\s]+Form[_\s]*Videos?\s+Nodes',      re.IGNORECASE), 'Short-Form Videos'),
    (re.compile(r'Seasons?\s+Nodes',                          re.IGNORECASE), 'Seasons'),
]


def _clean_module_label(module_raw):
    """Map a raw Module column value to a clean label for column 2 of the Failure table."""
    raw = str(module_raw or '').strip()
    for pattern, label in _MODULE_CLEAN_MAP:
        if pattern.search(raw):
            return label
    # Fallback: strip all repeated trailing "Nodes" suffixes
    return re.sub(r'(\s+Nodes)+\s*$', '', raw, flags=re.IGNORECASE).strip() or raw


def _extract_asset_ids_for_grouping(asset_ids_text):
    """
    Extract real asset IDs (must contain at least one digit) from the Asset IDs
    column value.  Returns a deduplicated ordered list, or [] when no real IDs
    are present (i.e. this is a module-level / root-level failure).

    Three-pass strategy
    -------------------
    Pass 1 — quoted dict keys (handles spaces):
        Captures the full string between opening/closing quotes that is
        immediately followed by ':', so keys like
            'Volvo China Open Day 4': [...]
        are extracted whole rather than being split on whitespace.

    Pass 2 — unquoted single-token dict keys and scalar values (legacy):
        Handles the original patterns such as
            'm30351': [...],  {key: {...}},  MOVIE_ID: 53

    Pass 3 — plain comma-separated IDs (no dict structure).
    """
    if not asset_ids_text:
        return []
    text = str(asset_ids_text).strip()
    ids = []

    def _is_valid_candidate(candidate):
        """Return True if *candidate* should be kept as an asset ID.
        Digits are NOT required — identifiers may be purely alphabetic with spaces.
        Skip-word sets filter out known field names and status tokens.
        Candidates that contain the word "Nodes" are always module/root labels,
        never real asset IDs, and are rejected here.
        """
        if not candidate:
            return False
        # "Live Feeds Nodes", "JSON Nodes", "Schedule Nodes" etc. are module labels
        if re.search(r'\bNodes?\b', candidate, re.IGNORECASE):
            return False
        norm = candidate.lower().replace(' ', '').replace('_', '')
        return norm not in _FIELD_SKIP_WORDS and norm not in _ID_SKIP_WORDS

    # Pass 1: quoted dict keys — captures full key including any spaces
    #   {'Volvo China Open Day 4': ['rating']}  →  Volvo China Open Day 4
    #   {'Magical Kenya Open': ['releaseDate']}  →  Magical Kenya Open
    #   {'m30351': ['thumbnail']}                →  m30351
    for m in re.finditer(r"""['"]([^'"]+)['"]\s*:""", text):
        candidate = m.group(1).strip()
        if _is_valid_candidate(candidate):
            ids.append(candidate)

    # Pass 2 (original): unquoted single-token keys / scalar values
    #   e.g.  {m30351: [...]}  or  key: 53
    # Digit is required here to prevent structural module-label tokens such as
    # "Nodes", "JSON", "Live", "Feeds" from being mistaken for asset IDs.
    # Those tokens are unquoted multi-word keys and always lack digits, while
    # real unquoted asset IDs (m30351, BellMedia-2931555) always contain digits.
    if not ids:
        for m in re.finditer(r"""['\"]?([A-Za-z0-9][\w\-]*)['\"]?\s*:\s*[\[{'"\d]""", text):
            candidate = m.group(1).strip()
            if (re.search(r'\d', candidate)
                    and re.match(r'^[A-Za-z0-9][\w\-]*$', candidate)
                    and _is_valid_candidate(candidate)):
                ids.append(candidate)

    # Pass 3: plain comma-separated list with no brace/bracket structure
    if not ids:
        for token in re.split(r'[,\n]+', text):
            token = token.strip().strip("'\" ")
            if token and re.match(r'^[A-Za-z0-9][\w\- ]*$', token) and _is_valid_candidate(token):
                ids.append(token)

    # Deduplicate preserving first-seen order
    seen: set = set()
    result = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            result.append(i)
    return result


def _parse_asset_field_mapping(asset_ids_text):
    """Parse the Asset IDs column into an OrderedDict of {asset_id: [fields]}
    when it contains per-asset missing-field mappings such as:

        {'20QFAZ4SO2KREXLT8T8JV': ['releaseDate']},
        {'20QF8QRN2P7P37RUZ83H6': ['thumbnail', 'releaseDate']}

    Returns an OrderedDict on success, or None when the format is not
    recognised (so callers fall back to the shared-issue-text path).
    """
    text = str(asset_ids_text or '').strip()
    # Quick guard: must look like it has dict-with-list structure
    if not text or '[' not in text or ':' not in text:
        return None
    try:
        # The column holds comma-separated single-key dicts; wrap in [] to eval.
        items = ast.literal_eval(f'[{text}]')
        if not isinstance(items, list) or not items:
            return None
        result = OrderedDict()
        for item in items:
            if not isinstance(item, dict):
                return None          # mixed structure — bail out safely
            for k, v in item.items():
                if isinstance(v, list) and all(isinstance(f, str) for f in v):
                    key_str = str(k)
                    # Reject module/root-level labels such as "Live Feeds Nodes",
                    # "JSON Nodes", "Schedule Nodes" — they are never asset IDs.
                    if re.search(r'\bNodes?\b', key_str, re.IGNORECASE):
                        return None
                    key_norm = key_str.lower().replace(' ', '').replace('_', '')
                    if key_norm in _FIELD_SKIP_WORDS or key_norm in _ID_SKIP_WORDS:
                        return None
                    result[key_str] = v
                else:
                    return None      # unexpected value type — bail out safely
        return result if result else None
    except Exception:
        return None


def _normalize_issue_text(issue: str) -> str:
    """Presentation-only normalisation applied when rendering issues in the
    Failure Summary table.  Never touches validators, Excel data, or any
    other part of the report pipeline.
    """
    import re as _re_local

    # 1. "for one or more [type] assets" → "for the asset"
    issue = _re_local.sub(
        r'\bfor one or more (?:series |episode |movie |TV special |short-form video |content )?assets?\b',
        'for the asset',
        issue, flags=_re_local.IGNORECASE,
    )

    # 2. "thumbnail value is missing" → "thumbnail image is missing"
    issue = issue.replace('thumbnail value is missing', 'thumbnail image is missing')

    # 3. Leading count in description/title length messages
    #    "8 description(s) exceed …" → "description exceeds …"
    issue = _re_local.sub(
        r'\b\d+\s+description\(s\)\s+exceed\b',
        'description exceeds',
        issue, flags=_re_local.IGNORECASE,
    )
    issue = _re_local.sub(
        r'\b\d+\s+title\(s\)\s+exceed\b',
        'title exceeds',
        issue, flags=_re_local.IGNORECASE,
    )

    # 3b. Leading count in year/version label messages
    #    "82 title(s) contain a year or version label" → "Title contains a year or version label."
    issue = _re_local.sub(
        r'\b\d+\s+title\(s\)\s+contain\s+a\s+year\s+or\s+version\s+label\.?',
        'Title contain year or version label.',
        issue, flags=_re_local.IGNORECASE,
    )

    # 4. "N thumbnail(s) are not 1920x1080 resolution"
    #    → "thumbnail does not have the required 1920×1080 resolution"
    issue = _re_local.sub(
        r'\b\d+\s+thumbnail\(s\)\s+are\s+not\s+1920[xX×]1080\s+resolution\b',
        'thumbnail does not have the required 1920×1080 resolution',
        issue, flags=_re_local.IGNORECASE,
    )

    # 5. "Thumbnail not having proper resolution: (W, H)"
    #    → "thumbnail resolution is invalid (W×H)"
    issue = _re_local.sub(
        r'Thumbnail not having proper resolution:\s*\((\d+),\s*(\d+)\)',
        lambda m: f'thumbnail resolution is invalid ({m.group(1)}×{m.group(2)})',
        issue, flags=_re_local.IGNORECASE,
    )

    return issue


def _should_use_asset_field_mapping(scenario: str, issue_text: str) -> bool:
    """Return True only when the row is a genuine missing-field scenario where
    per-asset field granularity is meaningful.

    Accepted patterns:
    - Scenario matches "Check Availability of … Keys" or
      "Check Availability of … Node Value"
    - Issue text explicitly contains both "required field" and "missing"

    This prevents diagnostic payloads (schedule times, matched title strings,
    etc.) from being misinterpreted as missing-field lists.
    """
    if re.search(
        r'check\s+availability\s+of\s+.+\s+(?:keys|node\s+value)',
        scenario,
        re.IGNORECASE,
    ):
        return True
    it = issue_text.lower()
    return 'required field' in it and 'missing' in it


def _group_failure_rows(rows):
    """Group failed Excel rows into two OrderedDicts shared by the HTML table
    and the embedded Excel export — ensuring both always match.

    Returns
    -------
    asset_groups  : OrderedDict  key=asset_id    → {'modules': [...], 'issues': [...]}
    module_groups : OrderedDict  key=module_label → {'issues': [...]}
    """
    failed_rows = [r for r in rows if _norm(r.get('Status', '')) == 'Failed']
    asset_groups: OrderedDict  = OrderedDict()
    module_groups: OrderedDict = OrderedDict()

    for row in failed_rows:
        module_label  = _clean_module_label(row.get('Module', ''))
        issue_summary = str(row.get('Issue Summary', '') or '').strip()
        scenario      = str(row.get('Scenario',      '') or '').strip()
        issue_text    = issue_summary if issue_summary else scenario

        asset_ids_raw   = str(row.get('Asset IDs', '') or '').strip()
        asset_field_map = (
            _parse_asset_field_mapping(asset_ids_raw)
            if _should_use_asset_field_mapping(scenario, issue_text)
            else None
        )

        if asset_field_map:
            # Per-asset granularity path — each asset gets its own field list.
            # Preserve the module-validation prefix already present in the
            # Issue Summary (e.g. "Movies validation:") so wording is consistent.
            _pm = re.match(r'^(.+?validation:)\s*', issue_text, re.IGNORECASE)
            _prefix = (_pm.group(1) + ' ') if _pm else f'{module_label} validation: '

            for aid, fields in asset_field_map.items():
                # Deduplicate while preserving original order
                field_str = ', '.join(dict.fromkeys(str(f) for f in fields))
                per_asset_issue = _normalize_issue_text(
                    f'{_prefix}required field "{field_str}" is missing for the asset.'
                )
                if aid not in asset_groups:
                    asset_groups[aid] = {'modules': [], 'issues': []}
                if module_label and module_label not in asset_groups[aid]['modules']:
                    asset_groups[aid]['modules'].append(module_label)
                if per_asset_issue and per_asset_issue not in asset_groups[aid]['issues']:
                    asset_groups[aid]['issues'].append(per_asset_issue)

        else:
            # Existing path — shared issue text across all extracted asset IDs.
            asset_ids     = _extract_asset_ids_for_grouping(asset_ids_raw)
            display_issue = _normalize_issue_text(issue_text) if issue_text else issue_text

            if asset_ids:
                for aid in asset_ids:
                    if aid not in asset_groups:
                        asset_groups[aid] = {'modules': [], 'issues': []}
                    if module_label and module_label not in asset_groups[aid]['modules']:
                        asset_groups[aid]['modules'].append(module_label)
                    if display_issue and display_issue not in asset_groups[aid]['issues']:
                        asset_groups[aid]['issues'].append(display_issue)
            else:
                if module_label not in module_groups:
                    module_groups[module_label] = {'issues': []}
                if display_issue and display_issue not in module_groups[module_label]['issues']:
                    module_groups[module_label]['issues'].append(display_issue)

    return asset_groups, module_groups


def _render_failure_html_card(asset_groups, module_groups):
    """Render the Failure Summary HTML card from pre-grouped data.

    Accepts the same (asset_groups, module_groups) produced by
    _group_failure_rows so the HTML table and the embedded Excel always match.
    """
    _dl_btn = (
        '<button class="dl-btn" onclick="downloadFailureSummary()">'
        'Download as Excel</button>'
    )

    if not asset_groups and not module_groups:
        return (
            '<div class="card">'
            f'<div class="card-label">Failure Summary {_dl_btn}</div>'
            '<div class="fs-none">No failures recorded.</div>'
            '</div>'
        )

    thead = (
        '<thead><tr>'
        '<th class="fs-col-id">Asset ID</th>'
        '<th class="fs-col-field">Field / Root Property</th>'
        '<th class="fs-col-issues">Issues</th>'
        '</tr></thead>'
    )

    def _issues_html(issues):
        if len(issues) > 1:
            return (
                '<ul style="margin:0;padding-left:16px;line-height:1.7;">'
                + ''.join(f'<li>{_esc(i)}</li>' for i in issues)
                + '</ul>'
            )
        return _esc(issues[0]) if issues else ''

    tbody_rows = ''

    # Module-level rows (no asset ID) rendered first so structural failures
    # appear at the top of the table, above per-asset failures.
    for module_label, data in module_groups.items():
        tbody_rows += (
            f'<tr>'
            f'<td class="fs-col-id"></td>'
            f'<td class="fs-col-field">{_esc(module_label)}</td>'
            f'<td class="fs-col-issues">{_issues_html(data["issues"])}</td>'
            f'</tr>'
        )

    for aid, data in asset_groups.items():
        tbody_rows += (
            f'<tr>'
            f'<td class="fs-col-id">{_esc(aid)}</td>'
            f'<td class="fs-col-field">{_esc(", ".join(data["modules"]))}</td>'
            f'<td class="fs-col-issues">{_issues_html(data["issues"])}</td>'
            f'</tr>'
        )

    return (
        '<div class="card">'
        f'<div class="card-label">Failure Summary {_dl_btn}</div>'
        f'<table class="fs-table">{thead}<tbody>{tbody_rows}</tbody></table>'
        '</div>'
    )


def _failure_summary_excel_b64(asset_groups, module_groups, channel_name):
    """Build an in-memory Excel workbook from failure-summary groups.

    Uses the identical grouped data as the HTML table so both always match.
    Returns (base64_string, suggested_download_filename).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Failure Summary'

    ws.append(['Asset ID', 'Field / Root Property', 'Issues'])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for aid, data in asset_groups.items():
        ws.append([aid, ', '.join(data['modules']), '\n'.join(data['issues'])])

    for module_label, data in module_groups.items():
        ws.append(['', module_label, '\n'.join(data['issues'])])

    for row in ws.iter_rows(min_row=2, max_col=3):
        row[2].alignment = Alignment(wrap_text=True)
    ws.column_dimensions['A'].width = 42
    ws.column_dimensions['B'].width = 28
    ws.column_dimensions['C'].width = 65

    buf = io.BytesIO()
    wb.save(buf)
    b64_str = base64.b64encode(buf.getvalue()).decode('ascii')

    safe_ch  = re.sub(r'[^\w\-]', '_', str(channel_name or 'report')).strip('_') or 'report'
    safe_ts  = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f'{safe_ch}_failure summary_{safe_ts}.xlsx'

    return b64_str, filename


def _group_failure_rows_from_updated_summary_list(updated_summary_list):
    """Build (asset_groups, module_groups) from the pre-filtered updated_summary_list.

    Each entry must have:
        'Asset_ID'      – asset identifier; empty/blank → module-level row
        'Module'        – field / root property label
        'Issue Summary' – human-readable issue text

    Returns the same (asset_groups, module_groups) tuple expected by
    _render_failure_html_card and _failure_summary_excel_b64.
    """
    asset_groups: OrderedDict  = OrderedDict()
    module_groups: OrderedDict = OrderedDict()

    for entry in updated_summary_list:
        asset_id     = str(entry.get('Asset_ID', entry.get('Asset ID', '')) or '').strip()
        module_label = str(entry.get('Module',        '') or '').strip()
        issue_text   = str(entry.get('Issue Summary', '') or '').strip()

        if asset_id:
            if asset_id not in asset_groups:
                asset_groups[asset_id] = {'modules': [], 'issues': []}
            if module_label and module_label not in asset_groups[asset_id]['modules']:
                asset_groups[asset_id]['modules'].append(module_label)
            if issue_text and issue_text not in asset_groups[asset_id]['issues']:
                asset_groups[asset_id]['issues'].append(issue_text)
        else:
            if module_label not in module_groups:
                module_groups[module_label] = {'issues': []}
            if issue_text and issue_text not in module_groups[module_label]['issues']:
                module_groups[module_label]['issues'].append(issue_text)

    return asset_groups, module_groups


def _build_failure_summary_card(rows):
    """Backward-compatible entry-point: groups rows then renders the HTML card."""
    ag, mg = _group_failure_rows(rows)
    return _render_failure_html_card(ag, mg)


# ---------------------------------------------------------------------------
# Coverage card builder
# ---------------------------------------------------------------------------


# def _build_coverage_card():
#     """
#     Read coverage stats from genai_utils module state and return an HTML card.
#     Returns an empty string if genai_utils is not importable or GENAI is off.
#     """
#     try:
#         from utils.genai_utils import get_coverage
#         cov = get_coverage()
#     except Exception:
#         return ""
#
#     ld = cov.get("lang_detect", {})
#     oc = cov.get("ocr", {})
#
#     # Suppress the card entirely if nothing was ever enqueued/tracked
#     if (ld.get("total_enqueued", 0) == 0 and oc.get("total_candidates", 0) == 0
#             and oc.get("total_enqueued", 0) == 0):
#         return ""
#
#     def _pill(label, count, pill_class="cov-reason-pill"):
#         return f'<span class="{pill_class}">{_esc(label)} &nbsp;{count}</span>'
#
#     def _stat_table(rows):
#         trs = "".join(
#             f'<tr><td>{_esc(label)}</td><td>{val}</td></tr>'
#             for label, val in rows
#         )
#         return f'<table class="cov-table">{trs}</table>'
#
#     def _reasons_block(reasons_dict, pill_class):
#         if not reasons_dict:
#             return '<div class="cov-none">None recorded</div>'
#         pills = "".join(
#             _pill(reason, count, pill_class)
#             for reason, count in sorted(reasons_dict.items(), key=lambda x: -x[1])
#         )
#         return f'<div class="cov-reasons"><div class="cov-reasons-label">Reasons</div>{pills}</div>'
#
#     # ── LANG_DETECT section ──────────────────────────────────────────────
#     ld_rows = [
#         ("Enqueued for detection",   ld.get("total_enqueued",   0)),
#         ("Succeeded",                ld.get("total_success",    0)),
#         ("Failed (API / parse)",     ld.get("total_failed_api", 0)),
#     ]
#     ld_fail_reasons = ld.get("failure_reasons", {})
#     ld_html = (
#         '<div class="cov-section">'
#         '<div class="cov-title">'
#         '<span class="cov-title-dot" style="background:#6366F1;"></span>'
#         'Language Detection (LANG_DETECT)</div>'
#         + _stat_table(ld_rows)
#         + _reasons_block(ld_fail_reasons, "cov-reason-pill")
#         + '</div>'
#     )
#
#     # ── OCR section ──────────────────────────────────────────────────────
#     ocr_rows = [
#         ("Total assets (candidates)", oc.get("total_candidates", 0)),
#         ("Eligible (all basic checks passed)", oc.get("total_eligible",   0)),
#         ("Enqueued for OCR",          oc.get("total_enqueued",   0)),
#         ("Succeeded",                 oc.get("total_success",    0)),
#         ("Failed (API / parse)",      oc.get("total_failed_api", 0)),
#         ("Skipped (pre-OCR)",         oc.get("total_skipped",    0)),
#     ]
#     ocr_skip_reasons = oc.get("skip_reasons", {})
#     ocr_fail_reasons = oc.get("failure_reasons", {})
#     ocr_html = (
#         '<div class="cov-section">'
#         '<div class="cov-title">'
#         '<span class="cov-title-dot" style="background:#F59E0B;"></span>'
#         'OCR Title Extraction (OCR_IMAGE_TEXT)</div>'
#         + _stat_table(ocr_rows)
#         + _reasons_block(ocr_skip_reasons, "cov-skip-pill")
#         + _reasons_block(ocr_fail_reasons, "cov-reason-pill")
#         + '</div>'
#     )
#
#     card = (
#         '<div class="card">'
#         '<div class="card-label">AI Processing Coverage</div>'
#         '<div class="cov-grid">'
#         + ld_html + ocr_html +
#         '</div>'
#         '</div>'
#     )
#     return card


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def summary_report_writer(
    excel_path,
    channel_name=None,
    content_partner_name=None,
    psd=None,
    json_url=None,
    updated_summary_list=None,
):
    """
    Build an HTML summary from the Excel report at *excel_path* and save it
    alongside the Excel file.

    Parameters
    ----------
    excel_path           : str  — absolute path to the generated Excel report.
    channel_name         : str  — optional channel display name shown in the
                                  Run Configuration card.
    content_partner_name : str  — optional content partner name (shown if provided).
    psd                  : str  — optional PSD reference value (shown if provided).
    json_url             : str  — runtime JSON feed URL; overrides the global
                                  JSON_URL imported from Input.py when supplied.

    Returns
    -------
    str  – path of the generated HTML file.
    """
    # Resolve the effective feed URL: runtime parameter wins; fall back to
    # the Input.py global so callers that omit json_url keep working.
    _effective_url = json_url
    #_effective_url = json_url if json_url is not None else JSON_URL
    if not excel_path or not os.path.isfile(excel_path):
        print(f'WARNING: summary_report_writer — Excel file not found: {excel_path}')
        return None

    rows = _read_excel(excel_path)
    if not rows:
        print('WARNING: summary_report_writer — Excel file is empty, skipping HTML report.')
        return None

    # Filter out excluded scenarios for HTML rendering only; Excel is unchanged.
    visible_rows = _filter_rows(rows)

    ts       = datetime.now().strftime('%B %d, %Y  ·  %H:%M:%S')
    ts_short = datetime.now().strftime('%Y-%m-%d %H:%M')
    total    = len(visible_rows)

    counts = defaultdict(int)
    for r in visible_rows:
        counts[_norm(r.get('Status', ''))] += 1
    passed_n = counts['Passed']
    failed_n = counts['Failed']
    nt_n     = counts['Not Tested']
    obs_n    = counts['Observation']
    pass_pct = int(passed_n / total * 100) if total else 0

    # Group by module, preserving order of first appearance
    modules = OrderedDict()
    for r in visible_rows:
        m = r.get('Module', 'Unknown') or 'Unknown'
        modules.setdefault(m, []).append(r)

    # ── Derive name tokens ────────────────────────────────────────────────
    try:
        json_name = os.path.splitext(os.path.basename(_effective_url.rstrip('/')))[0]
    except Exception:
        json_name = 'feed'
    excel_basename = os.path.splitext(os.path.basename(excel_path))[0]
    html_filename  = f'Summary-report_{json_name}_{excel_basename}.html'
    out_dir        = os.path.dirname(excel_path)
    out_path       = os.path.join(out_dir, html_filename)

    # ── Overall status pill ───────────────────────────────────────────────
    overall_status = 'Passed' if failed_n == 0 else 'Failed'
    pill_color     = '#22C55E' if overall_status == 'Passed' else '#EF4444'
    pill_bg        = 'rgba(34,197,94,.12)' if overall_status == 'Passed' else 'rgba(239,68,68,.12)'
    pill_border    = 'rgba(34,197,94,.35)' if overall_status == 'Passed' else 'rgba(239,68,68,.35)'

    excel_basename_ext = os.path.basename(excel_path)   # e.g. 1748000000000.xlsx
    json_basename_ext  = os.path.basename(_effective_url.rstrip('/'))  # e.g. 6962.json

    # ── Build HTML sections ───────────────────────────────────────────────
    # Optional metadata items — only rendered when a value was supplied
    _opt_items = ''
    if channel_name:
        _opt_items += (
            f'<div class="input-item"><label>Channel Name</label>'
            f'<span class="val">{_esc(channel_name)}</span></div>'
        )
    if content_partner_name:
        _opt_items += (
            f'<div class="input-item"><label>Content Partner</label>'
            f'<span class="val">{_esc(content_partner_name)}</span></div>'
        )
    if psd:
        _opt_items += (
            f'<div class="input-item"><label>PSD</label>'
            f'<span class="val">{_esc(psd)}</span></div>'
        )

    inputs_card = (
        '<div class="card">'
        '<div class="card-label">Run Configuration</div>'
        '<div class="input-grid">'
        f'<div class="input-item"><label>JSON Feed URL</label>'
        f'<span class="val">{_esc(_effective_url)}</span></div>'
        f'<div class="input-item"><label>Input JSON Name</label>'
        f'<span class="val">{_esc(json_basename_ext)}</span></div>'
        f'<div class="input-item"><label>Feed / Channel ID</label>'
        f'<span class="val">{_esc(json_name)}</span></div>'
        f'<div class="input-item"><label>Execution Timestamp</label>'
        f'<span class="val">{_esc(ts_short)}</span></div>'
        + _opt_items
        + '</div>'
        '</div>'
    )

    module_cards = '\n'.join(_module_card(m, r) for m, r in modules.items())

    # ── Failure Summary — compute groups once, reuse for HTML + embedded Excel ──
    if updated_summary_list:
        _fs_ag, _fs_mg = _group_failure_rows_from_updated_summary_list(updated_summary_list)
    else:
        _fs_ag, _fs_mg = _group_failure_rows(visible_rows)
    _fs_b64, _fs_filename = _failure_summary_excel_b64(_fs_ag, _fs_mg, channel_name)

    # JavaScript embedded in <head>: base64 payload + Blob download function.
    # Blob download works reliably from a standalone HTML file with no server.
    _fs_script = (
        '<script>\n'
        f'var _fsDlB64="{_fs_b64}";\n'
        f'var _fsDlName="{_fs_filename}";\n'
        'function downloadFailureSummary(){\n'
        '  var bin=atob(_fsDlB64),bytes=new Uint8Array(bin.length);\n'
        '  for(var i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);\n'
        '  var blob=new Blob([bytes],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"});\n'
        '  var a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=_fsDlName;\n'
        '  document.body.appendChild(a);a.click();\n'
        '  setTimeout(function(){document.body.removeChild(a);URL.revokeObjectURL(a.href);},0);\n'
        '}\n'
        '</script>\n'
    )

    # ── Assemble full document ────────────────────────────────────────────
    html_doc = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>Test Summary Report &mdash; {_esc(json_name)}</title>\n'
        f'<style>{_CSS}</style>\n'
        + _fs_script +
        '</head>\n'
        '<body>\n'

        # Hero
        '<div class="hero">'
        '<div class="hero-inner">'
        '<div class="hero-eyebrow">Samsung EPG Quality Report</div>'
        '<div class="hero-title">Test Summary Report</div>'
        f'<div class="hero-meta">'
        f'<span>&#128225;&nbsp;{_esc(_effective_url)}</span>'
        f'<span>&#128336;&nbsp;{_esc(ts)}</span>'
        f'</div>'
        '</div>'
        '</div>'

        # Body
        '<div class="container">'
        + inputs_card
        + _render_failure_html_card(_fs_ag, _fs_mg)
        + '</div>'

        # Footer
        '<div class="footer">'
        f'<strong>Samsung EPG Validation Framework</strong>'
        f'&ensp;&middot;&ensp;Source: {_esc(os.path.basename(excel_path))}'
        f'&ensp;&middot;&ensp;{_esc(ts)}'
        '</div>'

        '</body>\n</html>\n'
    )

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html_doc)

    print(f'INFO: HTML summary report saved → {out_path}')
    return out_path