"""Shared helpers for the dashboard: data loading, UND styling, page header, badges, charts and tables.

The look follows the sister dashboard, ND Fiscal and Economic Watch: dark UND theme, site banner, a status line with the
data checks, badges that say what kind of numbers a page shows, chart titles inside dark panels, and a
"Method and sources" panel at the foot of each page.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import COUNTIES, OUT, PEER_NAMES, REGIONS, SECTORS, SHORT  # noqa: E402

ASSETS = Path(__file__).parent / "assets"
LOGO = Path(__file__).parent / "logo.svg"
ORG = "Institute of Policy and Business Analytics (IPBA), Nistler College of Business & Public Administration, University of North Dakota"
DISCLAIMER = ("Independent analysis by the Institute of Policy and Business Analytics (IPBA), Nistler College of Business & "
              "Public Administration, University of North Dakota. Figures come from public statistics; estimates and model "
              "results are IPBA's. They do not represent the views of the University of North Dakota or the North Dakota "
              "University System, and nothing here endorses any business or program.")

# Public contact for questions, problem reports and accessible formats, as published on IPBA's page on the UND website
# (checked November 13, 2026): the institute page and the Nistler College office phone it lists. The page lists no
# general institute email; set CONTACT_EMAIL only to an address IPBA has agreed to publish.
CONTACT_URL = "https://business.und.edu/research/policy-institute/index.html"
CONTACT_PHONE = "701.777.2135"
CONTACT_EMAIL = ""


def contact_line():
    who = (f"the [Institute of Policy and Business Analytics]({CONTACT_URL}) (IPBA), Nistler College of Business & "
           "Public Administration, University of North Dakota")
    how = f"email [{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL}?subject=ND%20Business%20and%20Innovation%20Watch) or " \
          if CONTACT_EMAIL else ""
    return (f"Questions, corrections or a problem to report (including accessibility, or a request for the data in "
            f"another format): {how}contact {who}, phone {CONTACT_PHONE}.")


# UND brand (campus.und.edu/brand) and dark panels, as in ND Fiscal and Economic Watch
UND_GREEN, UND_GREEN_DARK, UND_GRAY = "#009A44", "#00662C", "#AEAEAE"
BG, PANEL, PANEL_2, INK, MUTED, GRID = "#1D2027", "#2A2E38", "#323743", "#E9ECEF", "#9AA1AC", "#3A3F4B"
GREEN_TEXT, NEG_TEXT = "#2EBD66", "#F28A45"     # text shades with at least 4.5:1 contrast on the panels
NEG = "#D55E00"                                 # declines: Okabe-Ito vermillion, distinct from green for colour-blind readers

# Places: ND in UND green and drawn heavier, the US a grey dashed line, peers in the sister dashboard's palette.
GEO_COLORS = {"ND": UND_GREEN, "MN": "#E5734B", "MT": "#C9B37E", "SD": "#8E8CD8", "WY": "#7FCFA0", "US": UND_GRAY}
ACCENT = UND_GREEN
SECOND = "#E5734B"                    # Fiscal Watch orange for the second series (no blue)
# County-map scale, one hue: the lowest colour keeps 3:1 contrast with the panel (WCAG 1.4.11)
SEQ = [[0, "#2E8B57"], [0.5, "#5DC08A"], [1, "#C8F5DA"]]
PALETTE = [UND_GREEN, "#E5734B", UND_GRAY, "#7FCFA0", "#C9B37E", "#8E8CD8", "#D98FB0"]   # Fiscal Watch colours, orange in place
# of blue; every colour has at least 3:1 contrast with the panel
DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]   # second cue so lines never rely on colour alone
BADGE = {"official": ("OFFICIAL DATA", "#5C6370"), "estimate": ("IPBA ESTIMATE", "#8A6D00"),
         "model": ("IPBA MODEL", "#00662C")}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, p, label, span, div {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }}
h1, h2, h3, .und-title, .kpi-label {{ font-family: "Oswald", "Trade Gothic", "Arial Narrow", sans-serif !important;
  letter-spacing: .02em; }}
.block-container {{ padding-top: 2.4rem; max-width: 1400px; }}
[data-testid="stSidebarHeader"] img, [data-testid="stHeaderLogo"], [data-testid="stSidebarLogo"], [data-testid="stLogo"] {{
  height: 2.9rem !important; max-width: 100%; }}
.site-banner {{ text-align: center; margin: 0 0 6px; padding-bottom: 8px; position: relative; font-family: "Oswald", "Arial Narrow", sans-serif;
  font-weight: 600; font-size: clamp(22px, 3vw, 36px); letter-spacing: .08em; text-transform: uppercase; animation: banner-in .9s ease-out both; }}
.site-banner span {{ background: linear-gradient(100deg, #FFFFFF 0%, #FFFFFF 38%, {UND_GREEN} 50%, #FFFFFF 62%, #FFFFFF 100%);
  background-size: 250% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: banner-shine 2.2s ease-in-out .4s 2 both; }}
.site-banner::after {{ content: ""; position: absolute; left: 50%; bottom: 0; width: 120px; height: 3px; margin-left: -60px;
  background: {UND_GREEN}; border-radius: 2px; animation: banner-rule 1.2s ease-out both; }}
.site-by {{ text-align: center; color: #B8BEC8; font-size: 12.5px; letter-spacing: .03em; margin: 0 0 14px; }}
@keyframes banner-in {{ from {{ opacity: 0; transform: translateY(-8px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes banner-shine {{ from {{ background-position: 125% 0; }} to {{ background-position: -125% 0; }} }}
@keyframes banner-rule {{ from {{ width: 0; margin-left: 0; }} to {{ width: 120px; margin-left: -60px; }} }}
@keyframes banner-fade {{ 0%, 100% {{ color: #FFFFFF; }} 50% {{ color: #7FCFA0; }} }}
@media (prefers-reduced-motion: reduce) {{ .site-banner, .site-banner::after {{ animation: none; }}
  .site-banner span {{ background: none; color: #fff; animation: banner-fade 4.6s ease-in-out 1 both; }} }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #252932 0%, #1A1D23 100%); border-right: 1px solid {GRID}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {UND_GREEN}22; border-left: 3px solid {UND_GREEN}; }}
[class*="st-key-navsec_"] button {{ justify-content: flex-start; border-radius: 0; border-bottom: 1px solid {GRID}; padding: 4px 0 4px 4px; margin-top: 10px; min-height: 0; }}
[class*="st-key-navsec_"] button > div {{ justify-content: flex-start; width: 100%; }}
[class*="st-key-navsec_"] button p {{ text-align: left; font-family: "Oswald", "Arial Narrow", sans-serif; font-size: 13px; color: #fff; text-transform: uppercase; letter-spacing: .08em; font-weight: 500; }}
[class*="st-key-navsec_"] button [data-testid="stIconMaterial"] {{ color: {MUTED}; font-size: 18px; }}
[class*="st-key-navsec_"] button:hover p, [class*="st-key-navsec_"] button:hover [data-testid="stIconMaterial"] {{ color: {UND_GREEN}; }}
.nav-sub {{ font-size: 10.5px; color: {MUTED}; text-transform: uppercase; letter-spacing: .07em; margin: 10px 0 0 8px; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ padding-top: 2px; padding-bottom: 2px; border-left: 3px solid transparent; }}
.und-head {{ display:flex; align-items:baseline; gap:22px; margin: 4px 0 10px; flex-wrap: wrap; }}
.und-title {{ font-size: 34px; font-weight: 500; color: #fff; margin: 0; padding: 0; line-height: 1.2; }}
.und-sub {{ color: {MUTED}; font-size: 13px; }}
.page-sub {{ color: #C9CED6; font-size: 14px; margin: -2px 0 10px; }}
.small-label {{ font-size: 11px; color: {MUTED}; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }}
[data-testid="stMain"] [data-testid="stHeading"] h3 {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important;
  font-size: 11px; color: {MUTED}; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; padding: 18px 0 4px; }}
[data-testid="stMain"] [data-testid="stHeading"] h3 a {{ display: none; }}
[data-testid="stNavSectionHeader"] {{ font-family: "Oswald", "Arial Narrow", sans-serif; font-size: 13px; color: #fff;
  text-transform: uppercase; letter-spacing: .08em; font-weight: 500; margin: 20px 0 4px; padding: 0 0 4px 8px;
  border-bottom: 1px solid {GRID}; }}
[data-testid="stNavSectionHeader"] * {{ font-family: inherit; color: inherit; font-size: inherit; letter-spacing: inherit; }}
div[data-testid="stSelectbox"] label, div[data-testid="stRadio"] > label, div[data-testid="stMultiSelect"] label {{
  font-size: 11px !important; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }}
.stButton>button, .stDownloadButton>button {{ border-radius: 8px; font-weight: 600; letter-spacing: .03em; }}
.badge {{ display:inline-block; color:#fff; font-size:10.5px; font-weight:700; letter-spacing:.06em; padding:2px 8px;
  border-radius:4px; margin-right:4px; }}
.foot {{ color: {MUTED}; font-size: 11px; margin-top: 18px; }}
.kpi {{ position: relative; background: linear-gradient(160deg, {PANEL_2} 0%, {PANEL} 55%); border: 1px solid {GRID};
  border-radius: 10px; padding: 14px 16px 10px; min-height: 150px; overflow: hidden; margin-bottom: 12px; }}
.kpi::before {{ content:""; position:absolute; top:-40px; right:-40px; width:160px; height:120px;
  background: radial-gradient(circle, var(--glow) 0%, transparent 70%); opacity:.30; }}
.kpi-label {{ font-size: 15px; color: #F1F3F5; font-weight: 400; line-height: 1.25; min-height: 38px; }}
.kpi {{ container-type: inline-size; }}          /* the number is never cut: the trend line shrinks first, then wraps */
.kpi-row {{ display:flex; flex-wrap: wrap; align-items:flex-end; justify-content:space-between; margin-top:10px; gap: 8px; }}
.kpi-spark {{ flex: 1 1 44px; min-width: 44px; max-width: 120px; line-height: 0; }}
.kpi-spark svg {{ width: 100%; height: 40px; display: block; }}
.kpi-value {{ flex: none; margin-left: auto; max-width: 100%; font-size: 26px; font-size: clamp(16px, 16cqw, 26px); color:#fff;
  font-weight: 400; line-height: 1; white-space: nowrap; }}
.kpi-delta {{ font-size: 11px; font-weight: 600; margin-top: 6px; }}
.kpi-note {{ font-size: 11px; color: {MUTED}; margin-top: 2px; }}
.src {{ color: {MUTED}; font-size: 12px; border-top: 1px solid {GRID}; padding-top: 8px; margin-top: 18px; }}
.src a {{ color: {GREEN_TEXT}; }}
@media (max-width: 640px) {{  /* touch targets at least 32 px tall on phones (WCAG 2.2, 2.5.8 asks for 24 px) */
  button, [role="tab"], summary, [data-testid="stSidebarNav"] a, .src a, label[data-baseweb="radio"],
  label[data-baseweb="checkbox"], [data-testid="stWidgetLabel"] + div [data-baseweb="select"] > div {{ min-height: 32px; }}
  label[data-baseweb="radio"], label[data-baseweb="checkbox"] {{ align-items: center; padding: 4px 0; }}
  .src a {{ display: inline-flex; align-items: center; }} }}
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible {{ outline: 3px solid #FFD166 !important; outline-offset: 2px; }}
</style>
"""


# ------------------------------------------------------------------ data
def _stamp(name):
    f = OUT / name
    return f.stat().st_mtime if f.exists() else 0


@st.cache_data(show_spinner=False)
def _read(name, stamp, **kw):
    return pd.read_csv(OUT / name, **kw)


def table(name, **kw):
    """A tidy table from outputs/; the cache refreshes when the file changes."""
    return _read(name, _stamp(name), **kw)


def sources():
    f = OUT / "sources.json"
    return json.loads(f.read_text()) if f.exists() else {}


def checks():
    f = OUT / "data_checks.json"
    return json.loads(f.read_text()) if f.exists() else {}


def ready():
    """True when the data tables exist; otherwise tell the reader how to build them."""
    need = ["bfs_monthly.csv", "bds_states.csv", "bds_firm_age.csv", "qcew_annual.csv", "bea_gdp.csv", "acs_places.csv",
            "county_business.csv", "cbp_sizes.csv", "scorecard.csv"]
    missing = [n for n in need if not (OUT / n).exists()]
    if missing:
        st.warning("The data tables have not been built yet. Run `py -3.15 src/run_all.py` and reload this page.")
        return False
    return True


def as_of(iso):
    """A date readers can quote, e.g. 'November 13, 2026' (local time of the update)."""
    try:
        d = datetime.fromisoformat(iso).astimezone()
    except (TypeError, ValueError):
        return "unknown"
    return f"{d:%B} {d.day}, {d.year}"


def release_text(v):
    """'released November 12, 2026' from a source record (src/releases.py); '' when the publisher gives no date."""
    if not v.get("released"):
        return ""
    verb = "first found" if v.get("released_basis", "").startswith("first found") else "released"
    return f"{verb} {as_of(v['released'])}"


def update_status():
    """The last automatic update (src/update.py), or {} if none has run."""
    f = OUT / "update_status.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def ago(iso):
    try:
        s = (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except (TypeError, ValueError):
        return "unknown"
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    return f"{int(s // 86400)}d ago"


# ------------------------------------------------------------------ page pieces
def sidebar():
    # logo.svg is drawn by src/make_icon.py
    st.logo(str(LOGO), size="large")
    with st.sidebar:
        st.divider()
        st.markdown(f'<div class="foot" style="margin-top:0">{DISCLAIMER}</div>', unsafe_allow_html=True)
        link = (f"mailto:{CONTACT_EMAIL}?subject=ND%20Business%20and%20Innovation%20Watch%20problem" if CONTACT_EMAIL
                else CONTACT_URL)
        st.markdown(f'<div class="foot"><a href="{link}" style="color:{GREEN_TEXT}">Report a problem or ask a question'
                    f'</a> &middot; IPBA, {CONTACT_PHONE}</div>', unsafe_allow_html=True)


def _section_paths(entries):
    return {e.url_path for e in entries if not isinstance(e, str)}


def _toggle(title):
    st.session_state.nav_open ^= {title}


def sidebar_nav(sections, current):
    """Sidebar menu built from the page list itself, as in ND Fiscal and Economic Watch. Each section header opens and
    closes its pages; the section holding the current page opens when you arrive in it, and the others keep the state
    you left them in. The current page is highlighted. sections: [(title, [page or a sub-heading string])]."""
    sel = f'a[href="{current.url_path}"]'          # exact match; links are relative and the Overview's is empty
    st.markdown(f'<style>[data-testid="stSidebar"] [data-testid="stPageLink"] {sel} {{ background: {UND_GREEN}33 '
                f'!important; border-left-color: {UND_GREEN}; font-weight: 600; }}</style>', unsafe_allow_html=True)
    st.session_state.setdefault("nav_open", set())
    here = next((t for t, es in sections if t and current.url_path in _section_paths(es)), None)
    if here and here != st.session_state.get("nav_here"):
        st.session_state.nav_open.add(here)
    st.session_state.nav_here = here
    with st.sidebar:
        for i, (title, entries) in enumerate(sections):
            if title:
                is_open = title in st.session_state.nav_open
                st.button(title, key=f"navsec_{i}", on_click=_toggle, args=(title,), type="tertiary", width="stretch",
                          icon=":material/expand_more:" if is_open else ":material/chevron_right:")
                if not is_open:
                    continue
            for e in entries:
                if isinstance(e, str):
                    st.markdown(f'<div class="nav-sub">{e}</div>', unsafe_allow_html=True)
                else:
                    st.page_link(e, label=e.title, icon=e.icon)


def banner():
    """Site title at the top of every page. The animation ends within five seconds (WCAG 2.2.2); readers who ask for
    reduced motion get a colour fade instead."""
    st.markdown('<div class="site-banner" role="banner"><span>ND Business and Innovation Watch</span></div>'
                '<div class="site-by">An independent analysis by the Institute of Policy and Business Analytics, '
                'University of North Dakota</div>', unsafe_allow_html=True)


def badges(*kinds, note=""):
    """Labels that say what a page's numbers are: official data, IPBA estimate or IPBA model result."""
    html = " ".join(f'<span class="badge" style="background:{BADGE[k][1]}">{BADGE[k][0]}</span>' for k in kinds)
    st.markdown(f'<div style="margin:-2px 0 12px">{html} <span class="und-sub">{note}</span></div>', unsafe_allow_html=True)


def header(title, subtitle, *kinds, note=""):
    banner()
    c = checks()
    stt = c.get("status", "")
    n = {s: sum(r["status"] == s for r in c.get("checks", [])) for s in ("PASS", "WARN", "FAIL")}
    clr = {"PASS": GREEN_TEXT, "WARN": "#C9A100", "FAIL": NEG_TEXT}.get(stt, MUTED)
    chk = (f' &middot; <span style="color:{clr}">data checks: {n["PASS"]} pass'
           f'{", " + str(n["WARN"]) + " warn" if n["WARN"] else ""}{", " + str(n["FAIL"]) + " FAIL" if n["FAIL"] else ""}'
           f'</span>') if c else ""
    upd = max((v.get("refreshed", "") for v in sources().values()), default="")
    st.markdown(f'<div class="und-head"><h1 class="und-title">{title}</h1>'
                f'<div class="und-sub">Data as of {as_of(upd)}{chk}</div></div>'
                f'<p class="page-sub">{subtitle}</p>', unsafe_allow_html=True)
    if kinds:
        badges(*kinds, note=note)
    if stt == "FAIL":
        st.error("A data check failed on the last update. Some figures may be affected; see About the data.",
                 icon=":material/report:")


def esc(t):
    return t.replace("$", r"\$")


def method_panel(lines, refs=()):
    """The standard 'Method and sources' panel at the foot of a page. `refs` are keys of references.REFERENCES (APA 7th),
    shown as a list; the full list is on the About the data page."""
    from references import REFERENCES
    with st.expander("Method and sources", icon=":material/menu_book:"):
        st.markdown("\n".join(f"- {esc(x)}" for x in lines))
        if refs:
            st.markdown('<div class="small-label">References</div>', unsafe_allow_html=True)
            st.markdown("\n".join(f"- {esc(REFERENCES[k])}" for k in refs))


def source_line(*keys, note=""):
    """Sources and dates for the numbers on a page."""
    s = sources()
    parts = []
    for k in keys:
        v = s.get(k)
        if v:
            name = f'<a href="{v["url"]}">{v["name"]}</a>' if v.get("url") else v["name"]
            rel = release_text(v)
            parts.append(f'{v["publisher"]}, {name} ({v["period"]}{"; " + rel if rel else ""})')
    upd = max((v.get("refreshed", "") for k, v in s.items() if k in keys), default="")
    when = f" Data last checked {as_of(upd)}." if upd else ""
    st.markdown(f'<div class="src"><b>Sources:</b> {"; ".join(parts)}.{when} {note}</div>', unsafe_allow_html=True)


def data_table(df, label="Chart data (accessible table)", key="t", fmt=None):
    """Text alternative for a chart: the plotted numbers as a table, with a CSV download."""
    with st.expander(label, icon=":material/table_view:"):
        cfg = {c: st.column_config.NumberColumn(format=(fmt or {}).get(c, "localized")) for c in df.columns
               if pd.api.types.is_numeric_dtype(df[c])}
        st.dataframe(df, width="stretch", hide_index=True, column_config=cfg)
        st.download_button("Download (CSV)", df.to_csv(index=False).encode(), f"{key}.csv", "text/csv", key=f"dl_{key}",
                           icon=":material/download:")


def layout(fig, h=400, ytitle=None, legend=True, title=None):
    """Dark-panel chart layout with the title inside the chart, as in the sister dashboard."""
    fig.update_layout(
        template="plotly_dark", height=h, paper_bgcolor=PANEL, plot_bgcolor=PANEL, colorway=PALETTE,
        font=dict(family="Helvetica Neue, Arial", color=INK, size=12),
        margin=dict(l=55, r=20, t=50 if title else 20, b=40), hovermode="x unified" if legend else "closest",
        showlegend=legend, legend=dict(orientation="h", x=1, xanchor="right", y=1.08, title=None,
                                       font=dict(size=11, color=MUTED), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=GRID, font=dict(color=INK)),
        title=dict(text=title, font=dict(family="Oswald, Arial", size=16, color="#fff"), x=0.01) if title else None)
    fig.update_yaxes(title=ytitle, gridcolor=GRID, zeroline=False)
    fig.update_xaxes(showgrid=False, title=None, zeroline=False)
    return fig


def show(fig, key, title=None):
    """Draw a chart; a title goes inside the chart panel."""
    if title:
        legend = fig.layout.showlegend is not False
        fig.update_layout(title=dict(text=title, font=dict(family="Oswald, Arial", size=16, color="#fff"), x=0.01),
                          margin=dict(t=80 if legend else 50))
        if legend:                        # legend on its own line under the title, right-aligned as in Fiscal Watch
            fig.update_layout(legend=dict(y=1.02, yanchor="bottom", x=1, xanchor="right"))
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def geo_lines(df, x, y, geo="geo", ytitle=None, fmt=",.0f", h=400, title=None):
    """One line per place; North Dakota drawn heavier, the US dashed; end labels so colour is not the only cue."""
    fig = go.Figure()
    for g in [g for g in GEO_COLORS if g in set(df[geo])]:
        d = df[df[geo] == g].sort_values(x)
        nd = g == "ND"
        fig.add_scatter(x=d[x], y=d[y], name=PEER_NAMES[g], mode="lines",
                        line=dict(color=GEO_COLORS[g], width=3.2 if nd else 2, dash="dash" if g == "US" else "solid"),
                        hovertemplate=f"%{{y:{fmt}}}")
        if len(d):
            fig.add_annotation(x=d[x].iloc[-1], y=d[y].iloc[-1], text=g, showarrow=False, xanchor="left", xshift=6,
                               font=dict(size=11, color=MUTED))
    return layout(fig, h, ytitle, title=title)


def sparkline(values, color, w=120, h=40):
    """Small trend line (decorative; the card states the value and change in text)."""
    import numpy as np
    v = np.asarray([x for x in values if pd.notna(x)], dtype=float)
    if len(v) < 2:
        return ""
    lo, hi = v.min(), v.max()
    rng = hi - lo or 1
    xs = np.linspace(2, w - 2, len(v))
    ys = h - 4 - (v - lo) / rng * (h - 10)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    gid = f"g{abs(hash((pts, color))) % 10**8}"
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="{gid}" x1="0" '
            f'y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".35"/><stop offset="1" '
            f'stop-color="{color}" stop-opacity="0"/></linearGradient></defs><polygon points="2,{h} {pts} {w - 2},{h}" '
            f'fill="url(#{gid})"/><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>')


def kpi_card(label, value, spark=(), change=None, good_up=True, note=""):
    """KPI card in the sister dashboard's style: label, value, sparkline, change vs a year earlier with direction."""
    if change is None or pd.isna(change):
        dl, color = "", UND_GRAY
    else:
        better = (change >= 0) == bool(good_up)
        color = UND_GREEN if better else NEG
        txt = GREEN_TEXT if better else NEG_TEXT
        dl = (f'<div class="kpi-delta" style="color:{txt}">{"↑" if change >= 0 else "↓"} {abs(change):.1f}% vs year earlier '
              f'({"better" if better else "worse"})</div>')
    st.markdown(f'<div class="kpi" style="--glow:{color}"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-row"><div class="kpi-spark">{sparkline(spark, color)}</div><div class="kpi-value">{value}</div></div>'
                f'{dl}<div class="kpi-note">{note}</div></div>', unsafe_allow_html=True)


def pick_places(key, default=("ND", "US"), label="Places on the chart"):
    """Multiselect of ND, peer states and the US; returns postal codes (ND kept if nothing is picked)."""
    names = {v: k for k, v in PEER_NAMES.items()}
    shown = st.multiselect(label, list(PEER_NAMES.values()), default=[PEER_NAMES[g] for g in default], key=key)
    return [names[n] for n in shown] or ["ND"]


def reliability(est, moe):
    """Reliability of an ACS estimate from its coefficient of variation, CV = (MOE / 1.645) / estimate (U.S. Census
    Bureau, 2020, chapter 8): under 15% reliable, 15-30% use with caution, over 30% low reliability."""
    import numpy as np
    if pd.isna(est) or pd.isna(moe) or est == 0:
        return np.nan, ""
    cv = moe / 1.645 / abs(est) * 100
    return cv, ("reliable" if cv < 15 else "use with caution" if cv <= 30 else "low reliability")


def money(x, unit=""):
    if pd.isna(x):
        return "–"
    a = abs(x)
    if a >= 1e9:
        return f"${x / 1e9:,.1f} billion"
    if a >= 1e6:
        return f"${x / 1e6:,.1f} million"
    return f"${x:,.0f}"


def num(x, d=0):
    return "–" if pd.isna(x) else f"{x:,.{d}f}"


def pct(x, d=1, signed=True):
    return "–" if pd.isna(x) else (f"{x:+.{d}f}%" if signed else f"{x:.{d}f}%")


def quarter_label(ts):
    ts = pd.Timestamp(ts)
    return f"{ts.year} Q{(ts.month - 1) // 3 + 1}"
