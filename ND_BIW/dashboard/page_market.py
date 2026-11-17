"""Market finder: a profile of one county or planning region - people, income, and businesses by industry."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import COUNTIES, REGIONS, SHORT

MAP_METRICS = {
    "population": ("Population", ",.0f"),
    "median_household_income": ("Median household income ($)", "$,.0f"),
    "per_capita_income": ("Per capita income ($)", "$,.0f"),
    "laus_rate": ("Unemployment rate, latest 12 months (%, BLS)", ".1f"),
    "unemployment_rate": ("Unemployment rate, ACS 2020-2024 survey (%)", ".1f"),
    "employer_per_1k": ("Employer establishments per 1,000 residents", ".1f"),
    "nonemployer_per_1k": ("Self-employed / nonemployer businesses per 1,000 residents", ".1f"),
    "business_share": ("Tax returns with business income (%, IRS)", ".1f"),
    "farm_share": ("Tax returns with farm income (%, IRS)", ".1f"),
}


@st.cache_data(show_spinner=False)
def geojson():
    return json.loads((lib.ASSETS / "nd_counties.geojson").read_text())


def laus():
    """Latest 12-month average unemployment by place (BLS LAUS), the month range covered, and monthly data."""
    f = lib.OUT / "laus_monthly.csv"
    if not f.exists():
        return None, None, None
    from laus import latest_12
    t = lib.table("laus_monthly.csv", parse_dates=["month"])
    g = latest_12(t).set_index("place")
    last = t.month.max()
    w = t[t.month > last - pd.DateOffset(months=12)].month
    return g, (w.min(), last, w.nunique()), t


def counties_frame(acs, biz):
    c = acs[acs.level == "county"].copy()
    g, _, _ = laus()
    if g is not None:
        c["laus_rate"] = c.county.map(g.rate)
    if (lib.OUT / "irs_soi.csv").exists():
        i = lib.table("irs_soi.csv")
        i = i[(i.level == "county") & (i.year == i.year.max())].set_index("place")
        c["business_share"] = c.county.map(i.business_share)
        c["farm_share"] = c.county.map(i.farm_share)
    tot = biz[biz.sector == "total"].set_index("county")
    c["employer_per_1k"] = c.county.map(tot.employer_estabs) / c.population * 1000
    c["nonemployer_per_1k"] = c.county.map(tot.nonemployers) / c.population * 1000
    c["fips"] = c.code.astype(str)
    return c


def plus_minus(v, moe, fmt):
    """Margin of error, and the estimate's reliability, as the metric's note; none when the margin is zero (population is
    fixed to official estimates)."""
    if not (pd.notna(moe) and moe > 0):
        return None
    _, label = lib.reliability(v, moe)
    return f"margin of error {fmt.format(moe)}" + (f" · {label}" if label and label != "reliable" else "")


def profile(row, level, county_rows):
    k = st.columns(4)
    k[0].metric("Population", lib.num(row.population), plus_minus(row.population, row.population_moe, "{:,.0f}"),
                delta_color="off", delta_arrow="off")
    if level in ("County", "Legislative district"):
        k[1].metric("Median household income", lib.money(row.median_household_income),
                    plus_minus(row.median_household_income, row.median_household_income_moe, "${:,.0f}"), delta_color="off", delta_arrow="off")
        k[3].metric("Median age", lib.num(row.median_age, 1), plus_minus(row.median_age, row.median_age_moe, "{:.1f}"),
                    delta_color="off", delta_arrow="off")
    else:
        k[1].metric("Per capita income", lib.money(row.per_capita_income),
                    plus_minus(row.per_capita_income, row.per_capita_income_moe, "${:,.0f}"), delta_color="off", delta_arrow="off")
        k[3].metric("Median household income, by county", f"${row.median_household_income_min / 1000:,.0f}k to "
                    f"${row.median_household_income_max / 1000:,.0f}k")
    g, span, t = laus()
    name = row.county if level == "County" else row.code
    if g is not None and name in g.index:
        nd = g.loc["North Dakota"].rate
        k[2].metric("Unemployment rate (BLS)", lib.pct(g.loc[name].rate, signed=False),
                    f"North Dakota {nd:.1f}% · {span[0]:%b %Y} to {span[1]:%b %Y}", delta_color="off", delta_arrow="off",
                    help="Official BLS Local Area Unemployment Statistics, average of the latest 12 months (removes the "
                         "seasonal swing). The ACS survey rate is on the county map, for comparison.")
    else:
        k[2].metric("Unemployment rate (ACS)", lib.pct(row.unemployment_rate, signed=False),
                    plus_minus(row.unemployment_rate, row.unemployment_rate_moe, "{:.1f} pts"), delta_color="off", delta_arrow="off")
    unemp_note = ("BLS does not publish unemployment for legislative districts, so the survey (ACS) rate is shown "
                  "with its margin of error; in many districts it is low reliability." if level == "Legislative district"
                  else "The unemployment rate is the official BLS county estimate instead (Local Area Unemployment "
                  "Statistics, produced with Job Service North Dakota), which is far more precise than the survey in "
                  "small counties." + (f" Months with no data are skipped ({12 - span[2]} in this window; BLS did not "
                  "collect data for October 2025)." if g is not None and span[2] < 12 else ""))
    st.caption("American Community Survey 5-year estimates (2020-2024 average). The margin of error is at the 90% level: "
               "the true value is likely within that range. Estimates are flagged 'use with caution' when the margin "
               "is large relative to the estimate (coefficient of variation 15-30%) and 'low reliability' above 30%, "
               "following Census guidance. " + unemp_note)
    if t is not None and name in set(t.place):
        m = t[t.place.isin([name, "North Dakota"])].pivot_table(index="month", columns="place", values="rate")
        fig = go.Figure()
        for col in [c for c in (name, "North Dakota") if c in m]:
            here = col == name
            fig.add_scatter(x=m.index, y=m[col], name=col if col == "North Dakota" else (f"{col} County" if level == "County" else col),
                            mode="lines+markers", marker=dict(size=4), hovertemplate="%{x|%b %Y}: %{y:.1f}%",
                            line=dict(color=lib.ACCENT if here else lib.UND_GRAY, width=2.6 if here else 1.8,
                                      dash="solid" if here else "dash"))
        lib.show(lib.layout(fig, 260, "% of labor force"), "mf_laus", title="Unemployment rate by month (not seasonally adjusted, BLS)")
        lib.data_table(m.round(1).reset_index().assign(month=lambda x: x.month.dt.strftime("%Y-%m")),
                       "Monthly unemployment (table)", key="mf_laus_t")


def businesses(biz, place_counties, pop, state_pop):
    st.subheader("Businesses by industry")
    b = biz[biz.county.isin(place_counties) & (biz.sector != "total")]
    agg = b.groupby("sector").agg(employer_estabs=("employer_estabs", "sum"), employees=("employees", "sum"),
                                  payroll_k=("payroll_k", "sum"), nonemployers=("nonemployers", "sum"),
                                  receipts_k=("nonemployer_receipts_k", "sum"),
                                  high_noise=("employee_noise", lambda s: (s == "J").any()),
                                  ne_missing=("nonemployers", lambda s: s.isna().any() or len(s) < len(place_counties)))
    st_all = biz[(biz.sector != "total")].groupby("sector")[["employer_estabs", "nonemployers"]].sum()
    agg["Employer establishments per 1,000 residents"] = agg.employer_estabs / pop * 1000
    agg["State per 1,000 residents"] = agg.index.map(st_all.employer_estabs) / state_pop * 1000
    agg["Nonemployers per 1,000 residents"] = agg.nonemployers / pop * 1000
    agg["State nonemployers per 1,000"] = agg.index.map(st_all.nonemployers) / state_pop * 1000
    agg["name"] = agg.index.map(SHORT)

    cols = st.columns(2)
    for col, mine, state, title, key in (
            (cols[0], "Employer establishments per 1,000 residents", "State per 1,000 residents",
             "Employer establishments per 1,000 residents", "mf_emp"),
            (cols[1], "Nonemployers per 1,000 residents", "State nonemployers per 1,000",
             "Nonemployer (self-employed) businesses per 1,000 residents", "mf_nonemp")):
        with col:
            v = agg.sort_values(mine)
            fig = go.Figure()
            fig.add_bar(y=v.name, x=v[state], name="North Dakota", orientation="h",
                        marker=dict(color=lib.GEO_COLORS["US"], cornerradius=2), hovertemplate="%{x:.2f}")
            fig.add_bar(y=v.name, x=v[mine], name="This place", orientation="h",
                        marker=dict(color=lib.ACCENT, cornerradius=2), hovertemplate="%{x:.2f}")
            fig.update_layout(barmode="group", bargap=.25, bargroupgap=.08)
            lib.show(lib.layout(fig, 560).update_layout(hovermode="y unified"), key, title=f"{title}")
    st.caption("Fewer businesses per resident than the state average can point to an underserved market, or to "
               "demand being met in a nearby trade center; compare with neighboring places before drawing conclusions.")
    t = agg.sort_values("employer_estabs", ascending=False).reset_index(drop=True)
    t = t[["name", "employer_estabs", "employees", "payroll_k", "nonemployers", "receipts_k",
           "Employer establishments per 1,000 residents", "State per 1,000 residents"]].rename(columns={
        "name": "Industry", "employer_estabs": "Employer establishments", "employees": "Employees (March)",
        "payroll_k": "Annual payroll ($1,000)", "nonemployers": "Nonemployer businesses",
        "receipts_k": "Nonemployer receipts ($1,000)"})
    lib.data_table(t.round(2), "Businesses by industry (table)", key="market_businesses")
    noisy = agg[agg.high_noise].name.tolist()
    st.caption("Employer data: County Business Patterns 2023 (establishments with paid employees, mid-March). "
               "Nonemployer data: Nonemployer Statistics 2024 (businesses with no paid employees, mostly self-employed). "
               "The Census Bureau adds noise to protect confidentiality"
               + (f"; employee counts carry high noise (5% or more) in: {', '.join(noisy)}." if noisy else "."))


def business_size(place_counties):
    z = lib.table("cbp_sizes.csv", dtype={"sector": str})
    z = z[z.sector == "total"]
    here = z[z.county.isin(place_counties)].groupby(["order", "size"]).estabs.sum().reset_index()
    state = z.groupby(["order", "size"]).estabs.sum().reset_index()
    here["share"] = here.estabs / here.estabs.sum() * 100
    state["share"] = state.estabs / state.estabs.sum() * 100
    fig = go.Figure()
    fig.add_bar(x=state["size"], y=state.share, name="North Dakota", marker=dict(color=lib.GEO_COLORS["US"], cornerradius=2),
                hovertemplate="%{y:.1f}%")
    fig.add_bar(x=here["size"], y=here.share, name="This place", marker=dict(color=lib.ACCENT, cornerradius=2),
                hovertemplate="%{y:.1f}%")
    fig.update_layout(barmode="group", bargap=.25, bargroupgap=.08)
    lib.layout(fig, 320, "% of establishments").update_xaxes(title="Employees (mid-March)", type="category")
    lib.show(fig, "mf_size", title="Employer establishments by number of employees (% of establishments)")
    small = here[here.order <= 2].estabs.sum() / here.estabs.sum() * 100
    st.caption(f"{small:.0f}% of employer establishments here have fewer than 20 employees. County Business Patterns "
               "2023; businesses without employees are not included.")
    t = here[["size", "estabs", "share"]].rename(columns={"size": "Employees", "estabs": "Establishments",
                                                          "share": "% of establishments"})
    t["North Dakota (%)"] = state.share.values
    lib.data_table(t.round(1), "Business size (table)", key="business_size")


def county_map(cf, selected):
    st.subheader("Compare counties")
    lab = st.selectbox("Map shows", [v[0] for v in MAP_METRICS.values()], key="mf_metric")
    metric = {v[0]: k for k, v in MAP_METRICS.items()}[lab]
    label, fmt = MAP_METRICS[metric]
    if metric + "_moe" in cf:
        note = [f" ± {m:{fmt.lstrip('$')}} ({lib.reliability(e, m)[1]})" if pd.notna(m) else ""
                for e, m in zip(cf[metric], cf[metric + "_moe"])]
    else:
        note = [""] * len(cf)
    fig = go.Figure(go.Choropleth(
        geojson=geojson(), locations=cf.fips, z=cf[metric], featureidkey="id", colorscale=lib.SEQ,
        marker_line_color=lib.PANEL, marker_line_width=0.6, text=cf.county, customdata=note,
        hovertemplate=f"%{{text}}: %{{z:{fmt}}}%{{customdata}}<extra></extra>", colorbar=dict(title=None, thickness=12)))
    sel = cf[cf.county.isin(selected)]
    fig.add_trace(go.Choropleth(geojson=geojson(), locations=sel.fips, z=[1] * len(sel), featureidkey="id",
                                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                marker_line_color="#FFFFFF", marker_line_width=2.5, hoverinfo="skip"))
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor=lib.PANEL, geo=dict(bgcolor=lib.PANEL),
                      font=dict(color=lib.INK), showlegend=False)
    fig.update_traces(colorbar=dict(tickfont=dict(color=lib.MUTED)), selector=dict(showscale=True))
    lib.show(fig, "mf_map", title=f"{label} by county")
    st.caption("The selected place is outlined in white.")
    t = cf[["county", "region", metric]].sort_values(metric, ascending=False).rename(
        columns={"county": "County", "region": "Planning region", metric: label})
    if metric + "_moe" in cf:
        t["Margin of error (±)"] = cf.loc[t.index, metric + "_moe"]
        rel = [lib.reliability(e, m) for e, m in zip(cf.loc[t.index, metric], cf.loc[t.index, metric + "_moe"])]
        t["Coefficient of variation (%)"] = [round(r[0], 1) for r in rel]
        t["Reliability"] = [r[1] for r in rel]
    lib.data_table(t, "Map data (all counties)", key=f"map_{metric}")


PEER_OUTCOMES = {"median_income": ("Median household income", "${:,.0f}"),
                 "unemployment_rate": ("Unemployment rate (ACS, %)", "{:.1f}%"),
                 "estabs_per_1k": ("Employer establishments per 1,000 residents", "{:.1f}"),
                 "nonemployers_per_1k": ("Self-employed businesses per 1,000 residents", "{:.1f}"),
                 "pay_per_job": ("Average pay per private job", "${:,.0f}"),
                 "home_value": ("Median home value", "${:,.0f}")}
MIX_NAMES = {"mix_11": "Agriculture support", "mix_21": "Mining, oil and gas", "mix_23": "Construction",
             "mix_31": "Manufacturing", "mix_42": "Wholesale", "mix_44": "Retail", "mix_48": "Transportation",
             "mix_62": "Health care", "mix_72": "Accommodation and food"}


def peer_counties(county):
    """Five US counties outside North Dakota most like this one in size, density, age and industry mix."""
    if not ((lib.OUT / "county_peers.csv").exists() and (lib.OUT / "county_peer_profiles.csv").exists()):
        return
    pe = lib.table("county_peers.csv", dtype={"fips": str, "peer_fips": str})
    pr = lib.table("county_peer_profiles.csv", dtype={"fips": str}).set_index("fips")
    mine = pe[pe.county == county].sort_values("rank")
    if mine.empty:
        return
    me = pr.loc[mine.fips.iloc[0]]
    peers = pr.loc[mine.peer_fips]
    med = peers[list(PEER_OUTCOMES)].median()
    st.markdown("**Similar counties elsewhere in the US**")
    st.caption("The five counties outside North Dakota most like this one in population, density, median age and mix "
               "of private industries. Comparing results with them asks: how does this county do compared with places "
               "built like it?")
    k = st.columns(4)
    for col, m in zip(k, ["median_income", "unemployment_rate", "estabs_per_1k", "pay_per_job"]):
        lab, fmt = PEER_OUTCOMES[m]
        col.metric(lab, fmt.format(me[m]) if pd.notna(me[m]) else "n/a",
                   f"peer median {fmt.format(med[m])}" if pd.notna(med[m]) else None, delta_color="off", delta_arrow="off")
    t = pd.concat([pd.DataFrame([{"County": f"{county} County, ND (this county)", "Match": "", **me.to_dict()}]),
                   pd.DataFrame([{"County": p, "Match": q, **pr.loc[f].to_dict()} for p, q, f in
                                 zip(mine.peer, mine.match, mine.peer_fips)]),
                   pd.DataFrame([{"County": "Median of the five peers", "Match": "", **med.to_dict()}]),
                   pd.DataFrame([{"County": "Median of all US counties", "Match": "", **pr.loc["US"].to_dict()}])],
                  ignore_index=True)
    show = t[["County", "Match", "population", *PEER_OUTCOMES]].rename(
        columns={"population": "Population", **{k_: v[0] for k_, v in PEER_OUTCOMES.items()}})
    lib.data_table(show.round(1), "This county, its peers and the US (table)", key="peer_table")
    mix = pd.DataFrame({"This county": me[list(MIX_NAMES)].astype(float), "Peers (average)": peers[list(MIX_NAMES)].mean()})
    mix.index = [MIX_NAMES[c] for c in mix.index]
    fig = go.Figure()
    fig.add_bar(y=mix.index, x=mix["Peers (average)"], name="Peers (average)", orientation="h",
                marker=dict(color=lib.GEO_COLORS["US"], line=dict(width=0)), hovertemplate="%{x:.1f}%")
    fig.add_bar(y=mix.index, x=mix["This county"], name="This county", orientation="h",
                marker=dict(color=lib.ACCENT, line=dict(width=0)), hovertemplate="%{x:.1f}%")
    fig.update_layout(barmode="group")
    lib.layout(fig, 380).update_xaxes(title="% of private jobs", ticksuffix="%")
    lib.show(fig, "peer_mix", title="Industry mix used for matching: this county and its peers")
    loose = (mine.match == "loose").sum()
    st.caption("Match quality compares each peer's distance with how far US counties typically are from their nearest "
               "counties: close, fair or loose." + (f" {loose} of these matches are loose: few US counties resemble "
               "this one closely, so read the comparison with care." if loose else "") + " Sources: ACS 2020-2024, "
               "County Business Patterns 2023, Nonemployer Statistics 2024, Census Gazetteer. County Business Patterns "
               "leaves out farm workers, government and the self-employed.")


def tax_returns(level, name):
    """Households earning business or farm income (IRS county data): a gauge of self-employment and farming."""
    if not (lib.OUT / "irs_soi.csv").exists():
        return
    i = lib.table("irs_soi.csv")
    y = int(i.year.max())
    lvl = "county" if level == "County" else "region"
    here = i[(i.level == lvl) & (i.place == name)].set_index("year")
    nd = i[(i.level == "state") & (i.place == "ND")].set_index("year")
    if y not in here.index:
        return
    h, n = here.loc[y], nd.loc[y]
    st.markdown(f"**Self-employment and farming: individual tax returns, tax year {y}**")
    k = st.columns(4)
    k[0].metric("Returns with business income", lib.pct(h.business_share, signed=False),
                f"North Dakota {n.business_share:.1f}%", delta_color="off", delta_arrow="off",
                help="Schedule C: sole proprietors, freelancers and independent contractors (profit or loss).")
    k[1].metric("Average business income per such return", f"${h.business_income_per_return:,.0f}",
                f"North Dakota ${n.business_income_per_return:,.0f}", delta_color="off", delta_arrow="off")
    k[2].metric("Returns with farm income", lib.pct(h.farm_share, signed=False), f"North Dakota {n.farm_share:.1f}%",
                delta_color="off", delta_arrow="off", help="Schedule F: farm profit or loss.")
    k[3].metric("Returns filed", f"{h.returns:,.0f}")
    t = here[["returns", "business_returns", "business_share", "business_income_per_return", "farm_returns",
              "farm_share"]].reset_index().rename(columns={
        "year": "Tax year", "returns": "Returns", "business_returns": "With business income",
        "business_share": "Business share (%)", "business_income_per_return": "Average business income ($)",
        "farm_returns": "Farm returns", "farm_share": "Farm share (%)"})
    lib.data_table(t.round(1), "Tax returns by year (table)", key="irs_here")
    st.caption("IRS Statistics of Income. A return with business income can also report wages; partnerships and "
               "corporations are not included. The IRS rounds counts, so small counties are approximate.")


DISTRICT_MEASURES = {"median_household_income": ("Median household income ($)", "${:,.0f}"),
                     "per_capita_income": ("Per capita income ($)", "${:,.0f}"),
                     "median_home_value": ("Median home value ($)", "${:,.0f}"),
                     "median_age": ("Median age (years)", "{:.1f}"),
                     "unemployment_rate": ("Unemployment rate, ACS (%)", "{:.1f}%"),
                     "population": ("Population", "{:,.0f}")}


def district_compare(acs, code):
    """All 47 legislative districts on one ACS measure, with 90% margins of error and reliability."""
    d = acs[acs.level == "district"].copy()
    nd = acs[(acs.level == "state") & (acs.code == "ND")].iloc[0]
    st.subheader("Compare legislative districts")
    lab = st.selectbox("Measure", [v[0] for v in DISTRICT_MEASURES.values()], key="ld_measure")
    m = {v[0]: k for k, v in DISTRICT_MEASURES.items()}[lab]
    fmt = DISTRICT_MEASURES[m][1]
    d = d.dropna(subset=[m]).sort_values(m)
    moe = d[m + "_moe"] if m + "_moe" in d else None
    fig = go.Figure(go.Bar(
        x=d.code.str.replace("LD", "", regex=False).str.lstrip("0"), y=d[m],
        marker=dict(color=[lib.SECOND if c == code else lib.ACCENT for c in d.code], line=dict(width=0)),
        error_y=dict(type="data", array=moe, color=lib.MUTED, thickness=1, width=2) if moe is not None else None,
        customdata=d.name, hovertemplate="%{customdata}: %{y:,.1f}<extra></extra>"))
    if pd.notna(nd[m]) and m != "population":
        fig.add_hline(y=nd[m], line_dash="dash", line_color=lib.UND_GRAY,
                      annotation_text=f"North Dakota {fmt.format(nd[m])}", annotation_position="top left")
    lib.layout(fig, 380, lab, legend=False).update_xaxes(title="Legislative district (sorted)", type="category")
    lib.show(fig, "ld_chart", title=f"{lab} by legislative district (orange: selected district; bars show 90% margins)")
    t = d[["name", m] + ([m + "_moe"] if moe is not None else [])].copy()
    if moe is not None:
        rel = [lib.reliability(e, mo) for e, mo in zip(d[m], d[m + "_moe"])]
        t["Reliability"] = [r[1] for r in rel]
    lib.data_table(t.sort_values(m, ascending=False).rename(columns={"name": "District", m: lab,
                                                                     m + "_moe": "Margin of error (±)"}).round(1),
                   "All legislative districts (table)", key=f"ld_{m}")
    st.caption("Districts whose margins overlap may not differ in fact. Each district elects one senator and two "
               "representatives; district boundaries are those the Census Bureau used for the 2020-2024 ACS.")


def page():
    lib.header("Market finder", "A profile of any North Dakota county, planning region or legislative district: who lives there, what they "
               "earn, and how many businesses serve them in each industry.", "official", "estimate",
               note="Census Bureau. Planning-region totals and per-resident rates: IPBA calculations.")
    if not lib.ready():
        return
    acs = lib.table("acs_places.csv")
    biz = lib.table("county_business.csv", dtype={"sector": str})
    c = st.columns([1, 2])
    level = c[0].radio("Look at", ["County", "Planning region", "Legislative district"], horizontal=True, key="mf_level")
    if level == "Legislative district":
        dist = acs[acs.level == "district"].sort_values("code")
        code = c[1].selectbox("Legislative district", list(dist.code), key="mf_district",
                              format_func=lambda x: f"District {int(x[2:])}")
        row = dist[dist.code == code].iloc[0]
        st.markdown(f"### {row['name']}", unsafe_allow_html=True)
        profile(row, level, [])
        st.info("Business counts, SBA loans and tax-return data are published by county, not by legislative district, "
                "so this view shows people and income from the American Community Survey.", icon=":material/info:")
        district_compare(acs, code)
        lib.method_panel(["People and income: ACS 5-year estimates (2020-2024) for state legislative districts "
                          "(summary level 610), with 90% margins of error and Census reliability flags."], ["census2020"])
        lib.source_line("acs")
        return
    if level == "County":
        place = c[1].selectbox("County", sorted(COUNTIES.values()), key="mf_county",
                               index=sorted(COUNTIES.values()).index("Cass"))
        row = acs[(acs.level == "county") & (acs.county == place)].iloc[0]
        members = [place]
        st.markdown(f"### {place} County  \n<span style='opacity:.75'>{row.region}</span>", unsafe_allow_html=True)
    else:
        place = c[1].selectbox("Planning region", list(REGIONS), key="mf_region")
        row = acs[(acs.level == "region") & (acs.code == place)].iloc[0]
        members = REGIONS[place]
        st.markdown(f"### {place}  \n<span style='opacity:.75'>Counties: {', '.join(members)}</span>", unsafe_allow_html=True)
    profile(row, level, members)
    state_pop = acs[(acs.level == "state") & (acs.code == "ND")].population.iloc[0]
    st.divider()
    businesses(biz, members, row.population, state_pop)
    business_size(members)
    tax_returns(level, place)
    if level == "County":
        st.divider()
        peer_counties(place)
    patents_here(members, row.population, state_pop)
    st.divider()
    county_map(counties_frame(acs, biz), members)
    lib.method_panel([
        "People and income: ACS 5-year estimates (2020-2024) with 90% margins of error.",
        "Planning regions: county counts are summed; the margin of error is the square root of the summed squared "
        "county margins. Medians cannot be summed, so regions show per capita income (aggregate income / population).",
        "Businesses: County Business Patterns 2023 (employer establishments, mid-March employment, payroll) and "
        "Nonemployer Statistics 2024 (businesses without paid employees). Per 1,000 residents uses ACS population.",
        "Unemployment: BLS Local Area Unemployment Statistics, not seasonally adjusted; regions sum county unemployed "
        "and labor force. The 12-month average removes most of the seasonal swing.",
        "Peer counties: the five US counties outside North Dakota nearest to this one on standardized measures of size "
        "(log population, weight 2), density (log residents per square mile), median age, and the shares of private "
        "jobs in nine industries (1/3 each). Results (income, unemployment, business density, pay, home values) are "
        "not used for matching, so they can be compared fairly."],
        ["census2020"])
    lib.source_line("acs", "laus", "cbp", "nes", "irs_soi", "gazetteer", "patents")


if __name__ == "__main__":
    page()


def patents_here(place_counties, pop, state_pop):
    """Patents by inventors living in the place (first North Dakota inventor's county), last 5 complete years."""
    f, s = lib.OUT / "patents_nd_region.csv", lib.OUT / "patents_state.csv"
    if not f.exists() or not s.exists():
        return
    r = lib.table("patents_nd_region.csv")
    if "county" not in r:
        return
    st_ = lib.table("patents_state.csv")
    years = sorted(st_[(st_.geo == "ND") & st_.complete_year.astype(bool)].year.unique())[-5:]
    here = r[r.county.isin(place_counties) & r.year.isin(years)].patents.sum()
    nd = r[r.year.isin(years)].patents.sum()
    st.markdown(f"**Innovation: patents by inventors living here, {years[0]}-{years[-1]}**")
    c = st.columns(3)
    c[0].metric("Patents granted", f"{here:,.0f}", f"{here / len(years):,.1f} a year", delta_color="off", delta_arrow="off")
    c[1].metric("Per 100,000 residents a year", f"{here / len(years) / pop * 1e5:,.1f}",
                f"North Dakota: {nd / len(years) / state_pop * 1e5:,.1f}", delta_color="off", delta_arrow="off")
    c[2].metric("Share of North Dakota patents", lib.pct(here / nd * 100 if nd else None, signed=False))
    st.caption("Utility patents with at least one North Dakota inventor, placed by the first North Dakota inventor's "
               "county (PatentsView). Small numbers vary a lot from year to year.")
