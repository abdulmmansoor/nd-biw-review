"""Industry profiles: jobs, pay and establishments by industry (QCEW), location quotients, GDP by industry (BEA)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from analysis import SMALL_BASE, clusters, dynamic_shift_share, economic_base, latest_complete_year, shift_share
from config import PEERS as STATE_FIPS
from lib import COUNTIES, PEER_NAMES, REGIONS, SHORT

PLACES = ["North Dakota"] + list(REGIONS) + [f"{c} County" for c in sorted(COUNTIES.values())]


def estimate_note(d, year):
    """For planning regions: how much of the private jobs shown was estimated for counties BLS withheld."""
    s = d[(d.year == year) & (d.own == "5") & (d.industry != "10") & d.jobs.notna()]
    if "estimated" not in s or not s.estimated.fillna(False).astype(bool).any():
        return ""
    share = (s.estimated_share.fillna(0) * s.jobs).sum() / s.jobs.sum()
    return (f" Region figures add up the region's counties; where BLS withheld a county, its jobs and wages are estimated "
            f"from the state total less published counties, shared by establishment counts (about {share:.0f}% of the "
            "private jobs shown here). Only region totals are shown, never the county estimates.")


def qcew_section(q, place, year):
    d = q[q.place == place]
    cur, prev = d[d.year == year], d[d.year == year - 1]

    def total(t, own="0"):
        r = t[(t.own == own) & (t.industry == "10")]
        return r.iloc[0] if len(r) else None

    tc, tp, pc = total(cur), total(prev), total(cur, "5")
    k = st.columns(4)
    k[0].metric(f"Jobs, {year} average", lib.num(tc.jobs),
                lib.pct((tc.jobs / tp.jobs - 1) * 100) + " vs year before" if tp is not None else None)
    k[1].metric("Average annual pay", lib.money(tc.avg_pay),
                lib.pct((tc.avg_pay / tp.avg_pay - 1) * 100) + " vs year before" if tp is not None else None)
    k[2].metric("Establishments", lib.num(tc.estabs))
    k[3].metric("Private-sector share of jobs", lib.pct(pc.jobs / tc.jobs * 100 if pc is not None else None, signed=False))

    s = cur[(cur.own == "5") & (cur.industry != "10")].copy()
    s["name"] = s.industry.map(SHORT)
    sp = prev[(prev.own == "5") & (prev.industry != "10")].set_index("industry").jobs
    s["change"] = (s.jobs / s.industry.map(sp) - 1) * 100
    hidden = s[~s.disclosed.astype(bool)].name.tolist()

    cols = st.columns(2)
    with cols[0]:
        v = s.dropna(subset=["jobs"]).sort_values("jobs")
        fig = go.Figure(go.Bar(y=v.name, x=v.jobs, orientation="h", marker=dict(color=lib.ACCENT, cornerradius=3),
                               hovertemplate="%{y}: %{x:,.0f} jobs<extra></extra>"))
        lib.show(lib.layout(fig, 520, legend=False), "ind_jobs", title=f"Private jobs by industry, {year}")
    with cols[1]:
        v = s[s.lq_jobs > 0].sort_values("lq_jobs")
        small = v.jobs < SMALL_BASE
        fig = go.Figure(go.Bar(y=v.name, x=v.lq_jobs, orientation="h",
                               marker=dict(color=[lib.UND_GRAY if b else lib.SECOND for b in small], cornerradius=3),
                               customdata=[f" (small base: {j:,.0f} jobs)" if b else "" for j, b in zip(v.jobs, small)],
                               hovertemplate="%{y}: %{x:.2f}%{customdata}<extra></extra>"))
        fig.add_vline(x=1, line_dash="dash", line_color="gray", annotation_text="US average = 1",
                      annotation_position="top")
        fig.update_xaxes(type="log")
        lib.show(lib.layout(fig, 520, legend=False), "ind_lq", title=f"Concentration compared with the US (location quotient), {year}")
    st.caption("A location quotient above 1 means the industry's share of local jobs is larger than its share of US "
               "jobs (2 = twice as concentrated); a sign of local specialization. Shown on a log scale. "
               f"Gray bars rest on fewer than {SMALL_BASE} jobs (small base): one employer can swing them, so read "
               "them with care. "
               + (f"Not disclosed by BLS to protect individual employers: {', '.join(hidden)}." if hidden else ""))
    s["base"] = s.jobs.map(lambda j: "small base" if pd.notna(j) and j < SMALL_BASE else "")
    t = s.sort_values("jobs", ascending=False)[["name", "estabs", "jobs", "avg_pay", "lq_jobs", "base", "change"]].rename(columns={
        "name": "Industry", "estabs": "Establishments", "jobs": "Jobs", "avg_pay": "Average annual pay ($)",
        "lq_jobs": "Location quotient", "base": f"LQ note (< {SMALL_BASE} jobs)", "change": "Job change vs year before (%)"})
    st.dataframe(t, hide_index=True, width="stretch",
                 column_config={"Location quotient": st.column_config.NumberColumn(format="%.2f"),
                                "Job change vs year before (%)": st.column_config.NumberColumn(format="%+.1f"),
                                "Average annual pay ($)": st.column_config.NumberColumn(format="dollar")})
    st.caption("Cells showing \"None\" are not disclosed (try an earlier year for a fuller picture). Covers jobs covered by unemployment insurance (most wage and salary jobs); "
               "the self-employed are on the Market finder page." + estimate_note(d, year))

    c = st.columns([1, 2])
    lab = c[0].selectbox("Industry", list(SHORT.values()), key="ind_trend", index=list(SHORT).index("21"))
    ind = {v: k for k, v in SHORT.items()}[lab]
    with c[1]:
        geos = lib.pick_places("ind_trend_places")
    codes = {f"{f}000": g for g, f in STATE_FIPS.items()} | {"US000": "US"}
    tr = q[q.area.isin(codes) & (q.own == "5") & (q.industry == ind)].dropna(subset=["jobs"]).copy()
    tr["geo"] = tr.area.map(codes)
    tr = tr[tr.geo.isin(geos)]
    tr["index"] = tr.jobs / tr.groupby("geo").jobs.transform("first") * 100
    lib.show(lib.geo_lines(tr, "year", "index", ytitle="Index", fmt=".1f", h=320), "ind_trend_chart", title="Job trend by industry: North Dakota, neighbors and the US (index, first year = 100)")
    lib.data_table(tr.pivot_table(index="year", columns="geo", values="jobs").rename(columns=PEER_NAMES).reset_index(),
                   "Trend data (jobs)", key="industry_job_trend")


def cluster_section(q, place, area, year):
    span_max = year - int(q[q.area == area].year.min())
    if span_max < 1:
        st.info("Pick a later year: growth needs at least two years of data.")
        return
    spans = list(range(1, min(span_max, 10) + 1))
    span = st.select_slider("Growth measured over (years)", spans, value=min(5, span_max), key="cl_span")
    t = clusters(q, area, year, span)
    tg = t.attrs["total_growth"]
    t["name"] = t.industry.map(SHORT)
    t["base"] = (t.jobs < SMALL_BASE).map({True: "small base", False: ""})
    # Label the big or outlying industries only; the crowd near the centre is read by hover or the table.
    big = t.jobs >= t.jobs.nlargest(5).min()
    out = (t.lq > 1.6) | (t.lq < 0.6) | ((t.growth - (tg if pd.notna(tg) else 0)).abs() > 1.5)
    label = t.name.where(big | out, "")
    fig = go.Figure(go.Scatter(
        x=t.lq, y=t.growth, mode="markers+text", text=label, textposition="top center", textfont=dict(size=10),
        hovertext=t.name,
        marker=dict(size=t.jobs, sizemode="area", sizeref=2 * t.jobs.max() / 55 ** 2, sizemin=6, color=lib.ACCENT,
                    opacity=.7, line=dict(color="white", width=1)),
        customdata=t[["jobs", "quadrant", "base"]], hovertemplate="<b>%{hovertext}</b><br>Location quotient %{x:.2f}<br>"
        "Job growth %{y:+.1f}% a year<br>%{customdata[0]:,.0f} jobs %{customdata[2]}<br>%{customdata[1]}<extra></extra>"))
    fig.add_vline(x=1, line_dash="dash", line_color="gray")
    if pd.notna(tg):
        fig.add_hline(y=tg, line_dash="dash", line_color="gray",
                      annotation_text=f"All private jobs: {tg:+.1f}% a year", annotation_position="bottom right")
    fig.update_xaxes(type="log", title="Location quotient (log scale; right of 1 = more concentrated than the US)")
    lib.show(lib.layout(fig, 520, "Job growth, % a year", legend=False), "cl_chart", title=f"Industry clusters in {place}: concentration against job growth, {year - span}-{year}")
    st.caption("Bubble size = jobs. Upper right: industries more concentrated here than in the US and growing faster "
               "than the local average. Industries BLS did not disclose are left out. "
               "Small places and short periods give noisy growth rates."
               + (f" {int((t.jobs < SMALL_BASE).sum())} industries here have fewer than {SMALL_BASE} jobs (small base): "
                  "their position can change with one hire or closure." if (t.jobs < SMALL_BASE).any() else ""))
    lib.data_table(t[["name", "jobs", "lq", "base", "growth", "quadrant"]].rename(columns={
        "name": "Industry", "jobs": f"Jobs, {year}", "lq": "Location quotient", "base": "LQ note",
        "growth": "Job growth (% a year)", "quadrant": "Position"}).round(2), key="clusters")

    b = economic_base(q, area, year)
    b["name"] = b.industry.map(SHORT)
    priv = q[(q.area == area) & (q.year == year) & (q.own == "5") & (q.industry == "10")].jobs
    k = st.columns(2)
    k[0].metric("Estimated export-oriented private jobs", lib.num(b.base_jobs.sum()))
    k[1].metric("Share of private jobs",
                lib.pct(b.base_jobs.sum() / priv.iloc[0] * 100 if len(priv) and priv.iloc[0] else None, signed=False))
    v = b[b.base_jobs > 0].sort_values("base_jobs")
    fig = go.Figure(go.Bar(y=v.name, x=v.base_jobs, orientation="h", marker=dict(color=lib.ACCENT, cornerradius=3),
                           hovertemplate="%{y}: %{x:,.0f} jobs<extra></extra>"))
    lib.show(lib.layout(fig, 80 + 28 * len(v), legend=False), "base_chart", title=f"Economic base: jobs that likely serve customers outside {place}, {year}")
    st.caption("Location-quotient method: in an industry with a location quotient above 1, the jobs above the US "
               "share are counted as serving outside customers (sales to other states or countries, or visitors). "
               "A rough estimate: it assumes US-average demand and productivity and ignores two-way trade. "
               "Industries BLS did not disclose are left out."
               + (" In a county, a few industries with small job counts can carry much of the estimate; see the LQ "
                  "note column." if area != "38000" else ""))
    b["base"] = (b.jobs < SMALL_BASE).map({True: "small base", False: ""})
    lib.data_table(b[["name", "jobs", "lq_jobs", "base", "base_jobs"]].rename(columns={
        "name": "Industry", "jobs": "Jobs", "lq_jobs": "Location quotient", "base": "LQ note",
        "base_jobs": "Export-oriented jobs"}).round(2), key="economic_base")


def shift_share_section(q, place, area):
    years = sorted(int(y) for y in q[q.area == area].year.unique())
    if len(years) < 2:
        st.info("Not enough years of data for this place.")
        return
    try:
        default_end = latest_complete_year(q, area)
    except ValueError:
        default_end = years[-1]
    c = st.columns([1, 1, 2])
    start = c[0].selectbox("From", years[:-1], index=0, key="ss_start")
    ends = [y for y in years if y > start]
    end = c[1].selectbox("To", ends, index=ends.index(default_end) if default_end in ends else len(ends) - 1,
                         key="ss_end")
    kind = c[2].radio("Method", ["Dynamic (year by year)", "Classic (start and end years)"], horizontal=True,
                      key="ss_kind", help="Dynamic shift-share adds up the parts for each year, so the result does not "
                      "hang on the industry mix of the start year (Barff & Knight, 1988). The classic method compares "
                      "only the two end years.")
    t = (dynamic_shift_share if kind.startswith("Dynamic") else shift_share)(q, area, start, end)
    t["name"] = t.industry.map(SHORT)
    k = st.columns(4)
    k[0].metric("Actual change", f"{t.change.sum():+,.0f}")
    k[1].metric("If jobs grew at the US rate", f"{t.national.sum():+,.0f}")
    k[2].metric("Industry mix", f"{t.industry_mix.sum():+,.0f}")
    k[3].metric("Local factors", f"{t.local.sum():+,.0f}")
    st.caption("Actual change = growth at the US private-sector rate + industry mix (more or fewer jobs here in "
               "industries growing fast nationally) + local factors (each industry growing faster or slower here than "
               "in the US). Local factors are where local conditions such as costs, resources, demand and policy show up. "
               "Results depend on the years chosen: in North Dakota, 2015 was still near the peak of the oil boom.")
    v = t.sort_values("local")
    fig = go.Figure(go.Bar(y=v.name, x=v.local, orientation="h", marker=dict(
        color=[lib.ACCENT if x >= 0 else lib.NEG for x in v.local], cornerradius=3),
        hovertemplate="%{y}: %{x:+,.0f} jobs<extra></extra>"))
    fig.add_vline(x=0, line_color="gray", line_width=1)
    lib.show(lib.layout(fig, 560, legend=False), "ss_chart", title="Local factors by industry: jobs gained (green) or lost (orange) compared with US industry growth")
    left = [SHORT[s] for s in t.attrs.get("left_out", [])]
    if left:
        when = f"in at least one year from {start} to {end}" if kind.startswith("Dynamic") else f"in {start} or {end}"
        st.caption(f"Left out because BLS did not disclose jobs {when}: {', '.join(left)}.")
    lib.data_table(t[["name", "jobs_start", "jobs_end", "change", "national", "industry_mix", "local"]].rename(columns={
        "name": "Industry", "jobs_start": f"Jobs {start}", "jobs_end": f"Jobs {end}", "change": "Actual change",
        "national": "US-rate growth", "industry_mix": "Industry mix", "local": "Local factors"}).round(0),
        key="shift_share")


def gdp_section():
    g = lib.table("bea_gdp.csv", dtype={"industry": str})
    last = int(g.year.max())
    st.subheader("Output by industry (GDP)")
    st.caption("Gross domestic product by industry, the value each industry adds to the economy. State level only.")
    cur = g[(g.measure == "current") & (g.year == last)]
    tot = cur[cur.industry == "total"].set_index("geo").value
    sh = cur[cur.industry != "total"].assign(share=lambda x: x.value / x.geo.map(tot) * 100)
    sh["name"] = sh.industry.map({**SHORT, "92": "Government"})
    real = g[(g.measure == "real") & (g.industry == "total")].set_index(["geo", "year"]).value
    k = st.columns(3)
    k[0].metric(f"ND GDP, {last}", lib.money(tot.get("ND") * 1e6))
    gr = (real.get(("ND", last)) / real.get(("ND", last - 1)) - 1) * 100
    k[1].metric("Real growth, ND", lib.pct(gr), f"US: {lib.pct((real.get(('US', last)) / real.get(('US', last - 1)) - 1) * 100)}",
                delta_color="off", delta_arrow="off")
    pc5 = (real.get(("ND", last)) / real.get(("ND", last - 5))) ** (1 / 5) * 100 - 100
    k[2].metric(f"ND average real growth, {last - 5}-{last}", lib.pct(pc5) + " a year")

    cols = st.columns(2)
    with cols[0]:
        v = sh[sh.geo.isin(["ND", "US"])].pivot_table(index="name", columns="geo", values="share").sort_values("ND")
        fig = go.Figure()
        for geo, color in (("US", lib.GEO_COLORS["US"]), ("ND", lib.GEO_COLORS["ND"])):
            fig.add_bar(y=v.index, x=v[geo], name=PEER_NAMES[geo], orientation="h", marker=dict(color=color, cornerradius=2),
                        hovertemplate="%{x:.1f}%")
        fig.update_layout(barmode="group", bargap=.25, bargroupgap=.08)
        lib.show(lib.layout(fig, 620, "% of GDP").update_layout(hovermode="y unified"), "gdp_share", title=f"Share of GDP, {last}: North Dakota and the US")
        lib.data_table(v.rename(columns=PEER_NAMES).round(2).reset_index().rename(columns={"name": "Industry"}),
                       key="gdp_share")
    with cols[1]:
        names = {**SHORT, "92": "Government", "total": "All industries"}
        order = ["total"] + list(SHORT) + ["92"]
        lab = st.selectbox("Industry", [names[k] for k in order], key="gdp_ind")
        ind = {names[k]: k for k in order}[lab]
        r = g[(g.measure == "real") & (g.industry == ind) & (g.year >= 2005)].dropna(subset=["value"]).copy()
        base = r[r.year == 2017].set_index("geo").value
        r["index"] = r.value / r.geo.map(base) * 100
        lib.show(lib.geo_lines(r, "year", "index", ytitle="Index", fmt=".1f", h=440), "gdp_trend", title="Real GDP growth for one industry, ND and neighbors (index, 2017 = 100)")
        lib.data_table(r.pivot_table(index="year", columns="geo", values="index").rename(columns=PEER_NAMES).round(1).reset_index(),
                       key="gdp_industry_index")
        st.caption("Real GDP is adjusted for inflation (chained 2017 dollars). Gaps mean BEA withheld the value to protect "
                   "individual businesses. Mining and oil output swings with prices and drilling.")


def target_section(q, place):
    """North Dakota's targeted industries: Commerce's definitions, IPBA's industry codes, and statewide measures."""
    st.subheader("North Dakota's targeted industries")
    st.markdown("The North Dakota Department of Commerce names six targeted industries and defines each in words. It "
                "publishes no industry codes, so IPBA assigns NAICS codes to each definition, following a published "
                "research framework where one exists (see *Definitions* below). The measures cover private employers "
                "statewide.")
    if place != "North Dakota":
        st.info("Targeted industries are shown for North Dakota as a whole; BLS withholds most of these detailed "
                "industries for counties and regions.")
    t = lib.table("target_industries.csv")
    codes = lib.table("target_industry_codes.csv", dtype={"naics": str, "naics_2017_code": str})
    year = int(t[t.headline].year.iloc[0])
    cur = t[t.year == year].copy()
    allr = cur[cur.group == "Any targeted industry"].iloc[0]
    nd = q[(q.area == "38000") & (q.own == "5") & (q.industry == "10") & (q.year == year)]
    k = st.columns(4)
    k[0].metric(f"Jobs in targeted industries, {year} (at least)", lib.num(allr.jobs),
                help="Sum of the industry codes BLS publishes; withheld codes are not included.")
    k[1].metric("Share of private jobs", lib.pct(allr.share_private_jobs * 100, signed=False))
    k[2].metric("Average annual pay", lib.money(allr.avg_pay),
                f"{lib.money(nd.avg_pay.iloc[0])} all private jobs" if len(nd) else None, delta_color="off")
    k[3].metric(f"Job change, {int(allr.from_year)}-{year}", lib.pct(allr.growth_pct))

    g = cur[cur.group != "Any targeted industry"].copy()
    g["label"] = g.group + g.proxy.map({True: " (proxy)", False: ""})
    v = g.sort_values("jobs")
    fig = go.Figure(go.Bar(y=v.label, x=v.jobs, orientation="h",
                           marker=dict(color=[lib.UND_GRAY if p else lib.ACCENT for p in v.proxy], cornerradius=3),
                           hovertemplate="%{y}: at least %{x:,.0f} jobs<extra></extra>"))
    lib.show(lib.layout(fig, 320, legend=False), "target_jobs", title=f"Private jobs by targeted industry, {year}")
    tab = g.assign(
        codes_note=g.codes_withheld.astype(int).astype(str) + " of " + g.codes.astype(int).astype(str),
        pay_vs_us=g.avg_pay / g.us_avg_pay * 100,
        window=g.from_year.astype(int).astype(str) + "-" + str(year))
    tab = tab[["label", "jobs", "share_private_jobs", "estabs", "avg_pay", "pay_vs_us", "lq", "growth_pct", "window",
               "codes_note", "estabs_withheld_share"]].rename(columns={
        "label": "Targeted industry", "jobs": "Jobs (at least)", "share_private_jobs": "Share of private jobs (%)",
        "estabs": "Establishments", "avg_pay": "Average annual pay ($)", "pay_vs_us": "Pay as % of US, same industries",
        "lq": "Location quotient", "growth_pct": "Job change (%)", "window": "Change period",
        "codes_note": "Industry codes withheld by BLS", "estabs_withheld_share": "Establishments in withheld codes (%)"})
    tab["Share of private jobs (%)"] *= 100
    tab["Establishments in withheld codes (%)"] *= 100
    st.dataframe(tab.sort_values("Jobs (at least)", ascending=False), hide_index=True, width="stretch",
                 column_config={"Share of private jobs (%)": st.column_config.NumberColumn(format="%.1f"),
                                "Average annual pay ($)": st.column_config.NumberColumn(format="dollar"),
                                "Pay as % of US, same industries": st.column_config.NumberColumn(format="%.0f"),
                                "Location quotient": st.column_config.NumberColumn(format="%.2f"),
                                "Job change (%)": st.column_config.NumberColumn(format="%+.1f"),
                                "Establishments in withheld codes (%)": st.column_config.NumberColumn(format="%.0f")})
    st.caption(f"{year} is the newest year with full detail (BLS withholds more in its first release of a year). "
               "Jobs are the sum of industry codes BLS publishes, so they are a floor: where BLS withheld a code to "
               "protect an employer, its establishments are counted but its jobs are not, and nothing is estimated. "
               "The location quotient compares those published codes with the same codes nationwide (above 1 = more "
               "concentrated in ND than in the US). Job change uses codes published in both years and one NAICS "
               "edition (technology-based business starts in 2022, when NAICS changed several of its codes). "
               "Groups overlap (for example, petroleum refining is energy and advanced manufacturing), so rows do not "
               "add up; \"any targeted industry\" counts each code once and leaves out the autonomous systems proxy.")

    tr = t[(t.year <= year) & (t.group != "Any targeted industry")]
    fig = go.Figure()
    for i, (grp, d) in enumerate(tr.groupby("group", sort=False)):
        fig.add_trace(go.Scatter(x=d.year, y=d.jobs, name=grp + (" (proxy)" if d.proxy.iloc[0] else ""),
                                 mode="lines+markers", line=dict(color=lib.PALETTE[i % len(lib.PALETTE)],
                                                                 dash=lib.DASHES[i % len(lib.DASHES)]),
                                 hovertemplate=grp + ", %{x}: %{y:,.0f} jobs<extra></extra>"))
    fig.add_vline(x=2021.5, line_dash="dot", line_color="gray", annotation_text="NAICS 2022", annotation_position="top")
    lib.show(lib.layout(fig, 380, ytitle="Jobs (published codes)"), "target_trend",
             title=f"Private jobs in targeted industries, 2017-{year}")
    st.caption("Year-to-year moves can partly reflect which codes BLS withheld that year. From 2022, technology-based "
               "business uses NAICS 2022 codes (software publishers, for example, gained activities moved from other "
               "codes), so compare it within the periods before and after the line.")
    lib.data_table(tr.pivot_table(index="year", columns="group", values="jobs").reset_index(),
                   "Trend data (jobs in published codes)", key="target_trend_table")

    with st.expander("Definitions: Commerce's words and IPBA's industry codes"):
        for grp in g.group:
            r = g[g.group == grp].iloc[0]
            st.markdown(f"**{grp}**" + (" (proxy)" if r.proxy else ""))
            st.markdown(f"> Commerce: “{r.commerce_definition}”")
            st.markdown(f"IPBA industry codes: {r.ipba_codes}")
        pick = st.selectbox("Show the industry codes for", list(g.group), key="target_codes_group")
        c = codes[codes.group == pick].copy()
        c["status"] = c.apply(lambda r: "withheld by BLS" if r.withheld else ("no ND employers" if r.estabs == 0 else ""),
                              axis=1)
        st.dataframe(c[["naics", "naics_2017_code", "title", "estabs", "jobs", "avg_pay", "lq", "status"]].rename(columns={
            "naics": "NAICS 2022", "naics_2017_code": "NAICS 2017 (before 2022)", "title": "Industry",
            "estabs": "Establishments", "jobs": "Jobs", "avg_pay": "Average annual pay ($)",
            "lq": "Location quotient", "status": "Note"}), hide_index=True, width="stretch",
            column_config={"Average annual pay ($)": st.column_config.NumberColumn(format="dollar"),
                           "Location quotient": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Commerce's definitions are from its Operation Intern Guidelines (program year 2025-27). Brookings' "
                   "advanced industries (Muro et al., 2015) are the 50 industries with R&D of at least $450 per worker "
                   "and a share of STEM jobs at or above the US average (21%), from its Table A-5. These groups are "
                   "for measurement only; they do not decide eligibility for any Commerce program.")
    lib.source_line("qcew", "commerce_targets", "brookings_ai")


def withheld_share(q, place):
    """Share of private industries BLS withheld for a place, by year."""
    p = q[(q.place == place) & (q.own == "5") & (q.industry != "10")]
    years = sorted(q[q.place == place].year.unique())
    return (~p.disclosed.astype(bool)).groupby(p.year).mean().reindex(years, fill_value=1.0)


def default_year(withheld):
    """Index (newest first) of the year to open on: the newest year, unless it withholds clearly more industries
    (over 5 points) than the year before, in which case the year before."""
    w = withheld.sort_index(ascending=False)
    return 1 if len(w) > 1 and w.iloc[0] > w.iloc[1] + .05 else 0


def page():
    lib.header("Industry profiles", "Which industries employ people and pay well in North Dakota and each county, "
               "where the state is specialized compared with the US, what drives job change, and how each "
               "industry's output is growing.", "official", "estimate",
               note="BLS and BEA. Clusters, economic base and shift-share: IPBA calculations.")
    if not lib.ready():
        return
    q = lib.table("qcew_annual.csv", dtype={"area": str, "own": str, "industry": str})
    c = st.columns([2, 1])
    place = c[0].selectbox("Place", PLACES, key="ind_place").removesuffix(" County")
    withheld = withheld_share(q, place)
    years = sorted(withheld.index, reverse=True)
    year = c[1].selectbox("Year", years, index=default_year(withheld), key="ind_year",
                          format_func=lambda y: f"{y} ({withheld[y]:.0%} of industries withheld)" if withheld[y] >= .05 else str(y),
                          help="BLS withholds industries with few businesses. The newest year usually has more withheld "
                               "until BLS revises it, so the page opens on the year with fuller detail.")
    area = q[q.place == place].area.iloc[0]
    tabs = st.tabs(["Jobs and pay", "Clusters and economic base", "What drives job change", "Output (GDP)",
                    "Targeted industries"])
    with tabs[0]:
        qcew_section(q, place, year)
    with tabs[1]:
        cluster_section(q, place, area, year)
    with tabs[2]:
        shift_share_section(q, place, area)
    with tabs[3]:
        gdp_section()
    with tabs[4]:
        target_section(q, place)
    lib.method_panel([
        "Jobs, pay and establishments: BLS QCEW annual averages, private ownership by NAICS sector; government by level.",
        "Location quotient (LQ): the industry's share of local jobs divided by its share of US jobs, as published by BLS.",
        "Cluster position: LQ against yearly job growth; the dashed line is growth of all private jobs in the place.",
        "Economic base: for industries with LQ > 1, jobs x (1 - 1/LQ) are counted as serving outside customers.",
        "Shift-share: change = jobs at start x US private growth + jobs at start x (US industry growth - US private "
        "growth) + jobs at start x (local industry growth - US industry growth). Undisclosed industries are left out. "
        "The dynamic version (default) computes this for each pair of consecutive years and adds the yearly parts.",
        f"LQs resting on fewer than {SMALL_BASE} jobs are flagged \"small base\"; they are shown, not hidden.",
        "GDP: BEA GDP by state and industry, current dollars for shares and chained 2017 dollars for growth.",
        "Planning regions: county figures added up. Where BLS withheld a county, its jobs and wages are estimated from "
        "the state total less published counties and the county-unknown line, shared by establishment counts "
        "(Isserman & Westervelt, 2006). Only region totals are shown; a region cell stays withheld when it would equal "
        "the withheld total exactly or when BLS withheld the state figure. Region LQs are computed as BLS does.",
        "Targeted industries: Commerce's six definitions (Operation Intern Guidelines, 2025-27) turned into NAICS codes "
        "by IPBA. Advanced manufacturing and technology-based business are the manufacturing and service industries "
        "among Brookings' 50 advanced industries (Muro et al., 2015); value-added agriculture follows USDA's "
        "change-in-physical-state test; tourism uses the core industries of BEA's Travel and Tourism Satellite "
        "Account without food services; autonomous systems is a labelled proxy. Jobs sum the "
        "codes BLS publishes; withheld codes are never estimated."],
        ["isserman1977", "isserman_westervelt2006", "tiebout1956", "porter2003", "stevens_moore1980", "barff_knight1988",
         "muro2015"])
    lib.source_line("qcew", "bea")


if __name__ == "__main__":
    page()
