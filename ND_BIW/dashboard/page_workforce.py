"""Workforce and talent: how tight the labor market is, which occupations employ North Dakotans and what they pay,
and how many people North Dakota colleges and universities prepare, by field."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT

LEVELS = ["Certificate", "Associate", "Bachelor's", "Graduate certificate", "Master's", "Doctoral"]


def ready():
    need = ["workforce_jolts.csv", "workforce_oews.csv", "ipeds_completions.csv"]
    if any(not (OUT / n).exists() for n in need):
        st.info("The workforce tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def tightness(j, laus):
    """Job openings per unemployed person in North Dakota: average JOLTS openings over the latest 12 months of state
    data divided by average LAUS unemployed in the same months (Elsby et al., 2015)."""
    nd = j[j.geo == "ND"].dropna(subset=["openings"]).set_index("month").openings * 1000
    last = nd.index.max()
    months = nd[nd.index > last - pd.DateOffset(months=12)].index
    u = laus[laus.place == "North Dakota"].set_index("month").unemployed.reindex(months).dropna()
    if not len(u):
        return None, None
    return nd.reindex(u.index).mean() / u.mean(), (u.index.min(), u.index.max())


def labor_market():
    j = lib.table("workforce_jolts.csv", parse_dates=["month"])
    st.subheader("Labor market: how tight is it?")
    laus = lib.table("laus_monthly.csv", parse_dates=["month"]) if (OUT / "laus_monthly.csv").exists() else None
    r = j.sort_values("month").copy()
    for c in ("openings_rate", "hires_rate", "quits_rate"):
        r[c + "_3m"] = r.groupby("geo")[c].transform(lambda s: s.rolling(3).mean())
    nd = r[r.geo == "ND"].dropna(subset=["openings_rate"])
    last = nd.month.max()
    us_same = r[(r.geo == "US") & (r.month == last)]
    k = st.columns(4)
    k[0].metric(f"Job openings rate, ND, {last:%b %Y}", f"{nd.openings_rate_3m.iloc[-1]:.1f}%",
                f"US {us_same.openings_rate_3m.iloc[0]:.1f}% (same months)" if len(us_same) else None,
                delta_color="off", delta_arrow="off", help="Openings as a % of jobs plus openings, 3-month average.")
    k[1].metric("Job openings, ND", f"{nd.openings.tail(3).mean() * 1000:,.0f}", "3-month average",
                delta_color="off", delta_arrow="off")
    if laus is not None:
        ratio, span = tightness(j, laus)
        if ratio is not None:
            k[2].metric("Openings per unemployed person", f"{ratio:.1f}",
                        f"{span[0]:%b %Y} to {span[1]:%b %Y}", delta_color="off", delta_arrow="off",
                        help="Above 1: more open jobs than people looking for work (a tight market).")
        st_ = laus[laus.level == "state"].sort_values("month")
        k[3].metric(f"Unemployment rate, {st_.month.iloc[-1]:%b %Y}", f"{st_.rate.iloc[-1]:.1f}%",
                    "not seasonally adjusted (BLS LAUS)", delta_color="off", delta_arrow="off")
    cols = st.columns(2)
    with cols[0]:
        lib.show(lib.geo_lines(r.dropna(subset=["openings_rate_3m"]), "month", "openings_rate_3m",
                               ytitle="% (3-month average)", fmt=".1f", h=320), "jolts_open",
                 title="Job openings rate, ND and US (%)")
    with cols[1]:
        lib.show(lib.geo_lines(r.dropna(subset=["quits_rate_3m"]), "month", "quits_rate_3m",
                               ytitle="% (3-month average)", fmt=".1f", h=320), "jolts_quits",
                 title="Quits rate: workers leaving jobs by choice (%)")
    t = r.pivot_table(index="month", columns="geo", values=["openings_rate", "hires_rate", "quits_rate"])
    t.columns = [f"{a.replace('_', ' ').capitalize()} ({g}, %)" for a, g in t.columns]
    lib.data_table(t.reset_index().assign(month=lambda x: x.month.dt.strftime("%Y-%m")).round(1), key="jolts")
    st.caption(f"State job openings, hires and quits are BLS model-based estimates (seasonally adjusted); North "
               f"Dakota data end in {last:%B %Y}, the US runs later. A higher quits rate usually means workers are "
               "confident they can find another job. BLS does not publish job openings below the state level.")
    if laus is not None:
        regional_unemployment(laus)


def regional_unemployment(laus):
    """Unemployment by planning region: latest 12-month average and change from the 12 months before (BLS LAUS)."""
    from laus import latest_12
    last = laus.month.max()
    now = latest_12(laus).set_index("place")
    before = latest_12(laus[laus.month <= last - pd.DateOffset(months=12)]).set_index("place")
    reg = now[now.level.isin(["region", "state"])].copy()
    reg["before"] = before.rate.reindex(reg.index)
    reg = reg.reindex(list(lib.REGIONS) + ["North Dakota"]).dropna(subset=["rate"])
    st.markdown(f"**Unemployment by planning region, 12 months to {last:%B %Y}**")
    fig = go.Figure(go.Bar(x=reg.index.str.replace(r" \(", "<br>(", regex=True), y=reg.rate,
                           marker=dict(color=[lib.UND_GRAY if p == "North Dakota" else lib.ACCENT for p in reg.index],
                                       line=dict(width=0)),
                           text=[f"{v:.1f}%" for v in reg.rate], textposition="outside",
                           customdata=reg.before, hovertemplate="%{x}: %{y:.1f}% (12 months before: %{customdata:.1f}%)"
                                                                "<extra></extra>"))
    lib.layout(fig, 320, "% of labor force", legend=False).update_yaxes(range=[0, reg.rate.max() * 1.25])
    lib.show(fig, "wf_reg_unemp", title="Unemployment rate by planning region (12-month average, BLS)")
    t = reg.assign(change=reg.rate - reg.before)[["labor_force", "unemployed", "rate", "before", "change"]].reset_index()
    lib.data_table(t.rename(columns={"place": "Place", "labor_force": "Labor force (avg)", "unemployed": "Unemployed (avg)",
                                     "rate": "Rate (%)", "before": "12 months before (%)", "change": "Change (points)"})
                   .round(1), "Unemployment by region (table)", key="wf_reg_unemp_t")
    st.caption("Regions add up their counties' labor force and unemployed (BLS Local Area Unemployment Statistics, not "
               "seasonally adjusted; months BLS did not publish are skipped).")


def occupations():
    o = lib.table("workforce_oews.csv")
    year = int(o.year.iloc[0])
    st.subheader(f"Occupations: jobs and pay, May {year}")
    allocc = o[o.occupation == "All occupations"].iloc[0]
    g = o[o.occupation != "All occupations"].copy()
    g["lq"] = g.nd_share / g.us_share
    k = st.columns(3)
    k[0].metric("Jobs counted", f"{allocc.nd_jobs:,.0f}", "wage and salary jobs, North Dakota", delta_color="off",
                delta_arrow="off")
    k[1].metric("Median annual wage, all occupations", f"${allocc.nd_median_wage:,.0f}",
                f"US ${allocc.us_median_wage:,.0f}", delta_color="off", delta_arrow="off")
    top = g.sort_values("lq", ascending=False).iloc[0]
    k[2].metric("Most concentrated group vs US", top.occupation, f"{top.lq:.1f} times the US share",
                delta_color="off", delta_arrow="off")
    view = st.radio("Show", ["Share of jobs", "Median annual wage"], horizontal=True, key="wf_occ_view")
    g = g.sort_values("nd_share" if view == "Share of jobs" else "nd_median_wage")
    fig = go.Figure()
    if view == "Share of jobs":
        fig.add_bar(y=g.occupation, x=g.us_share, name="United States", orientation="h",
                    marker=dict(color=lib.GEO_COLORS["US"], line=dict(width=0)), hovertemplate="US: %{x:.1f}%<extra></extra>")
        fig.add_bar(y=g.occupation, x=g.nd_share, name="North Dakota", orientation="h",
                    marker=dict(color=lib.ACCENT, line=dict(width=0)), hovertemplate="ND: %{x:.1f}%<extra></extra>")
        xt = "% of all jobs"
    else:
        fig.add_bar(y=g.occupation, x=g.us_median_wage, name="United States", orientation="h",
                    marker=dict(color=lib.GEO_COLORS["US"], line=dict(width=0)), hovertemplate="US: $%{x:,.0f}<extra></extra>")
        fig.add_bar(y=g.occupation, x=g.nd_median_wage, name="North Dakota", orientation="h",
                    marker=dict(color=lib.ACCENT, line=dict(width=0)), hovertemplate="ND: $%{x:,.0f}<extra></extra>")
        xt = "Median annual wage ($)"
    fig.update_layout(barmode="group", bargap=.25)
    lib.layout(fig, 640).update_xaxes(title=xt)
    lib.show(fig, "wf_occ", title=f"Major occupation groups, North Dakota and US ({view.lower()})")
    t = g.sort_values("nd_jobs", ascending=False).rename(columns={
        "occupation": "Occupation group", "nd_jobs": "ND jobs", "nd_share": "ND share (%)", "us_share": "US share (%)",
        "lq": "Concentration vs US (LQ)", "nd_median_wage": "ND median wage ($)", "us_median_wage": "US median wage ($)",
        "wage_ratio": "ND wage / US wage"})
    lib.data_table(t.drop(columns=["code", "year"]).round(2), "Occupations (table)", key="oews")
    st.caption("Wages are not adjusted for differences in living costs between North Dakota and the US. Concentration "
               "(LQ) above 1 means the group is a larger share of jobs here than nationally. Self-employed people are "
               "not counted. BLS publishes occupation data for metro and non-metro areas that do not match the "
               "planning regions, so this section is statewide.")


def region_table(d, last):
    """Awards by planning region of the institution, latest year and change since the first year shown."""
    first = int(d.year.min())
    g = d.groupby(["region", "year"]).awards.sum().unstack("year")
    if last not in g or first not in g:
        return
    t = pd.DataFrame({"Awards, latest year": g[last], f"Change since {first - 1}-{str(first)[2:]} (%)":
                      (g[last] / g[first] - 1) * 100, "Share of ND awards (%)": g[last] / g[last].sum() * 100})
    t = t.reindex(list(lib.REGIONS)).fillna({"Awards, latest year": 0, "Share of ND awards (%)": 0})
    inst = d[d.year == last].groupby("region").institution.nunique()
    t.insert(0, "Institutions", inst.reindex(t.index).fillna(0).astype(int))
    lib.data_table(t.round(1).reset_index().rename(columns={"region": "Planning region", "index": "Planning region"}),
                   "Awards by planning region of the institution (table)", key="ipeds_regions")


def graduates():
    c = lib.table("ipeds_completions.csv")
    last = int(c.year.max())
    st.subheader("Talent pipeline: degrees and certificates awarded")
    k = st.columns([1.2, 1.2, 2])
    who = k[0].radio("Institutions", ["North Dakota University System", "All North Dakota institutions"],
                     key="wf_inst")
    where = k[1].selectbox("Where", ["North Dakota"] + list(lib.REGIONS), key="wf_where")
    levels = k[2].multiselect("Award levels", LEVELS, default=LEVELS, key="wf_levels")
    d = c[c.level.isin(levels or LEVELS)]
    if who.startswith("North Dakota University"):
        d = d[d.ndus]
    region_table(d, last)
    if where != "North Dakota":
        d = d[d.region == where]
        if d.empty or last not in set(d.year):
            st.info(f"No {'NDUS ' if who.startswith('North Dakota University') else ''}institution in {where} awarded "
                    "degrees or certificates at these levels.")
            return levels or LEVELS
    tot = d.groupby("year").awards.sum()
    first = int(tot.index.min())
    m = st.columns(3)
    m[0].metric(f"Awards, {last - 1}-{str(last)[2:]}", f"{tot.loc[last]:,.0f}",
                f"{(tot.loc[last] / tot.loc[first] - 1) * 100:+.1f}% since {first - 1}-{str(first)[2:]}",
                delta_color="off", delta_arrow="off")
    nd_all = c[(c.year == last) & c.level.isin(levels or LEVELS)].awards.sum()
    m[1].metric("Share of all ND awards", f"{tot.loc[last] / nd_all * 100:.0f}%")
    health = d[(d.year == last) & (d.cip2 == 51)].awards.sum()
    m[2].metric("Health professions awards", f"{health:,.0f}", f"{health / tot.loc[last] * 100:.0f}% of awards",
                delta_color="off", delta_arrow="off")
    cols = st.columns([3, 2])
    with cols[0]:
        f = d[d.year == last].groupby("field").awards.sum().sort_values().tail(15)
        fig = go.Figure(go.Bar(y=f.index, x=f.values, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                               hovertemplate="%{y}: %{x:,.0f}<extra></extra>"))
        lib.show(lib.layout(fig, 480, legend=False), "wf_fields", title=f"Top 15 fields, {last - 1}-{str(last)[2:]}")
    with cols[1]:
        lv = d.groupby(["year", "level"]).awards.sum().reset_index()
        fig = go.Figure()
        for i, (name, g) in enumerate(lv.groupby("level", sort=False)):
            fig.add_scatter(x=g.year, y=g.awards, name=name, mode="lines+markers",
                            line=dict(color=lib.PALETTE[i % len(lib.PALETTE)], width=2, dash=lib.DASHES[i % len(lib.DASHES)]),
                            hovertemplate="%{y:,.0f}")
        lib.layout(fig, 480, "Awards").update_xaxes(dtick=1, title="Academic year ending")
        lib.show(fig, "wf_levels_chart", title="Awards by level")
    t = d[d.year == last].pivot_table(index="field", columns="level", values="awards", aggfunc="sum", fill_value=0)
    t = t[[x for x in LEVELS if x in t]]
    t["Total"] = t.sum(axis=1)
    lib.data_table(t.sort_values("Total", ascending=False).reset_index().rename(columns={"field": "Field"}),
                   "Awards by field and level (table)", key="ipeds_fields")
    inst = d[d.year == last].groupby("institution").awards.sum().sort_values(ascending=False)
    lib.data_table(inst.reset_index().rename(columns={"institution": "Institution", "awards": "Awards"}),
                   "Awards by institution (table)", key="ipeds_inst")
    st.caption("Counts are awards for first majors, not people: one graduate can earn two awards. Not every graduate "
               "stays in North Dakota. Fields follow the federal Classification of Instructional Programs (2-digit families). "
               "Regions follow the county of the institution's main campus (IPEDS directory); online students may live "
               "anywhere.")
    return levels or LEVELS


def pipeline_table(pr, lk, o):
    """Awards allocated to SOC major groups (equal shares across a program's linked groups), next to jobs and wages,
    per 1,000 jobs in North Dakota and the US."""
    m = pr.merge(lk[["cip", "soc_major", "share"]], on="cip")
    a = m.assign(nd=m.nd_awards * m.share, ndus=m.ndus_awards * m.share, us=m.us_awards * m.share)         .groupby("soc_major")[["nd", "ndus", "us"]].sum()
    g = o[o.occupation != "All occupations"].copy()
    g["soc_major"] = g.code.astype(str).str.zfill(2)
    g = g.set_index("soc_major").join(a).fillna({"nd": 0, "ndus": 0, "us": 0})
    g["nd_per_1k"] = g.nd / g.nd_jobs * 1000
    g["us_per_1k"] = g.us / g.us_jobs * 1000
    g["ratio"] = g.nd_per_1k / g.us_per_1k
    return g.reset_index()


def pipeline(levels):
    if not ((OUT / "ipeds_programs.csv").exists() and (OUT / "cip_soc_links.csv").exists()):
        return
    pr = lib.table("ipeds_programs.csv", dtype={"cip": str})
    lk = lib.table("cip_soc_links.csv", dtype={"cip": str, "soc_major": str})
    o = lib.table("workforce_oews.csv", dtype={"code": str})
    pr = pr[pr.level.isin(levels)]
    yr = int(pr.year.max())
    st.subheader("From fields of study to occupations")
    st.caption(f"Awards in {yr - 1}-{str(yr)[2:]} linked to the occupation groups they prepare for (NCES-BLS "
               "crosswalk), per 1,000 jobs in the group. Compared with the same ratio for the US: above 1, North "
               "Dakota institutions award relatively more for that occupation than the nation does.")
    g = pipeline_table(pr, lk, o)
    show = g[g.us_per_1k >= 5].sort_values("ratio")
    fig = go.Figure(go.Bar(y=show.occupation, x=show.ratio, orientation="h",
                           marker=dict(color=[lib.ACCENT if r >= 1 else lib.SECOND for r in show.ratio], line=dict(width=0)),
                           customdata=show[["nd_per_1k", "us_per_1k"]].values,
                           hovertemplate="%{y}: %{x:.2f} (ND %{customdata[0]:.0f}, US %{customdata[1]:.0f} per 1,000 jobs)"
                                         "<extra></extra>"))
    fig.add_vline(x=1, line_color=lib.UND_GRAY, line_width=1, line_dash="dash")
    lib.layout(fig, 520, legend=False).update_xaxes(title="ND awards per 1,000 jobs ÷ US awards per 1,000 jobs")
    lib.show(fig, "wf_pipe", title="Graduates relative to jobs, North Dakota compared with the US")
    st.caption("Green: at or above the US ratio; orange: below. Groups where the US awards fewer than 5 per 1,000 jobs "
               "(mostly learned on the job, such as food service) are left off the chart but are in the table. Farming looks "
               "high partly because self-employed farmers are not counted as jobs; health care support looks low partly "
               "because short non-credit training (for example nursing assistant courses) is not in IPEDS.")
    t = g.sort_values("nd", ascending=False)[["occupation", "nd_jobs", "nd_median_wage", "nd", "ndus", "nd_per_1k",
                                               "us_per_1k", "ratio"]].rename(columns={
        "occupation": "Occupation group", "nd_jobs": "ND jobs", "nd_median_wage": "ND median wage ($)",
        "nd": "ND awards linked", "ndus": "of which NDUS", "nd_per_1k": "ND awards per 1,000 jobs",
        "us_per_1k": "US awards per 1,000 jobs", "ratio": "ND / US"})
    lib.data_table(t.round(2), "Fields to occupations (table)", key="pipeline")
    pick = st.selectbox("Programs behind one occupation group", g.sort_values("nd", ascending=False).occupation,
                        key="wf_pipe_group")
    code = g.loc[g.occupation == pick, "soc_major"].iloc[0]
    m = pr.merge(lk[lk.soc_major == code][["cip", "share"]], on="cip")
    m = m.groupby(["cip", "title"]).agg(nd=("nd_awards", "sum"), ndus=("ndus_awards", "sum"), share=("share", "first"))
    m = m[m.nd > 0].sort_values("nd", ascending=False).reset_index().head(20)
    lib.data_table(m.rename(columns={"cip": "CIP code", "title": "Program", "nd": "ND awards (all levels chosen)",
                                     "ndus": "of which NDUS", "share": "Share counted for this group"}).round(2),
                   f"Top programs linked to {pick.lower()} (table)", key="pipeline_programs")
    linked = pr.cip.isin(lk.cip)
    st.caption(f"{pr[linked].nd_awards.sum() / max(pr.nd_awards.sum(), 1) * 100:.0f}% of North Dakota awards link to an "
               "occupation group; general studies and similar programs do not. A program linked to several groups is "
               "split equally among them. Postsecondary teaching jobs are left out of the links. The link says what a "
               "program prepares for, not where graduates end up working.")


def page():
    lib.header("Workforce and talent", "How tight North Dakota's labor market is, which occupations employ people "
               "here and what they pay, and how many graduates the state's colleges and universities prepare.",
               "official", "estimate", note="BLS and NCES. Openings per unemployed person and concentration: IPBA "
               "calculations.")
    if not ready():
        return
    labor_market()
    st.divider()
    occupations()
    st.divider()
    levels = graduates()
    st.divider()
    pipeline(levels)
    lib.method_panel([
        "Job openings, hires and quits: BLS Job Openings and Labor Turnover Survey (JOLTS) state estimates, seasonally "
        "adjusted. State figures combine the survey with QCEW data in a model, so single months are uncertain; the "
        "page uses 3-month averages. Openings rate = openings / (jobs + openings).",
        "Openings per unemployed person: average openings over the latest 12 months of state data divided by average "
        "unemployed (BLS LAUS, not seasonally adjusted) in the same months, a standard gauge of labor market "
        "tightness (Elsby et al., 2015).",
        "Occupations: BLS Occupational Employment and Wage Statistics, May estimates, 22 major groups of the Standard "
        "Occupational Classification. Concentration (LQ) = ND share of jobs / US share. Wages are medians in current "
        "dollars.",
        "Graduates: NCES IPEDS Completions, first majors, academic years (July to June). NDUS institutions are those "
        "IPEDS lists in the North Dakota University System.",
        "Fields to occupations: NCES-BLS CIP 2020 to SOC 2018 crosswalk. Each award in a linked program is split "
        "equally among the major occupation groups the program links to (postsecondary teachers excluded). Ratio = "
        "(ND awards / ND jobs) / (US awards / US jobs), with US awards from institutions in the 50 states and DC."],
        ["elsby2015"])
    lib.source_line("jolts", "laus", "oews", "ipeds", "cipsoc")


if __name__ == "__main__":
    page()
