"""Innovation: one view of North Dakota across five fields (research and development, invention and
commercialization, entrepreneurship and startup capital, technology economy, talent and connectivity), next to the peer
states and the US."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

GEOS = ["ND", "MN", "MT", "SD", "WY", "US"]
FMT = {"$": "${:,.2f}", "patents": "{:,.1f}", "offerings": "{:,.2f}", "%": "{:.1f}%", "%2": "{:.2f}%", "LQ": "{:.2f}",
       "per1k": "{:,.1f}"}


def ready():
    need = ["innovation_scorecard.csv", "innovation_trends.csv"]
    if not all((OUT / f).exists() for f in need):
        st.info("The innovation tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def messages(c):
    """Strengths and gaps worded from the scorecard: rank among the five states and the ratio to the US."""
    good, gaps = [], []
    for r in c.itertuples():
        f = FMT.get(r.unit, "{:,.2f}")
        us = f" (US {f.format(r.US)})" if pd.notna(r.US) else ""
        rank = f"{int(r.nd_rank)} of {int(r.states_ranked)} states" if pd.notna(r.nd_rank) else None
        if rank and unclear(getattr(r, "rank_clear", None)):
            rank += " (within the margin of error)"
        line = f"**{r.measure}**: {f.format(r.ND)}{us}" + (f", rank {rank}" if rank else "") + f" ({r.period})."
        strong = (pd.notna(r.nd_rank) and r.nd_rank <= 2) or (pd.isna(r.nd_rank) and r.nd_vs_us >= 1.1)
        weak = (pd.notna(r.nd_rank) and r.nd_rank >= 4) or (
            (pd.isna(r.nd_rank) or r.nd_rank == 3) and pd.notna(r.nd_vs_us) and r.nd_vs_us < 0.7)
        if strong and not weak:
            good.append(line)
        elif weak:
            gaps.append(line)
    return good, gaps


def scorecard(c):
    st.subheader("Scorecard: North Dakota, its neighbors and the US")
    good, gaps = messages(c)
    cols = st.columns(2)
    with cols[0]:
        with st.container(border=True):
            st.markdown("**Where North Dakota stands out**")
            st.markdown(lib.esc("\n".join(f"- {x}" for x in good)) if good else "None of the measures this period.")
    with cols[1]:
        with st.container(border=True):
            st.markdown("**Where North Dakota trails**")
            st.markdown(lib.esc("\n".join(f"- {x}" for x in gaps)) if gaps else "None of the measures this period.")
    fields = list(dict.fromkeys(c.field)) if "field" in c else [None]
    for f in fields:
        part = c[c.field == f] if f else c
        st.markdown(f"**{f}**" if f else "")
        t = part.copy()
        for g in GEOS:
            t[g] = [cell(u, v, part.get(f"{g}_moe", pd.Series(index=part.index)).get(i))
                    for i, u, v in zip(part.index, part.unit, part[g])]
        t["ND rank (of 5)"] = [("–" if pd.isna(v) else f"{int(v)}" + (" ±" if unclear(k) else ""))
                               for v, k in zip(part.nd_rank, part.get("rank_clear", pd.Series(index=part.index)))]
        t["ND vs US"] = part.nd_vs_us.map(lambda v: "–" if pd.isna(v) else f"{v:.2f}x")
        t["ND change"] = [("–" if pd.isna(v) else f"{v:+.0f}% ({p})") for v, p in zip(part.nd_change_pct, part.change_period)]
        st.dataframe(t[["measure", "period", *GEOS, "ND rank (of 5)", "ND vs US", "ND change", "source"]]
                     .rename(columns={"measure": "Measure", "period": "Period", "source": "Source", **PEER_NAMES}),
                     hide_index=True, width="stretch")
    st.caption("Rank among North Dakota, Minnesota, Montana, South Dakota and Wyoming (1 = highest). Each measure is "
               "per resident, per dollar of GDP or a share, so states of different size compare; no overall index is "
               "formed, because the measures are on different scales. STEM occupations and STEM degrees are compared "
               "with the US only (state detail for the peers is not built). Census ACS figures are 2020-2024 averages "
               "with 90% margins of error (±); a rank marked ± is within the margin of error of a neighboring state. "
               "Wyoming's business applications and Form D counts are inflated by companies that register there but "
               "operate elsewhere.")


def unclear(k):
    """rank_clear is False (read from CSV as bool or text) when the rank is within the margin of error."""
    return k is not None and not (isinstance(k, float) and pd.isna(k)) and str(k) in ("False", "0", "0.0")


def cell(unit, v, moe=None):
    if pd.isna(v):
        return "–"
    txt = FMT.get(unit, "{:,.2f}").format(v)
    return txt + (f" ± {moe:.1f}" if moe is not None and pd.notna(moe) else "")


def trends():
    tr = lib.table("innovation_trends.csv")
    st.subheader("Trends")
    c = st.columns([2, 2])
    m = c[0].selectbox("Measure", list(dict.fromkeys(tr.measure)), key="inn_measure")
    geos = c[1].multiselect("Places", GEOS, default=["ND", "MN", "SD", "US"], key="inn_geos", format_func=PEER_NAMES.get)
    d = tr[(tr.measure == m) & tr.geo.isin(geos)]
    fig = go.Figure()
    for i, g in enumerate(geos):
        e = d[d.geo == g].sort_values("year")
        fig.add_trace(go.Scatter(x=e.year, y=e.value, name=PEER_NAMES[g], mode="lines+markers",
                                 line=dict(color=lib.GEO_COLORS.get(g, lib.UND_GRAY), dash=lib.DASHES[i % len(lib.DASHES)],
                                           width=3 if g == "ND" else 1.6),
                                 hovertemplate=PEER_NAMES[g] + ", %{x}: %{y:,.2f}<extra></extra>"))
    lib.layout(fig, 360, ytitle=m)
    lib.show(fig, "inn_trend", title=m)
    lib.data_table(d.pivot_table(index="year", columns="geo", values="value").round(2).reset_index(),
                   f"{m} (table)", key="inn_trend_t")
    st.caption("Small states swing from year to year (a few awards or patents move the rate), so read the trend over "
               "several years.")


def inside_nd():
    st.subheader("Inside North Dakota")
    cols = st.columns(2)
    if (OUT / "patents_nd_region.csv").exists():
        pr = lib.table("patents_nd_region.csv")
        s = lib.table("patents_state.csv")
        done = int(s[(s.geo == "ND") & s.complete_year.astype(bool)].year.max())
        w = pr[pr.year.between(done - 9, done)].groupby("region").patents.sum().sort_values()
        with cols[0]:
            fig = go.Figure(go.Bar(y=w.index, x=w.values, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                                   hovertemplate="%{y}: %{x:,.0f} patents<extra></extra>"))
            lib.layout(fig, 330, legend=False).update_xaxes(title="Patents")
            lib.show(fig, "inn_pat_region", title=f"Patents by planning region, {done - 9}-{done}")
    if (OUT / "patents_nd_owner.csv").exists():
        po = lib.table("patents_nd_owner.csv")
        last = po[po.year.between(done - 9, done)].groupby("owner").patents.sum().sort_values()
        with cols[1]:
            fig = go.Figure(go.Bar(y=last.index, x=last.values, orientation="h",
                                   marker=dict(color=lib.SECOND, line=dict(width=0)),
                                   hovertemplate="%{y}: %{x:,.0f} patents<extra></extra>"))
            lib.layout(fig, 330, legend=False).update_xaxes(title="Patents")
            lib.show(fig, "inn_pat_owner", title=f"Who owns ND inventors' patents, {done - 9}-{done}")
    st.caption("Patents are counted by the first-named inventor's county and by the type of first owner (assignee). "
               "Patents measure invention, not its commercial use.")
    st.markdown("**Go deeper:** SBIR/STTR by agency and region, Form D capital, and the occupations behind technology "
                "industries on [Business support insights](business-support); the targeted industries on "
                "[Industry profiles](industry); the advanced manufacturing and technology case on "
                "[Case studies](case-studies); graduates by field on [Workforce and talent](workforce).")


def page():
    lib.header("Innovation", "North Dakota across five fields of innovation: research and development, invention and "
               "commercialization, entrepreneurship and startup capital, the technology economy, and talent and "
               "connectivity, next to Minnesota, Montana, South Dakota, Wyoming and the US.", "official", "estimate",
               note="NSF, USPTO, SBA, Census, SEC, BLS and NCES; per-resident rates, ranks and shares: IPBA calculations.")
    if not ready():
        return
    c = lib.table("innovation_scorecard.csv")
    scorecard(c)
    st.divider()
    trends()
    st.divider()
    inside_nd()
    lib.method_panel([
        "University R&D: NSF Higher Education Research and Development Survey, all R&D expenditures by fiscal year, "
        "per resident (Census population estimates).",
        "Business R&D: NSF/Census Business Enterprise R&D Survey, R&D performed by companies in the state from all "
        "sources of funds, as a share of state GDP (BEA, current dollars). Federal R&D: NSF Survey of Federal Funds for "
        "R&D, obligations by the state where the work is done, 3-year average per resident (yearly amounts are lumpy).",
        "Patents: utility patents by grant year and first-named inventor's state (PatentsView), complete years only.",
        "SBIR/STTR: SBIR.gov award data by the company's state, 10-year average of dollars per resident. Form D: SEC "
        "notices of company-building raises (outside real estate, finance and pooled funds), 5-year average.",
        "Technology-based business and advanced manufacturing: ND Commerce's targeted industries as coded by IPBA "
        "(Brookings advanced industries; Muro et al., 2015), BLS QCEW private jobs; jobs in published codes only.",
        "Entrepreneurship: high-propensity business applications (Census BFS; applications likely to become employers) "
        "per 1,000 residents over the last 12 months; establishment opening rate and jobs at firms 5 years old or "
        "younger (Census BDS).",
        "STEM occupations: computer and mathematical; architecture and engineering; life, physical and social science "
        "(BLS OEWS major groups 15, 17, 19), share of all jobs. Education and broadband: Census ACS 5-year, adults 25 "
        "and older with a bachelor's degree or higher; households with a broadband subscription of any type.",
        "STEM degrees: bachelor's, master's and doctoral awards in computer science, engineering, engineering "
        "technology, biology, mathematics, physical sciences and science technologies (CIP 11, 14, 15, 26, 27, 40, 41).",
        "Ranks are positions among the five states, not scores; no composite index is formed."],
        refs=("griliches1990", "muro2015"))
    lib.source_line("herd", "berd", "fedrd", "bea", "patents", "sbir", "bfs", "bds", "formd", "qcew", "oews", "ipeds",
                    "acs", "popest")


if __name__ == "__main__":
    page()
