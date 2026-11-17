"""Indicators and outlook pages: business and innovation indicators, business conditions now (diffusion index), and
short-term outlooks. Calculations are in src/indicators.py and src/outlook.py; these pages only display them."""
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

FREQ = {"M": "monthly", "Q": "quarterly", "A": "yearly"}
SPARK = {"M": 36, "Q": 16, "A": 12}
LEVEL_UNITS = ("%", "per resident", "$ per week")          # comparable across places as levels; others as an index
THEME_ORDER = ["Business formation", "Business dynamics", "Jobs and pay", "Spending", "Innovation"]


SHORT = {"Business applications": "Applications", "High-propensity applications (likely employers)": "Likely employers",
         "Jobs covered by unemployment insurance": "Jobs", "Business locations with employees": "Business locations",
         "Taxable sales and purchases": "Taxable sales", "Average weekly wage": "Weekly wage"}


def ready():
    if not (OUT / "indicators.csv").exists():
        st.info("Indicators have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def data():
    t = lib.table("indicators.csv", parse_dates=["date"])
    cat = lib.table("indicators_catalog.csv").set_index("id")
    return t, cat


def period(d, freq):
    d = pd.Timestamp(d)
    return {"M": f"{d:%b %Y}", "Q": f"{d.year} Q{(d.month - 1) // 3 + 1}", "A": f"{d.year}"}[freq]


def year_change(s, freq):
    """Change vs a year earlier; monthly series use 3-month averages."""
    s = s.dropna().sort_index()
    if len(s) < 2:
        return np.nan
    last = s.index[-1]
    if freq == "M":
        cur, prev = s.iloc[-3:].mean(), s[s.index <= last - pd.DateOffset(months=12)].iloc[-3:].mean()
    else:
        prev = s.get(last - pd.DateOffset(years=1), np.nan)
        cur = s.iloc[-1]
    return (cur / prev - 1) * 100 if prev and pd.notna(prev) else np.nan


# ------------------------------------------------------------------ indicators
def indicators_page():
    lib.header("Business and innovation indicators", "The latest readings on starting businesses, business dynamics, "
               "jobs and pay, spending and innovation in North Dakota, with neighbors and the nation for comparison.",
               "official", "estimate", note="Census Bureau, BLS, NSF, SBA and ND Tax Commissioner. Changes: IPBA calculations.")
    if not ready():
        return
    t, cat = data()
    nd = t[t.geo == "ND"]
    for theme in THEME_ORDER:
        ids = [i for i in cat.index if cat.loc[i, "theme"] == theme and i in set(nd.id)]
        if not ids:
            continue
        st.subheader(theme)
        cols = st.columns(4)
        for k, i in enumerate(ids):
            c = cat.loc[i]
            s = nd[nd.id == i].set_index("date").value.sort_index()
            good = None if pd.isna(c.higher_is_good) else bool(c.higher_is_good)
            with cols[k % 4]:
                lib.kpi_card(c["name"], c.format.format(s.iloc[-1]), s.tail(SPARK[c.freq]).values,
                             year_change(s, c.freq), good if good is not None else True,
                             f"{period(s.index[-1], c.freq)} · {FREQ[c.freq]} · {c.unit}")
    st.caption("Change vs a year earlier; monthly figures compare 3-month averages. Green = better for business "
               "conditions, orange = worse (for closings, a fall is better). Small numbers, such as SBIR/STTR awards, "
               "swing a lot from year to year.")

    st.subheader("Compare places over time")
    k = st.columns([2, 3])
    names = {cat.loc[i, "name"]: i for i in cat.index if i in set(t.id)}
    lab = k[0].selectbox("Indicator", list(names), key="ind_explore")
    i = names[lab]
    c = cat.loc[i]
    geos_avail = [g for g in PEER_NAMES if g in set(t[t.id == i].geo)]
    with k[1]:
        geos = lib.pick_places("ind_explore_places", default=tuple(g for g in ("ND", "US") if g in geos_avail))
    d = t[(t.id == i) & t.geo.isin(geos)].copy()
    as_level = any(u in c.unit for u in LEVEL_UNITS) or len(set(d.geo)) == 1
    if not as_level:
        start = max(d.groupby("geo").date.min())
        base = d[d.date == start].set_index("geo").value
        d["value"] = d.value / d.geo.map(base) * 100
    ytitle = c.unit if as_level else f"Index ({period(start, c.freq)} = 100)"
    lib.show(lib.geo_lines(d, "date", "value", ytitle=ytitle, fmt=",.1f", h=400), "ind_explore_chart",
             title=f"{lab}{'' if as_level else ', indexed so places of different size can be compared'}")
    tab = d.pivot_table(index="date", columns="geo", values="value").rename(columns=PEER_NAMES).reset_index()
    tab["date"] = tab.date.dt.strftime("%Y-%m")
    lib.data_table(tab.round(2), key=f"indicator_{i}")
    lib.method_panel([
        "Business formation: Census Business Formation Statistics, seasonally adjusted. Business formations are new "
        "employer businesses within 4 quarters of the application: actual counts, then Census projections for recent months.",
        "Jobs and pay: BLS QCEW quarterly data (jobs = average of the quarter's three months). Core technology industries: "
        "computer and electronic products, software publishers and computer systems design; other technology industries "
        "are withheld for North Dakota in some quarters and left out.",
        "Business dynamics: Census Business Dynamics Statistics (March to March).",
        "Innovation: NSF HERD university R&D (fiscal years) and SBIR/STTR awards by award year; per-resident values "
        "divide by the Census population estimate for the same year.",
        "Spending: ND Tax Commissioner taxable sales and purchases by filing quarter (current dollars)."],
        ["burns1946", "bayard2018", "haltiwanger2013", "griliches1990"])
    lib.source_line("bfs", "qcew_q", "bds", "taxable_sales", "herd", "sbir", "popest")


# ------------------------------------------------------------------ conditions now
def energy_section():
    """Oil production and price: context for western North Dakota and state revenue."""
    if not (OUT / "energy_monthly.csv").exists():
        return
    e = lib.table("energy_monthly.csv", parse_dates=["month"])
    e = e[e.month >= "2010-01-01"]
    st.subheader("Oil context: North Dakota production and price")
    p, w = e.dropna(subset=["nd_crude_kbd"]), e.dropna(subset=["wti_usd"])
    py = p.set_index("month").nd_crude_kbd
    wy = w.set_index("month").wti_usd
    has_nd = bool("nd_price_usd" in e and e.nd_price_usd.notna().any())
    k = st.columns(3 if has_nd else 2)
    lp, lw = py.index.max(), wy.index.max()
    k[0].metric(f"Crude oil production, {lp:%B %Y}", f"{py.iloc[-1]:,.0f}k barrels a day",
                f"{(py.iloc[-1] / py.get(lp - pd.DateOffset(years=1)) - 1) * 100:+.1f}% vs a year earlier"
                if (lp - pd.DateOffset(years=1)) in py else None, delta_color="off", delta_arrow="off")
    k[1].metric(f"WTI oil price, {lw:%B %Y}", f"${wy.iloc[-1]:,.2f} a barrel",
                f"{(wy.iloc[-1] / wy.get(lw - pd.DateOffset(years=1)) - 1) * 100:+.1f}% vs a year earlier"
                if (lw - pd.DateOffset(years=1)) in wy else None, delta_color="off", delta_arrow="off")
    if has_nd:
        ny = e.dropna(subset=["nd_price_usd"]).set_index("month").nd_price_usd
        ln = ny.index.max()
        gap = ny.iloc[-1] - wy.get(ln, float("nan"))
        k[2].metric(f"Price ND producers received, {ln:%B %Y}", f"${ny.iloc[-1]:,.2f} a barrel",
                    f"${abs(gap):,.2f} {'below' if gap < 0 else 'above'} WTI that month" if pd.notna(gap) else None,
                    delta_color="off", delta_arrow="off",
                    help="EIA first purchase price: what producers are paid when the oil is first sold, at the lease.")
    c = st.columns(2)
    with c[0]:
        fig = go.Figure(go.Scatter(x=p.month, y=p.nd_crude_kbd, mode="lines", line=dict(color=lib.ACCENT, width=2),
                                   hovertemplate="%{x|%b %Y}: %{y:,.0f}k barrels a day<extra></extra>"))
        lib.show(lib.layout(fig, 300, "Thousand barrels a day", legend=False), "oil_prod", title="North Dakota crude oil production")
    with c[1]:
        fig = go.Figure(go.Scatter(x=w.month, y=w.wti_usd, mode="lines", name="WTI (Cushing)",
                                   line=dict(color=lib.SECOND, width=2), hovertemplate="%{x|%b %Y}: $%{y:,.2f}"))
        if has_nd:
            n = e.dropna(subset=["nd_price_usd"])
            fig.add_scatter(x=n.month, y=n.nd_price_usd, mode="lines", name="ND first purchase price",
                            line=dict(color=lib.ACCENT, width=2, dash="dash"), hovertemplate="%{x|%b %Y}: $%{y:,.2f}")
        lib.show(lib.layout(fig, 300, "$ a barrel", legend=has_nd), "oil_price",
                 title="Oil price: WTI and what North Dakota producers received" if has_nd else "Oil price (WTI, Cushing)")
    lib.data_table(e.assign(month=e.month.dt.strftime("%Y-%m")).rename(columns={
        "month": "Month", "nd_crude_kbd": "ND crude production (thousand barrels a day)", "wti_usd": "WTI price ($ a barrel)",
        "nd_price_usd": "ND first purchase price ($ a barrel)"}), "Oil data (table)", key="oil")
    disc = ""
    if has_nd:
        both = e.dropna(subset=["nd_price_usd", "wti_usd"])
        recent = both[both.month > both.month.max() - pd.DateOffset(months=12)]
        disc = (f" Over the last 12 months of data, North Dakota producers received on average "
                f"${(recent.wti_usd - recent.nd_price_usd).mean():,.2f} a barrel less than WTI, mostly the cost of "
                "moving the oil to market.")
    st.caption("U.S. Energy Information Administration: WTI spot price at Cushing, Oklahoma, and the North Dakota crude "
               "oil first purchase price (what producers are paid at the lease), current dollars." + disc +
               " The ND price is published with a lag of about two months.")


def conditions_page():
    lib.header("Current realities", "Short term, the latest 12 to 24 months: is North Dakota's business climate improving? "
               "The share of business and innovation indicators better than a year earlier, and the momentum of the main ones.",
               "official", "estimate", note="Diffusion index and growth rates: IPBA calculations from public data.")
    if not ready():
        return
    t, cat = data()
    dif = lib.table("diffusion.csv", parse_dates=["month"]).dropna(subset=["improving_share"])
    det = lib.table("diffusion_detail.csv", parse_dates=["latest"])
    nd = t[t.geo == "ND"]
    last = dif.iloc[-1]
    c = st.columns(4)
    with c[0]:
        lib.kpi_card("Indicators improving", f"{last.improving_share:.0f}%", dif.improving_share.tail(36).values,
                     None, True, f"{int(det.improving.sum())} of {len(det)} indicators · {last.month:%b %Y}")
    for col, i in zip(c[1:], ["applications", "jobs_q", "taxable_sales"]):
        s = nd[nd.id == i].set_index("date").value.sort_index()
        with col:
            lib.kpi_card(cat.loc[i, "name"], cat.loc[i, "format"].format(s.iloc[-1]), s.tail(SPARK[cat.loc[i, "freq"]]).values,
                         year_change(s, cat.loc[i, "freq"]), True, period(s.index[-1], cat.loc[i, "freq"]))
    tone = ("conditions are improving on most fronts" if last.improving_share > 60 else
            "the picture is mixed" if last.improving_share >= 40 else "conditions are weakening on most fronts")
    st.markdown(f"**Reading:** {last.improving_share:.0f}% of North Dakota's business and innovation indicators are better "
                f"than a year earlier, so {tone}. The index uses the latest figure each source has "
                "published, so slower annual measures lag behind monthly ones."
                + (f" Counting only the timely monthly and quarterly indicators, {last.timely_share:.0f}% are improving "
                   f"({int(last.timely_indicators)} indicators)." if "timely_share" in dif and pd.notna(last.timely_share) else ""))
    cols = st.columns([1.4, 1])
    with cols[0]:
        fig = go.Figure(go.Scatter(x=dif.month, y=dif.improving_share, mode="lines", line=dict(color=lib.UND_GREEN, width=2.4),
                                   fill="tozeroy", fillcolor="rgba(0,154,68,.12)", name="All indicators",
                                   hovertemplate="All: %{y:.0f}%<extra></extra>"))
        if "timely_share" in dif:
            fig.add_scatter(x=dif.month, y=dif.timely_share, mode="lines", name="Monthly and quarterly only",
                            line=dict(color=lib.SECOND, width=2, dash="dot"), hovertemplate="Timely: %{y:.0f}%<extra></extra>")
        fig.add_hline(y=50, line_dash="dash", line_color=lib.MUTED, annotation_text="50%: as many improving as worsening",
                      annotation_font_color=lib.MUTED)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        lib.show(lib.layout(fig, 370, "% of indicators improving"), "dif_chart",
                 title="Diffusion index of ND business indicators: all, and timely (monthly and quarterly) only")
        lib.data_table(dif.assign(month=dif.month.dt.strftime("%Y-%m")).rename(columns={
            "month": "Month", "improving_share": "All indicators improving (%)", "indicators": "Indicators",
            "timely_share": "Timely indicators improving (%)", "timely_indicators": "Timely indicators"}).round(1),
            key="diffusion")
    with cols[1]:
        g = det.groupby("theme").improving.agg(["sum", "size"])
        fig = go.Figure(go.Bar(y=g.index, x=g["sum"] / g["size"] * 100, orientation="h",
                               marker=dict(color=lib.UND_GREEN, line=dict(width=0)),
                               text=[f"{int(a)} of {int(b)}" for a, b in zip(g["sum"], g["size"])], textposition="outside",
                               hovertemplate="%{y}: %{x:.0f}%<extra></extra>"))
        fig.update_xaxes(range=[0, 125], ticksuffix="%")
        lib.show(lib.layout(fig, 370, legend=False), "dif_theme", title="Improving now, by theme")
    # momentum: change vs a year earlier for the timeliest series
    rows = []
    for i in ["applications", "hp_applications", "jobs_q", "estabs_q", "taxable_sales", "wage_q"]:
        s = nd[nd.id == i].set_index("date").value.sort_index()
        f = cat.loc[i, "freq"]
        lag = 12 if f == "M" else 4
        sm = s.rolling(3).mean() if f == "M" else s
        yoy = (sm / sm.shift(lag) - 1) * 100
        rows.append(pd.DataFrame({"date": yoy.index, "value": yoy.values, "name": cat.loc[i, "name"]}))
    m = pd.concat(rows).dropna()
    m = m[m.date >= "2019-01-01"]
    fig = go.Figure()
    palette = lib.PALETTE
    ends = []
    for k, (n, g) in enumerate(m.groupby("name", sort=False)):
        clr = palette[k % len(palette)]
        fig.add_scatter(x=g.date, y=g.value, name=n, mode="lines", hovertemplate="%{y:+.1f}%",
                        line=dict(color=clr, width=2, dash=lib.DASHES[k % len(lib.DASHES)]))
        ends.append([g.value.iloc[-1], SHORT.get(n, n), clr])
    # end labels at the right edge, spread apart so they never overlap
    gap = (m.value.quantile(.99) - m.value.quantile(.01)) * .09
    ends.sort()
    for a, b in zip(ends, ends[1:]):
        b[0] = max(b[0], a[0] + gap)
    for y, n, clr in ends:
        fig.add_annotation(x=m.date.max(), y=y, text=n, showarrow=False, xanchor="left", xshift=8,
                           font=dict(color=clr, size=11))
    fig.add_hline(y=0, line_color=lib.UND_GRAY, line_width=1)
    fig.update_yaxes(ticksuffix="%")
    fig = lib.layout(fig, 420, "% change from a year earlier")
    fig.update_layout(margin=dict(r=150))
    lib.show(fig, "momentum", title="Momentum: change from a year earlier")
    st.caption("Each line has its own dash pattern and is named at its right end.")
    tab = m.pivot_table(index="date", columns="name", values="value").reset_index()
    tab["date"] = tab.date.dt.strftime("%Y-%m")
    lib.data_table(tab.round(1), key="momentum")
    d2 = det.assign(latest=det.latest.dt.strftime("%Y-%m"))[["theme", "indicator", "latest", "change_pct", "improving"]]
    st.dataframe(d2.rename(columns={"theme": "Theme", "indicator": "Indicator", "latest": "Latest data",
                                    "change_pct": "Change vs year earlier (%)", "improving": "Improving"}),
                 hide_index=True, width="stretch",
                 column_config={"Change vs year earlier (%)": st.column_config.NumberColumn(format="%+.1f")})
    energy_section()
    lib.method_panel([
        "Diffusion index: for each month, the share of North Dakota indicators better than a year earlier, using the "
        "latest value each source had published by then. For closings a fall counts as better. Monthly series compare "
        "3-month averages; per-resident versions of the same measure are not counted twice. Above 50%, most indicators "
        "are improving (Burns & Mitchell, 1946).",
        "Momentum: change from a year earlier; monthly series use 3-month averages.",
        "Oil context: EIA North Dakota field production of crude oil and the WTI spot price, monthly. Not counted in "
        "the diffusion index: a higher price helps producers and state revenue but raises costs for other businesses."],
        ["burns1946"])
    lib.source_line("bfs", "qcew_q", "bds", "taxable_sales", "herd", "sbir", "eia")


# ------------------------------------------------------------------ outlook
def sector_outlooks():
    """Four-quarter job outlooks for each private industry sector (src/outlook_sector.py)."""
    if not (OUT / "outlook_sector_meta.csv").exists():
        return
    m = lib.table("outlook_sector_meta.csv", dtype={"sector": str}, parse_dates=["last_actual"])
    fc = lib.table("outlook_sector.csv", dtype={"sector": str}, parse_dates=["date"])
    last = m.last_actual.max()
    st.subheader("Outlook by industry: private jobs over the next 4 quarters")
    st.caption(f"Average jobs over the next four quarters compared with the last four (through {lib.quarter_label(last)}), "
               "with the 80% range. Each sector is modelled on its own with the same tested methods as above, so the "
               "sectors do not add up exactly to the statewide outlook.")
    m = m.assign(lo_pct=(m.next_lo / m.jobs_last_year - 1) * 100, hi_pct=(m.next_hi / m.jobs_last_year - 1) * 100)
    s = m.sort_values("change_pct")
    fig = go.Figure(go.Bar(
        y=s.name, x=s.change_pct, orientation="h",
        marker=dict(color=[lib.ACCENT if v >= 0 else lib.SECOND for v in s.change_pct], line=dict(width=0)),
        error_x=dict(type="data", symmetric=False, array=s.hi_pct - s.change_pct, arrayminus=s.change_pct - s.lo_pct,
                     color=lib.MUTED, thickness=1.2, width=3),
        customdata=s[["lo_pct", "hi_pct", "backtest_error_pct"]].values,
        hovertemplate="%{y}: %{x:+.1f}% (80% range %{customdata[0]:+.1f}% to %{customdata[1]:+.1f}%; past error "
                      "%{customdata[2]:.1f}%)<extra></extra>"))
    fig.add_vline(x=0, line_color=lib.UND_GRAY, line_width=1)
    lib.layout(fig, 600, legend=False).update_xaxes(title="% change in average jobs, next 4 quarters vs last 4",
                                                     ticksuffix="%")
    lib.show(fig, "ol_sectors", title="Expected change in private jobs by sector, with 80% ranges")
    pick = st.selectbox("Sector", m.sort_values("jobs_last_year", ascending=False).name, key="ol_sector")
    row = m[m.name == pick].iloc[0]
    d = fc[fc.sector == row.sector]
    a = d[(d.kind == "actual") & (d.date >= d.date.max() - pd.DateOffset(years=6))]
    f = d[d.kind == "forecast"]
    fig = go.Figure()
    fig.add_scatter(x=list(f.date) + list(f.date[::-1]), y=list(f.hi) + list(f.lo[::-1]), fill="toself",
                    fillcolor="rgba(0,154,68,.18)", line=dict(width=0), name="80% range", hoverinfo="skip")
    fig.add_scatter(x=a.date, y=a.value, name="Actual", mode="lines", line=dict(color=lib.UND_GRAY, width=2),
                    hovertemplate="%{y:,.0f}")
    join = pd.concat([a.tail(1), f])
    fig.add_scatter(x=join.date, y=join.value, name="Outlook", mode="lines",
                    line=dict(color=lib.UND_GREEN, width=2.6, dash="dot"), hovertemplate="%{y:,.0f}")
    lib.show(lib.layout(fig, 360, "Jobs"), "ol_sector_chart", title=f"{pick}: private jobs, actual and outlook")
    if row.estimated_quarters:
        st.caption(f"BLS withheld {int(row.estimated_quarters)} past quarter(s) for this sector; they were estimated "
                   "from the same quarter a year earlier and the growth of the neighbouring quarters.")
    if row.coverage_pct < 70:
        st.warning("For this sector the 80% range held fewer later outcomes than it should in testing, so the true "
                   "uncertainty is likely wider than shown.", icon=":material/warning:")
    t = m.sort_values("jobs_last_year", ascending=False)[["name", "jobs_last_year", "next_year", "change_pct", "next_lo",
                                                           "next_hi", "model", "backtest_error_pct", "coverage_pct",
                                                           "estimated_quarters"]]
    lib.data_table(t.rename(columns={
        "name": "Sector", "jobs_last_year": "Jobs, last 4 quarters (avg)", "next_year": "Outlook, next 4 quarters (avg)",
        "change_pct": "Change (%)", "next_lo": "80% range, low", "next_hi": "80% range, high", "model": "Model",
        "backtest_error_pct": "Average past error (%)", "coverage_pct": "Past outcomes inside range (%)",
        "estimated_quarters": "Withheld quarters estimated"}).round(1), "Sector outlooks (table)", key="outlook_sectors")


def region_outlooks():
    """Four-quarter private job outlooks for the 8 planning regions (src/outlook_region.py)."""
    if not (OUT / "outlook_region_meta.csv").exists():
        return
    m = lib.table("outlook_region_meta.csv", parse_dates=["last_actual"])
    fc = lib.table("outlook_region.csv", parse_dates=["date"])
    last = m.last_actual.max()
    st.subheader("Outlook by planning region: private jobs over the next 4 quarters")
    st.caption(f"Each region's private jobs (its counties added up, through {lib.quarter_label(last)}) are modelled on "
               "their own with the same tested methods; the regions do not add up exactly to the statewide outlook.")
    m = m.assign(lo_pct=(m.next_lo / m.jobs_last_year - 1) * 100, hi_pct=(m.next_hi / m.jobs_last_year - 1) * 100)
    order = [r for r in lib.REGIONS if r in set(m.region)]
    s = m.set_index("region").loc[order].reset_index()
    fig = go.Figure(go.Bar(
        x=s.region.str.replace(r" \(", "<br>(", regex=True), y=s.change_pct,
        marker=dict(color=[lib.ACCENT if v >= 0 else lib.SECOND for v in s.change_pct], line=dict(width=0)),
        error_y=dict(type="data", symmetric=False, array=s.hi_pct - s.change_pct, arrayminus=s.change_pct - s.lo_pct,
                     color=lib.MUTED, thickness=1.2, width=4),
        customdata=s[["lo_pct", "hi_pct", "backtest_error_pct"]].values,
        hovertemplate="%{x}: %{y:+.1f}% (80% range %{customdata[0]:+.1f}% to %{customdata[1]:+.1f}%; past error "
                      "%{customdata[2]:.1f}%)<extra></extra>"))
    fig.add_hline(y=0, line_color=lib.UND_GRAY, line_width=1)
    lib.layout(fig, 380, "% change in average private jobs", legend=False).update_yaxes(ticksuffix="%")
    lib.show(fig, "ol_regions", title="Expected change in private jobs by planning region, with 80% ranges")
    pick = st.selectbox("Planning region", order, key="ol_region")
    row = s[s.region == pick].iloc[0]
    d = fc[fc.region == pick]
    a = d[(d.kind == "actual") & (d.date >= d.date.max() - pd.DateOffset(years=6))]
    f = d[d.kind == "forecast"]
    fig = go.Figure()
    fig.add_scatter(x=list(f.date) + list(f.date[::-1]), y=list(f.hi) + list(f.lo[::-1]), fill="toself",
                    fillcolor="rgba(0,154,68,.18)", line=dict(width=0), name="80% range", hoverinfo="skip")
    fig.add_scatter(x=a.date, y=a.value, name="Actual", mode="lines", line=dict(color=lib.UND_GRAY, width=2),
                    hovertemplate="%{y:,.0f}")
    join = pd.concat([a.tail(1), f])
    fig.add_scatter(x=join.date, y=join.value, name="Outlook", mode="lines",
                    line=dict(color=lib.UND_GREEN, width=2.6, dash="dot"), hovertemplate="%{y:,.0f}")
    lib.show(lib.layout(fig, 340, "Private jobs"), "ol_region_chart", title=f"{pick}: private jobs, actual and outlook")
    if row.coverage_pct < 70:
        st.warning("For this region the 80% range held fewer later outcomes than it should in testing, so the true "
                   "uncertainty is likely wider than shown.", icon=":material/warning:")
    t = s[["region", "jobs_last_year", "next_year", "change_pct", "next_lo", "next_hi", "model", "backtest_error_pct",
           "coverage_pct"]]
    lib.data_table(t.rename(columns={
        "region": "Planning region", "jobs_last_year": "Private jobs, last 4 quarters (avg)",
        "next_year": "Outlook, next 4 quarters (avg)", "change_pct": "Change (%)", "next_lo": "80% range, low",
        "next_hi": "80% range, high", "model": "Model", "backtest_error_pct": "Average past error (%)",
        "coverage_pct": "Past outcomes inside range (%)"}).round(1), "Region outlooks (table)", key="outlook_regions")
    if "excluded_counties" in s:
        ex = s[s.excluded_counties.fillna("") != ""]
        if len(ex):
            st.caption("Left out because BLS withheld their jobs in some quarters (not estimated, to protect employers): "
                       + "; ".join(f"{c} County in {r} ({p:.2f}% of the region's private jobs)"
                                   for r, c, p in zip(ex.region, ex.excluded_counties, ex.excluded_share_pct)) + ".")


REVENUE_SHOWN = ["sales_use", "corp_income", "indiv_income", "motor_vehicle", "oil_taxes"]


def revenue_link():
    """General fund revenue outlook from the sister dashboard ND Fiscal and Economic Watch (read only)."""
    if not (OUT / "fiscal_outlook.csv").exists():
        return
    f = lib.table("fiscal_outlook.csv")
    meta = json.loads((OUT / "fiscal_outlook_meta.json").read_text()) if (OUT / "fiscal_outlook_meta.json").exists() else {}
    v = f.set_index(["code", "biennium", "kind"]).value_m
    st.subheader("What it means for state revenue: the general fund outlook")
    st.caption("From IPBA's ND Fiscal and Economic Watch, which models North Dakota's general fund revenue. Sales and "
               "corporate income taxes follow business activity, so the business outlook above and the revenue outlook "
               "move together. Figures are in $ millions per two-year budget period (biennium, July to June).")
    k = st.columns(4)
    def get(code, b, kind):
        return v.get((code, b, kind), float("nan"))
    tot_a, tot_n = get("total", "2023-25", "actual"), get("total", "2027-29", "IPBA estimate")
    k[0].metric("General fund revenue, 2027-29 (IPBA)", lib.money(tot_n * 1e6),
                f"{(tot_n / tot_a - 1) * 100:+.1f}% vs 2023-25 actual", delta_color="off", delta_arrow="off")
    lo, hi = get("total", "2027-29", "low-oil scenario"), get("total", "2027-29", "high-oil scenario")
    k[1].metric("Oil-price scenarios, 2027-29", f"{lib.money(lo * 1e6)} to {lib.money(hi * 1e6)}",
                f"base assumes WTI about ${meta.get('wti_baseline_2027_29', float('nan')):,.0f}" if meta else None,
                delta_color="off", delta_arrow="off")
    s_a, s_n = get("sales_use", "2023-25", "actual"), get("sales_use", "2027-29", "IPBA estimate")
    k[2].metric("Sales and use tax, 2027-29", lib.money(s_n * 1e6), f"{(s_n / s_a - 1) * 100:+.1f}% vs 2023-25",
                delta_color="off", delta_arrow="off")
    c_a, c_n = get("corp_income", "2023-25", "actual"), get("corp_income", "2027-29", "IPBA estimate")
    k[3].metric("Corporate income tax, 2027-29", lib.money(c_n * 1e6), f"{(c_n / c_a - 1) * 100:+.1f}% vs 2023-25",
                delta_color="off", delta_arrow="off")
    names = f.drop_duplicates("code").set_index("code").category
    cols = [("2023-25", "actual", lib.UND_GRAY), ("2025-27", "official forecast", lib.GEO_COLORS["MT"]),
            ("2025-27", "IPBA estimate", lib.SECOND), ("2027-29", "IPBA estimate", lib.ACCENT)]
    fig = go.Figure()
    for b, kind, clr in cols:
        y = [get(c, b, kind) for c in REVENUE_SHOWN]
        err = None
        if b == "2027-29":
            lo_ = [get(c, b, "low-oil scenario") for c in REVENUE_SHOWN]
            hi_ = [get(c, b, "high-oil scenario") for c in REVENUE_SHOWN]
            err = dict(type="data", symmetric=False, array=[h - m for h, m in zip(hi_, y)],
                       arrayminus=[m - l for m, l in zip(y, lo_)], color=lib.MUTED, thickness=1.2, width=4)
        fig.add_bar(x=[names[c] for c in REVENUE_SHOWN], y=y, name=f"{b} {kind}", error_y=err,
                    marker=dict(color=clr, line=dict(width=0)), hovertemplate="%{x}: $%{y:,.0f}M")
    fig.update_layout(barmode="group")
    lib.show(lib.layout(fig, 400, "$ millions per biennium"), "rev_link",
             title="General fund revenue by source, actual and outlook (2027-29 bars show the oil-price scenario range)")
    t = f.pivot_table(index="category", columns=["biennium", "kind"], values="value_m", sort=False)
    t.columns = [f"{b} {k_}" for b, k_ in t.columns]
    lib.data_table(t.round(1).reset_index().rename(columns={"category": "Revenue source"}),
                   "General fund revenue outlook, $ millions (table)", key="rev_link_t")
    st.caption(f"Source: ND Fiscal and Economic Watch (IPBA), collections through {meta.get('last_actual', 'n/a')}; "
               "'official forecast' is the Legislature's adopted forecast. Oil and gas taxes reach the general fund up "
               "to a fixed amount set in law, so they barely change across scenarios; the oil price mostly moves sales "
               "and income taxes. 2023-25 includes one-time transfers. Methods and full detail are in the Fiscal and "
               "Economic Watch.")


def outlook_page():
    lib.header("Future implications", "Where business formation and jobs in North Dakota are heading: a 12-month outlook "
               "from statistical models tested on past data, illustrative paths to 2030, and what they mean for businesses.",
               "model", note="IPBA statistical outlook, not an official forecast. Ranges show past forecast errors.")
    if not (OUT / "outlook_meta.json").exists():
        st.info("The outlook has not been built yet. Run `py -3.15 src/run_all.py`.")
        return
    meta = json.loads((OUT / "outlook_meta.json").read_text())
    fc = lib.table("outlook_forecast.csv", parse_dates=["date"])
    bt = lib.table("outlook_backtest.csv")
    implications(meta)
    st.subheader("The next 12 months, series by series")
    labels = {v["name"]: k for k, v in meta.items()}
    key = labels[st.selectbox("Series", list(labels), key="ol_series")]
    m = meta[key]
    q = m["freq"] == "Q"
    unit = "average level over the next 4 quarters" if q else "total over the next 12 months"
    c = st.columns(4)
    c[0].metric("Outlook, " + ("next 4 quarters (average)" if q else "next 12 months (total)"), f"{m['next_total']:,.0f}",
                f"{m['change_pct']:+.1f}% vs the previous {'4 quarters' if q else '12 months'}", delta_color="off",
                delta_arrow="off")
    c[1].metric("80% range", f"{m['next_total_lo']:,.0f} to {m['next_total_hi']:,.0f}")
    c[2].metric("Average past error", f"{m['backtest_error_pct']:.1f}%", f"{m['origins']} test forecasts", delta_color="off",
                delta_arrow="off")
    c[3].metric("Past outcomes inside the 80% range", f"{m['coverage_80_out_of_sample']:.0f}%", "tested on later forecasts",
                delta_color="off", delta_arrow="off")
    if m["coverage_80_out_of_sample"] < 70:
        st.warning("For this series the 80% range held fewer later outcomes than it should in testing, so the true "
                   "uncertainty is likely wider than shown.", icon=":material/warning:")
    d = fc[fc.series == key]
    a = d[d.kind == "actual"]
    a = a[a.date >= a.date.max() - pd.DateOffset(years=6)]
    f = d[d.kind == "forecast"]
    fig = go.Figure()
    fig.add_scatter(x=list(f.date) + list(f.date[::-1]), y=list(f.hi) + list(f.lo[::-1]), fill="toself",
                    fillcolor="rgba(0,154,68,.18)", line=dict(width=0), name="80% range", hoverinfo="skip")
    fig.add_scatter(x=a.date, y=a.value, name="Actual", mode="lines", line=dict(color=lib.UND_GRAY, width=2),
                    hovertemplate="%{y:,.0f}")
    join = pd.concat([a.tail(1), f])
    fig.add_scatter(x=join.date, y=join.value, name="Outlook", mode="lines", line=dict(color=lib.UND_GREEN, width=2.6, dash="dot"),
                    hovertemplate="%{y:,.0f}")
    lib.show(lib.layout(fig, 430, m["name"]), "ol_chart",
             title=f"{m['name']}: actual and outlook ({'quarterly' if q else 'monthly, not seasonally adjusted'})")
    tab = f[["date", "value", "lo", "hi"]].assign(date=f.date.dt.strftime("%Y-%m")).rename(columns={
        "date": "Period", "value": "Outlook", "lo": "80% range, low", "hi": "80% range, high"})
    lib.data_table(tab.round(0), "Outlook (table)", key=f"outlook_{key}")
    st.markdown(f"**Model used:** {m['model']}, chosen because it had the smallest average error for the {unit} "
                f"in {m['origins']} test forecasts made with only the data available at the time.")
    b = bt[bt.series == key][["model", "mean_error_pct", "median_error_pct", "origins"]].rename(columns={
        "model": "Model", "mean_error_pct": "Average error (%)", "median_error_pct": "Median error (%)", "origins": "Test forecasts"})
    st.dataframe(b.round(2), hide_index=True, width="stretch")
    sector_outlooks()
    region_outlooks()
    revenue_link()
    paths_section()
    lib.method_panel([
        "Models: seasonal naive (the same period last year), exponential smoothing on logs with a damped trend and "
        "seasonality (Holt-Winters), and their average. Series are not seasonally adjusted; the models handle seasons.",
        "Backtest: forecasts made from every month (or quarter) of the last 6 (or 8) years with only the data available "
        "then, compared with what happened. The model with the smallest average error of the horizon total is used.",
        "80% range: adaptive conformal ranges (Gibbs & Candès, 2021). At each past forecast date the range is set from "
        "the errors already known then, and it widens after a miss and narrows after a hit, so it keeps about 80% "
        "coverage when a series becomes more volatile (as business locations did after 2021). 'Past outcomes inside "
        "the 80% range' counts how often these out-of-sample ranges held the actual value.",
        "These are statistical extrapolations of past patterns. They know nothing about new policy, prices, large projects "
        "or shocks, and they are not official forecasts."],
        ["gardner1985", "hyndman2021", "gibbs2021"])
    lib.source_line("bfs", "qcew_q", "fiscal_watch")


def implications(meta):
    """Summary of all outlooks and what they mean for businesses (generated from the results)."""
    rows = []
    for k, m in meta.items():
        q = m["freq"] == "Q"
        rows.append({"Series": m["name"], "Next": "4 quarters (average)" if q else "12 months (total)",
                     "Outlook": f"{m['next_total']:,.0f}", "Change": f"{m['change_pct']:+.1f}%",
                     "80% range": f"{m['next_total_lo']:,.0f} to {m['next_total_hi']:,.0f}",
                     "Past error": f"{m['backtest_error_pct']:.1f}%",
                     "Range reliability": "good" if m["coverage_80_out_of_sample"] >= 70 else "range likely too narrow"})
    c = st.columns(4)
    a, j, e, h = meta["applications"], meta["private_jobs"], meta["estabs"], meta["hp_applications"]
    c[0].metric("Business applications, next 12 months", f"{a['next_total']:,.0f}", f"{a['change_pct']:+.1f}%",
                delta_color="off", delta_arrow="off")
    c[1].metric("Likely-employer applications", f"{h['next_total']:,.0f}", f"{h['change_pct']:+.1f}%", delta_color="off",
                delta_arrow="off")
    c[2].metric("Private-sector jobs, next 4 quarters", f"{j['next_total']:,.0f}", f"{j['change_pct']:+.1f}%",
                delta_color="off", delta_arrow="off")
    c[3].metric("Business locations, next 4 quarters", f"{e['next_total']:,.0f}", f"{e['change_pct']:+.1f}%",
                delta_color="off", delta_arrow="off")
    st.subheader("What it means for businesses")
    gap = a["change_pct"] - j["change_pct"]
    lines = [
        f"**New business formation** is set to {'rise' if a['change_pct'] > 1 else 'hold steady' if a['change_pct'] > -1 else 'fall'} "
        f"({a['change_pct']:+.1f}%), while **private jobs** are expected to {'grow' if j['change_pct'] > 0.5 else 'stay about flat' if j['change_pct'] > -0.5 else 'shrink'} "
        f"({j['change_pct']:+.1f}%). "
        + ("More new firms chasing a labor force that is not growing means hiring will stay competitive: new and expanding "
           "businesses should plan for recruiting costs and wage pressure." if gap > 2 else
           "Formation and jobs are moving together, so demand for workers and customers should broadly keep pace."),
        f"**Likely employers**: high-propensity applications are expected to change {h['change_pct']:+.1f}%. These are "
        "the applications most likely to become businesses with payrolls, so they are the best early signal of future "
        "job creation by new firms.",
        f"**Business locations** with employees are expected to change {e['change_pct']:+.1f}%; "
        + ("the range for this series was too narrow in testing, so treat it with extra caution." if
           e["coverage_80_out_of_sample"] < 70 else "growing locations mean more local competition and more suppliers."),
        "**Planning a project?** The What-if impact page estimates the jobs, income and taxes a new or expanding business "
        "would support in North Dakota or any planning region.",
    ]
    st.markdown("\n".join(f"- {x}" for x in lines))
    st.markdown("[What-if impact →](what-if)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def paths_section():
    if not (OUT / "outlook_paths.csv").exists():
        return
    p = lib.table("outlook_paths.csv")
    st.subheader("Illustrative paths to 2030")
    st.caption("Not forecasts: from the 12-month outlook, each series grows at the slow, middle or fast pace it has "
               "actually had over past 5-year periods. They show the range of plausible paths, not their likelihood.")
    cols = st.columns(2)
    colors = {"Slower (25th percentile)": "#C9B37E", "Middle (median)": lib.UND_GREEN, "Faster (75th percentile)": "#E5734B"}
    for col, i in zip(cols, ["applications", "private_jobs"]):
        d = p[p.id == i]
        a = d[(d.path == "Actual") & (d.year >= 2010)]
        fig = go.Figure()
        fig.add_scatter(x=a.year, y=a.value, name="Actual", mode="lines", line=dict(color=lib.UND_GRAY, width=2),
                        hovertemplate="%{y:,.0f}")
        for name, clr in colors.items():
            q = d[d.path == name]
            fig.add_scatter(x=q.year, y=q.value, name=f"{name.split(' (')[0]} ({q.growth_pct.iloc[0]:+.1f}% a year)",
                            mode="lines", line=dict(color=clr, width=2, dash="dot"), hovertemplate="%{y:,.0f}")
        with col:
            lib.show(lib.layout(fig, 400, d.label.iloc[0]), f"path_{i}", title=d.label.iloc[0])
    t = p[p.path != "Actual"].pivot_table(index=["label", "year"], columns="path", values="value").reset_index().round(0)
    lib.data_table(t, "Paths (table)", key="outlook_paths")
