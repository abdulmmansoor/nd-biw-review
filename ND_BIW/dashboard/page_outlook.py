"""Business and Innovation Overview (landing page) and the Outlook's Evolving dynamics page.
Calculations are in src/dynamics.py, src/indicators.py and src/outlook.py; these pages only display them."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

PHASES = [("Before the oil boom", 2000, 2010), ("Bakken boom", 2011, 2015), ("Oil bust", 2016, 2017),
          ("Recovery and pandemic", 2018, 2021), ("After the pandemic", 2022, 2100)]


def ready(*files):
    missing = [f for f in files if not (OUT / f).exists()]
    if missing:
        st.info("Some results have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def fmt_growth(v, kind):
    if pd.isna(v):
        return "–"
    return f"{v:+.1f} pts" if kind == "points" else f"{v:+.1f}% a year"


def link_row(items):
    st.markdown(" &nbsp;·&nbsp; ".join(f"[{t} →]({u})" for t, u in items), unsafe_allow_html=True)


# ------------------------------------------------------------------ overview
def overview_page():
    lib.header("Business and Innovation Overview", "North Dakota's business and innovation economy at a glance: how it "
               "has evolved, where it stands now, and what the next years may bring.", "official", "estimate", "model",
               note="Public data from Census, BLS, BEA, NSF and SBA; IPBA calculations, outlook and model.")
    if not ready("indicators.csv", "diffusion.csv", "outlook_meta.json", "dynamics_growth.csv"):
        return
    t = lib.table("indicators.csv", parse_dates=["date"])
    cat = lib.table("indicators_catalog.csv").set_index("id")
    dif = lib.table("diffusion.csv", parse_dates=["month"]).dropna()
    g = lib.table("dynamics_growth.csv")
    meta = json.loads((OUT / "outlook_meta.json").read_text())
    nd = t[t.geo == "ND"]
    from page_conditions import year_change, period, SPARK

    def card(i, note_extra=""):
        s = nd[nd.id == i].set_index("date").value.sort_index()
        c = cat.loc[i]
        lib.kpi_card(c["name"], c.format.format(s.iloc[-1]), s.tail(SPARK[c.freq]).values, year_change(s, c.freq),
                     bool(c.higher_is_good), f"{period(s.index[-1], c.freq)}{note_extra}")

    st.markdown('<div class="small-label">Where North Dakota stands</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        last = dif.iloc[-1]
        lib.kpi_card("Business indicators improving", f"{last.improving_share:.0f}%", dif.improving_share.tail(36).values,
                     None, True, f"of {int(last.indicators)} indicators · {last.month:%b %Y}")
    for col, i in zip(cols[1:], ["applications", "formations", "jobs_q"]):
        with col:
            card(i)
    cols = st.columns(4)
    for col, i in zip(cols, ["estabs_q", "wage_q", "taxable_sales", "herd"]):
        with col:
            card(i)

    def gl(i, geo="ND"):
        r = g[(g.id == i) & (g.geo == geo)]
        return r.iloc[0] if len(r) else None

    a, au = gl("applications"), gl("applications", "US")
    e, eu = gl("establishments"), gl("establishments", "US")
    rp, rpu = gl("real_pay"), gl("real_pay", "US")
    h, hu = gl("herd"), gl("herd", "US")
    ma, mj = meta["applications"], meta["private_jobs"]
    st.subheader("Key messages")
    c = st.columns(3)
    with c[0]:
        st.markdown("**Evolving dynamics**")
        st.markdown(
            f"- Business applications grew {a.long:+.1f}% a year over {a.long_period} (US {au.long:+.1f}%).\n"
            f"- Business locations with employees grew {e.long:+.1f}% a year over {e.long_period} (US {eu.long:+.1f}%).\n"
            f"- Real average pay grew {rp.long:+.1f}% a year over {rp.long_period} (US {rpu.long:+.1f}%).\n"
            f"- University R&D grew {h.long:+.1f}% a year over {h.long_period} (US {hu.long:+.1f}%).")
        link_row([("Evolving dynamics", "evolving-dynamics")])
    with c[1]:
        st.markdown("**Current realities**")
        det = lib.table("diffusion_detail.csv")
        plain = {"Establishment closing rate": "fewer establishment closings"}
        up = det[det.improving].indicator.replace(plain).tolist()
        down = det[~det.improving].indicator.replace({"Establishment closing rate": "more establishment closings"}).tolist()
        st.markdown(
            f"- {last.improving_share:.0f}% of business and innovation indicators are better than a year earlier.\n"
            f"- Improving: {', '.join(up[:4]).lower()}{'…' if len(up) > 4 else ''}.\n"
            f"- Weaker: {', '.join(down[:4]).lower() if down else 'none'}{'…' if len(down) > 4 else ''}.")
        link_row([("Current realities", "current-realities")])
    with c[2]:
        st.markdown("**Future implications**")
        st.markdown(
            f"- Business applications: about {ma['next_total']:,.0f} in the next 12 months ({ma['change_pct']:+.1f}%), "
            f"80% range {ma['next_total_lo']:,.0f} to {ma['next_total_hi']:,.0f}.\n"
            f"- Private-sector jobs: about {mj['next_total']:,.0f} on average over the next 4 quarters "
            f"({mj['change_pct']:+.1f}%).\n"
            f"- Statistical outlooks, tested on past data; not official forecasts.")
        link_row([("Future implications", "future-implications")])

    fc = lib.table("outlook_forecast.csv", parse_dates=["date"])
    d = fc[fc.series == "applications"]
    act = d[(d.kind == "actual") & (d.date >= d.date.max() - pd.DateOffset(years=4))]
    f = d[d.kind == "forecast"]
    fig = go.Figure()
    fig.add_scatter(x=list(f.date) + list(f.date[::-1]), y=list(f.hi) + list(f.lo[::-1]), fill="toself",
                    fillcolor="rgba(0,154,68,.18)", line=dict(width=0), name="80% range", hoverinfo="skip")
    fig.add_scatter(x=act.date, y=act.value, name="Actual", mode="lines", line=dict(color=lib.UND_GRAY, width=2),
                    hovertemplate="%{y:,.0f}")
    j = pd.concat([act.tail(1), f])
    fig.add_scatter(x=j.date, y=j.value, name="Outlook", mode="lines", line=dict(color=lib.UND_GREEN, width=2.6, dash="dot"),
                    hovertemplate="%{y:,.0f}")
    lib.show(lib.layout(fig, 380, "Applications per month"), "ov_apps",
             title="North Dakota business applications: recent months and the 12-month outlook")
    st.markdown('<div class="small-label">Explore</div>', unsafe_allow_html=True)
    link_row([("Business pulse", "pulse"), ("Industry profiles", "industry"), ("Market finder", "market"),
              ("Peer scorecard", "scorecard"), ("Indicators", "indicators"), ("What-if impact", "what-if")])
    lib.method_panel(["Cards: latest value and change from a year earlier (monthly series compare 3-month averages). "
                      "Green = better for business conditions.",
                      "Key messages are generated from the latest data each time the data are updated."])
    lib.source_line("bfs", "qcew_q", "bds", "taxable_sales", "herd", "sbir")


# ------------------------------------------------------------------ evolving dynamics
def shade(fig, y0):
    for i, (name, a, b) in enumerate(PHASES):
        if b < y0:
            continue
        fig.add_vrect(x0=max(a, y0) - 0.5, x1=min(b, 2026) + 0.5, fillcolor="rgba(174,174,174,.10)" if i % 2 else
                      "rgba(0,0,0,0)", line_width=0, annotation_text=name, annotation_position="top left",
                      annotation_font=dict(size=10, color=lib.MUTED))


def evolving_page():
    lib.header("Evolving dynamics", "Long term (up to 20 years) and medium term (5 years): how North Dakota's business "
               "and innovation economy has changed through the oil boom, the bust, the pandemic and since.",
               "official", "estimate", note="Growth rates and phases: IPBA calculations from public data.")
    if not ready("dynamics_growth.csv", "dynamics_series.csv", "dynamics_phases.csv"):
        return
    g = lib.table("dynamics_growth.csv")
    s = lib.table("dynamics_series.csv")
    ph = lib.table("dynamics_phases.csv")
    nd = g[g.geo == "ND"].set_index("id")
    us = g[g.geo == "US"].set_index("id")
    c = st.columns(4)
    for col, i in zip(c, ["applications", "establishments", "real_pay", "herd"]):
        r = nd.loc[i]
        col.metric(f"{r['name']}, {r.long_period}", fmt_growth(r.long, r.kind),
                   f"US {fmt_growth(us.loc[i].long, r.kind)}", delta_color="off", delta_arrow="off")
    tab = g.pivot_table(index=["name", "kind"], columns="geo", values=["long", "medium", "short"], aggfunc="first")
    rows = []
    for (name, kind), r in tab.iterrows():
        per = g[(g.name == name) & (g.geo == "ND")].iloc[0]
        rows.append({"Measure": name, "Long term": per.long_period, "ND": fmt_growth(r[("long", "ND")], kind),
                     "US": fmt_growth(r.get(("long", "US")), kind), "Medium term": per.medium_period,
                     "ND ": fmt_growth(r[("medium", "ND")], kind), "US ": fmt_growth(r.get(("medium", "US")), kind),
                     "Latest year": per.short_period, "ND  ": fmt_growth(r[("short", "ND")], kind),
                     "US  ": fmt_growth(r.get(("short", "US")), kind)})
    st.subheader("Growth over three horizons: North Dakota and the US")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Compound yearly growth; for rates (opening rate, young-firm share) the change in percentage points. "
               "Each measure's horizons end at its latest data year.")

    names = dict(zip(g.name, g.id))
    lab = st.selectbox("Measure over time", list(dict.fromkeys(g.name)), key="ev_measure")
    i = names[lab]
    kind = g[g.id == i].kind.iloc[0]
    d = s[s.id == i].copy()
    if kind == "growth":
        y0 = int(d.year.min())
        base = d[d.year == d.groupby("geo").year.transform("min")].set_index("geo").value
        d["value"] = d.value / d.geo.map(base) * 100
        ytitle = f"Index (first year = 100)"
    else:
        ytitle = "%"
    fig = lib.geo_lines(d, "year", "value", ytitle=ytitle, fmt=".1f", h=420)
    shade(fig, int(d.year.min()))
    lib.show(fig, "ev_chart", title=f"{lab}: North Dakota and the US")
    t2 = d.pivot_table(index="year", columns="geo", values="value").rename(columns=PEER_NAMES).reset_index()
    lib.data_table(t2.round(2), key=f"dynamics_{i}")
    p = ph[ph.id == i]
    if len(p):
        order = [x[0] for x in PHASES]
        fig = go.Figure()
        for geo in ("US", "ND"):
            q = p[p.geo == geo].set_index("phase").reindex(order).dropna(subset=["value"])
            fig.add_bar(x=q.index, y=q.value, name=PEER_NAMES[geo], marker=dict(color=lib.GEO_COLORS[geo], line=dict(width=0)),
                        text=q.years, hovertemplate="%{x} (%{text}): %{y:.1f}")
        fig.add_hline(y=0, line_color=lib.UND_GRAY, line_width=1)
        fig.update_layout(barmode="group", hovermode="x unified")
        lib.show(lib.layout(fig, 360, "% a year" if kind == "growth" else "points a year"), "ev_phase",
                 title=f"{lab}: average yearly change by phase")
    st.markdown("**What stands out.** " + messages(g))
    lib.method_panel([
        "Long term: up to 20 years, as far as each source goes; medium term: 5 years; latest year: last year vs the one before.",
        "Real pay: QCEW average annual pay deflated by the PCE price index (BEA NIPA Table 1.1.4).",
        "Phases of North Dakota's economy: before the oil boom (to 2010), Bakken boom (2011-2015), oil bust (2016-2017), "
        "recovery and pandemic (2018-2021), after the pandemic (2022 on).",
        "Business locations and employment over 20 years come from Census BDS (to 2023); QCEW starts in 2015 here."],
        ["haltiwanger2013", "decker2014"])
    lib.source_line("bfs", "bds", "qcew", "herd", "sbir")


def messages(g):
    nd = g[g.geo == "ND"].set_index("id")
    us = g[g.geo == "US"].set_index("id")
    out = []
    for i in ("applications", "establishments", "private_jobs", "real_pay", "herd"):
        if i in nd.index and i in us.index:
            a, b = nd.loc[i], us.loc[i]
            word = "faster than" if a.long > b.long + 0.1 else ("slower than" if a.long < b.long - 0.1 else "about as fast as")
            out.append(f"{a['name']} grew {word} the US over {a.long_period} ({fmt_growth(a.long, a.kind)} vs "
                       f"{fmt_growth(b.long, b.kind)}).")
    return " ".join(out)
