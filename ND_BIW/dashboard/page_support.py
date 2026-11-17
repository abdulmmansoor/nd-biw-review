"""Business support insights: benchmarks for organizations that advise, finance and develop North Dakota businesses
(small business advisers, economic developers, innovation centers). Public, aggregated data only; no program or business
is rated."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

GEOS = ["ND", "MN", "MT", "SD", "WY", "US"]
WIDE_MOE = 15          # owner-age shares with a 90% margin wider than this many points are flagged
MIN_FIRMS = 10         # Phase I to Phase II rates need at least this many companies


def color(g):
    return lib.ACCENT if g == "ND" else (lib.UND_GRAY if g != "US" else lib.SECOND)


# ------------------------------------------------------------------ survival
def survival():
    p = lib.table("survival_sector.csv", dtype={"sector": str})
    t = lib.table("survival_trend.csv")
    st.subheader("How many new businesses are still open 1, 3 and 5 years later")
    st.markdown("A North Dakota benchmark for advisers who track their clients' survival: the share of new firms in "
                "the state still operating after 1, 3 and 5 years, by industry, next to the peer states and the US.")
    a = p[p.sector == "00"].set_index(["geo", "horizon"]).survival
    k = st.columns(3)
    for i, h in enumerate((1, 3, 5)):
        r = p[(p.sector == "00") & (p.horizon == h)].iloc[0]
        k[i].metric(f"Still open after {h} year{'s' if h > 1 else ''}, ND", lib.pct(a.get(("ND", h)), 0, signed=False),
                    f"US {a.get(('US', h)):.0f}% (firms born {int(r.cohort_from)}-{int(r.cohort_to)})",
                    delta_color="off", delta_arrow="off")
    c = st.columns([1, 2])
    h = c[0].radio("Years after opening", [1, 3, 5], index=2, horizontal=True, key="sup_surv_h")
    geos = c[1].multiselect("Compare with", [g for g in GEOS if g != "ND"], default=["US"], key="sup_surv_geo",
                            format_func=PEER_NAMES.get)
    d = p[(p.horizon == h) & (p.sector != "00")]
    nd = d[d.geo == "ND"].dropna(subset=["survival"]).sort_values("survival")
    fig = go.Figure()
    fig.add_bar(y=nd.sector_name, x=nd.survival, orientation="h", name="North Dakota",
                marker=dict(color=lib.ACCENT, line=dict(width=0)), hovertemplate="%{y}: %{x:.0f}%<extra>North Dakota</extra>")
    for i, g in enumerate(geos):
        e = d[d.geo == g].set_index("sector_name").survival.reindex(nd.sector_name)
        fig.add_trace(go.Scatter(y=e.index, x=e.values, mode="markers", name=PEER_NAMES[g],
                                 marker=dict(color=[lib.SECOND, lib.UND_GRAY, "#C9B37E", "#8E8CD8", "#7FCFA0"][i % 5],
                                             size=11, symbol=["diamond", "circle", "square", "triangle-up", "x"][i % 5]),
                                 hovertemplate="%{y}: %{x:.0f}%<extra>" + PEER_NAMES[g] + "</extra>"))
    lib.layout(fig, 560).update_xaxes(title=f"% of new firms still open after {h} years", range=[0, 100])
    fig.update_layout(hovermode="closest")
    lib.show(fig, "sup_surv", title=f"New firms still open after {h} year{'s' if h > 1 else ''}, by industry")
    hidden = sorted(set(d[(d.geo == "ND")].sector_name) - set(nd.sector_name))
    st.caption(f"Firms born in {int(d.cohort_from.iloc[0])}-{int(d.cohort_to.iloc[0])}, pooled (sum of survivors over "
               "sum of births) because single years of small industries are noisy. "
               + (f"Not shown for ND (too few new firms, or withheld by Census): {', '.join(hidden)}." if hidden else ""))
    w = p[p.horizon == h].pivot_table(index="sector_name", columns="geo", values="survival").reindex(columns=GEOS)
    lib.data_table(w.round(1).rename(columns=PEER_NAMES).reset_index(), "Survival by industry and place, % (table)",
                   key="sup_surv_t")
    tt = t[(t.horizon == h) & t.geo.isin(["ND", "US"])]
    fig = go.Figure()
    for i, g in enumerate(["ND", "US"]):
        e = tt[tt.geo == g]
        fig.add_trace(go.Scatter(x=e.cohort, y=e.survival, name=PEER_NAMES[g], mode="lines+markers",
                                 line=dict(color=color(g), dash=lib.DASHES[i]),
                                 hovertemplate=PEER_NAMES[g] + ", born %{x}: %{y:.0f}%<extra></extra>"))
    lib.layout(fig, 300, ytitle="% still open")
    lib.show(fig, "sup_surv_trend", title=f"All industries: firms still open after {h} years, by year of birth")
    lib.data_table(tt.pivot_table(index="cohort", columns="geo", values="survival").round(1).reset_index(),
                   "Survival by year of birth (table)", key="sup_surv_trend_t")


# ------------------------------------------------------------------ owners
def owners():
    n = lib.table("owners_55plus.csv", dtype={"sector": str})
    a = lib.table("owners_age.csv", dtype={"sector": str})
    y0, y1 = int(n.year.min()), int(n.year.max())
    st.subheader("Business owners near retirement age: the coming succession wave")
    st.markdown("How many owners of North Dakota's employer businesses are 55 or older, by industry, compared with the "
                "peer states and the US: a guide to where exit and succession planning will be needed.")
    al = n[(n.sector == "00")].set_index(["geo", "year"])
    k = st.columns(3)
    k[0].metric(f"ND owners aged 55 or older, {y1}", f"{al.loc[('ND', y1), 'share_55plus']:.0f}%",
                f"± {al.loc[('ND', y1), 'share_55plus_moe90']:.0f} points (90%)", delta_color="off", delta_arrow="off")
    k[1].metric(f"US, {y1}", f"{al.loc[('US', y1), 'share_55plus']:.0f}%")
    k[2].metric(f"ND, {y0}", f"{al.loc[('ND', y0), 'share_55plus']:.0f}%")
    d = n[(n.year == y1) & (n.geo == "ND") & (n.sector != "00") & (n.owners_55plus > 0)].sort_values("share_55plus")
    wide = d.share_55plus_moe90 > WIDE_MOE
    fig = go.Figure(go.Bar(y=d.sector_name, x=d.share_55plus, orientation="h",
                           marker=dict(color=[lib.UND_GRAY if w else lib.ACCENT for w in wide], line=dict(width=0)),
                           error_x=dict(type="data", array=d.share_55plus_moe90.clip(upper=60), color="#999", thickness=1),
                           customdata=d[["share_55plus_moe90", "owners_55plus"]].values,
                           hovertemplate="%{y}: %{x:.0f}% ± %{customdata[0]:.0f} (%{customdata[1]:,.0f} owners)<extra></extra>"))
    fig.add_vline(x=al.loc[("ND", y1), "share_55plus"], line_dash="dot", line_color="gray",
                  annotation_text="all industries", annotation_position="top")
    lib.layout(fig, 520, legend=False).update_xaxes(title="% of owners aged 55 or older", range=[0, 100])
    lib.show(fig, "sup_owners", title=f"North Dakota owners aged 55 or older, by industry, {y1}")
    st.caption(f"Annual Business Survey {y1}: owners of employer firms that answered (up to four owners a firm). Bars show "
               f"90% margins of error; gray bars have margins wider than {WIDE_MOE} points, so read them as rough. "
               "Industries Census did not publish for ND are left out.")
    w = n[(n.year == y1) & (n.sector == "00")].set_index("geo").reindex(GEOS)
    fig = go.Figure(go.Bar(x=[PEER_NAMES[g] for g in w.index], y=w.share_55plus,
                           marker=dict(color=[color(g) for g in w.index], line=dict(width=0)),
                           error_y=dict(type="data", array=w.share_55plus_moe90, color="#999", thickness=1),
                           hovertemplate="%{x}: %{y:.0f}%<extra></extra>"))
    lib.layout(fig, 300, ytitle="% of owners 55 or older", legend=False)
    lib.show(fig, "sup_owners_geo", title=f"Owners aged 55 or older, all industries, {y1}")
    lib.data_table(n[n.year == y1].pivot_table(index="sector_name", columns="geo", values="share_55plus")
                   .reindex(columns=GEOS).round(1).rename(columns=PEER_NAMES).reset_index(),
                   f"Owners aged 55 or older by industry and place, %, {y1} (table)", key="sup_owners_t")
    acq = a[(a.question == "Year owner acquired the business") & (a.sector == "00") & (a.year == y1) & a.geo.isin(["ND", "US"])]
    if len(acq):
        lib.data_table(acq.pivot_table(index="category", columns="geo", values="share").round(1).reset_index(),
                       f"When owners acquired their business, % of owners, {y1} (table)", key="sup_owners_acq_t")
    if (OUT / "owners_demographics.csv").exists():
        ownership()


def ownership():
    t = lib.table("owners_demographics.csv", dtype={"sector": str})
    y0, y1 = int(t.year.min()), int(t.year.max())
    st.markdown("##### Who owns employer businesses")
    st.markdown("Employer firms by the majority owners' sex, ethnicity, race and veteran status, as shares of firms "
                "whose owners could be classified (publicly held firms are left out).")
    a = t[(t.sector == "00") & ~t.detail.astype(bool)].set_index(["geo", "year", "category"])
    k = st.columns(3)
    for i, (cat, lab) in enumerate((("Female", "Women-owned"), ("Minority", "Minority-owned"), ("Veteran", "Veteran-owned"))):
        nd, us = a.loc[("ND", y1, cat)], a.loc[("US", y1, cat)]
        k[i].metric(f"{lab} employer firms, ND, {y1}", f"{nd.share:.0f}%",
                    f"± {nd.share_moe90:.1f} pts; US {us.share:.0f}%; ND {y0} {a.loc[('ND', y0, cat)].share:.0f}%",
                    delta_color="off", delta_arrow="off")
    c = st.columns([1, 2])
    dim = c[0].radio("Owners by", ["Sex", "Race", "Ethnicity", "Veteran status"], horizontal=True, key="sup_own_dim")
    d = t[(t.sector == "00") & (t.dimension == dim) & (t.year == y1) & ~t.detail.astype(bool)]
    if dim == "Race":
        d = pd.concat([d, t[(t.sector == "00") & (t.year == y1) & t.detail.astype(bool)]])
    cats = list(dict.fromkeys(d.category))
    fig = go.Figure()
    for i, g in enumerate(GEOS):
        e = d[d.geo == g].set_index("category").reindex(cats)
        fig.add_bar(x=cats, y=e.share, name=PEER_NAMES[g], marker=dict(color=color(g) if g in ("ND", "US") else
                                                                       ["#C9B37E", "#8E8CD8", "#7FCFA0", "#D98FB0"][i % 4],
                                                                       line=dict(width=0)),
                    error_y=dict(type="data", array=e.share_moe90, color="#999", thickness=1),
                    hovertemplate=PEER_NAMES[g] + ", %{x}: %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="group")
    lib.layout(fig, 360, ytitle="% of classifiable employer firms").update_yaxes(type="log" if dim != "Sex" else "linear")
    lib.show(fig, "sup_own", title=f"Employer firms by owners' {dim.lower()}, {y1}")
    st.caption("Log scale for race, ethnicity and veteran status, so small groups are visible. Race groups can overlap "
               "(owners may report more than one race); 'Minority' means any race other than White alone, or Hispanic. "
               "Bars show approximate 90% margins.")
    cat = c[1].selectbox("Industry detail for North Dakota", ["Female", "Minority", "Veteran",
                                                             "American Indian and Alaska Native", "Hispanic"],
                         key="sup_own_cat", format_func=lambda x: {"Female": "Women-owned", "Minority": "Minority-owned",
                                                                   "Veteran": "Veteran-owned"}.get(x, x + "-owned"))
    s = t[(t.geo == "ND") & (t.year == y1) & (t.category == cat) & (t.sector != "00")]
    s = s.assign(shown=s.share.where(s.reliable.astype(bool)))
    lib.data_table(s.sort_values("shown", ascending=False)[["sector_name", "firms", "shown", "share_moe90", "employees"]]
                   .round(1).rename(columns={"sector_name": "Industry", "firms": "Firms", "shown": "Share of firms (%)",
                                             "share_moe90": "90% margin (points)", "employees": "Employees"}),
                   f"North Dakota, {cat.lower() if cat in ('Female', 'Minority', 'Veteran') else cat}-owned firms by "
                   f"industry, {y1} (table)", key="sup_own_t")
    st.caption("Shares resting on fewer than 20 firms or on counts with a relative standard error above 50% are left "
               "blank. Annual Business Survey (Census Bureau), employer firms.")


# ------------------------------------------------------------------ targeted industries vs peers
def targets():
    t = lib.table("target_industries_peers.csv")
    y = int(t.year.iloc[0])
    st.subheader("ND Commerce's targeted industries in North Dakota and the peer states")
    st.markdown("The six targeted industries (Commerce's definitions, IPBA's industry codes; see Industry profiles) "
                "measured the same way in each state: concentration against the US, job change, and pay.")
    groups = [g for g in t.group.unique()]
    c = st.columns([2, 1])
    measure = c[0].radio("Measure", ["Concentration (location quotient)", "Job change (%)", "Average pay ($)"],
                         horizontal=True, key="sup_tgt_m")
    col = {"Concentration (location quotient)": "lq", "Job change (%)": "growth_pct", "Average pay ($)": "avg_pay"}[measure]
    w = t.pivot_table(index="group", columns="geo", values=col).reindex(groups).reindex(columns=GEOS[:-1])
    flag = t.pivot_table(index="group", columns="geo", values="flag_withheld", aggfunc="max").reindex(groups) \
        .reindex(columns=GEOS[:-1]).fillna(False).astype(bool)
    txt = w.map(lambda v: "–" if pd.isna(v) else (f"{v:.2f}" if col == "lq" else
                                                     (f"{v:+.1f}%" if col == "growth_pct" else f"${v / 1000:,.0f}k")))
    txt = txt.where(~flag, txt + "*")
    z = w.copy()
    if col == "lq":
        z = z.clip(upper=3)
    fig = go.Figure(go.Heatmap(z=z.values, x=[PEER_NAMES[g] for g in w.columns], y=w.index, text=txt.values,
                               texttemplate="%{text}", colorscale=lib.SEQ[::-1] if col != "growth_pct" else "RdYlGn",
                               zmid=0 if col == "growth_pct" else None, showscale=False,
                               hovertemplate="%{y}, %{x}: %{text}<extra></extra>"))
    lib.layout(fig, 360, legend=False)
    lib.show(fig, "sup_targets", title=f"Targeted industries by state, {y}: {measure.lower()}")
    st.caption("Jobs are sums of the industry codes BLS publishes in each state (a floor). * = a quarter or more of the "
               "group's establishments in that state are in codes BLS withheld, so compare with care. Job change uses "
               "codes published in both years (technology-based business from 2022). Location quotients above 3 share "
               "the darkest shade.")
    tab = t[["geo", "group", "jobs", "share_private_jobs", "lq", "growth_pct", "from_year", "avg_pay", "pay_vs_us",
             "estabs_withheld_share"]].copy()
    tab["share_private_jobs"] *= 100
    tab["estabs_withheld_share"] *= 100
    lib.data_table(tab.round(2).rename(columns={"geo": "State", "group": "Targeted industry", "jobs": "Jobs (at least)",
                                                "share_private_jobs": "Share of private jobs (%)", "lq": "Location quotient",
                                                "growth_pct": "Job change (%)", "from_year": "Change from",
                                                "avg_pay": "Average pay ($)", "pay_vs_us": "Pay vs US, same codes (%)",
                                                "estabs_withheld_share": "Establishments in withheld codes (%)"}),
                   "All states and measures (table)", key="sup_targets_t")
    if (OUT / "target_occupations.csv").exists():
        occupations()


def occupations():
    o = lib.table("target_occupations.csv")
    g = lib.table("target_occ_groups.csv", dtype={"soc_major": str})
    st.markdown("##### Who does the work: occupations in each targeted industry")
    grp = st.selectbox("Targeted industry", sorted(o.group.unique()), key="sup_occ_group")
    d = o[o.group == grp].sort_values("est_jobs")
    fig = go.Figure(go.Bar(y=d.occupation, x=d.est_jobs, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                           customdata=d[["share_of_group", "nd_median_wage"]].values,
                           hovertemplate="%{y}: about %{x:,.0f} jobs (%{customdata[0]:.1f}%), ND median wage "
                                         "$%{customdata[1]:,.0f}<extra></extra>"))
    lib.layout(fig, 420, legend=False).update_xaxes(title="Estimated ND jobs in this industry")
    lib.show(fig, "sup_occ", title=f"Largest occupations in {grp.lower()}, North Dakota (estimated)")
    lib.data_table(d.sort_values("est_jobs", ascending=False)[["occ_code", "occupation", "est_jobs", "share_of_group",
                                                               "nd_median_wage"]].round(1).rename(columns={
        "occ_code": "SOC", "occupation": "Occupation", "est_jobs": "Estimated ND jobs", "share_of_group":
        "Share of the industry's jobs (%)", "nd_median_wage": "ND median annual wage, all industries ($)"}),
        "Top occupations (table)", key="sup_occ_t")
    gg = g[g.group == grp].head(8)
    lib.data_table(gg[["major_title", "est_jobs", "share_of_group", "nd_awards_linked", "awards_per_1k_jobs"]].round(1)
                   .rename(columns={"major_title": "Occupation group", "est_jobs": "Estimated jobs in this industry",
                                    "share_of_group": "Share (%)", "nd_awards_linked": "ND graduates linked a year",
                                    "awards_per_1k_jobs": "Graduates per 1,000 ND jobs in the group"}),
                   "Occupation groups and ND graduates (table)", key="sup_occ_g_t")
    st.caption(f"Estimated: North Dakota's published jobs in each code of the industry, spread over occupations with the "
               f"national staffing pattern of that code (BLS OEWS, May {int(o.oews_year.iloc[0])}); ND's actual mix can "
               f"differ. Wages: ND medians for the occupation across all industries. Graduates: awards by ND institutions "
               f"in {int(gg.ipeds_year.iloc[0]) - 1}-{str(int(gg.ipeds_year.iloc[0]))[2:]} linked to each occupation group "
               "(NCES-BLS crosswalk), statewide, not only for this industry.")


# ------------------------------------------------------------------ SBIR/STTR
def sbir():
    s = lib.table("sbir_states.csv").set_index("geo")
    ag = lib.table("sbir_nd_agency.csv")
    rg = lib.table("sbir_nd_region.csv")
    y0, y1 = int(s.year_from.iloc[0]), int(s.year_to.iloc[0])
    st.subheader("SBIR/STTR: federal research awards to small businesses")
    st.markdown("Small Business Innovation Research and Technology Transfer awards fund early-stage research and "
                "development. How often North Dakota businesses win them, from which agencies, where in the state, and "
                "how ND compares per resident.")
    k = st.columns(4)
    k[0].metric(f"ND awards, {y0}-{y1}", lib.num(s.loc["ND", "awards"]),
                f"{int(s.loc['ND', 'firms'])} companies", delta_color="off", delta_arrow="off")
    k[1].metric("Award dollars per resident a year, ND", f"${s.loc['ND', 'dollars_per_resident_yr']:,.2f}",
                f"US ${s.loc['US', 'dollars_per_resident_yr']:,.2f}", delta_color="off", delta_arrow="off")
    k[2].metric("Awards per 100,000 residents a year, ND", f"{s.loc['ND', 'awards_per_100k_yr']:.2f}",
                f"US {s.loc['US', 'awards_per_100k_yr']:.2f}", delta_color="off", delta_arrow="off")
    n1 = s.loc["ND", "p1_firms"]
    k[3].metric("Phase I companies winning Phase II within 3 years, ND",
                f"{s.loc['ND', 'conversion']:.0f}%" if n1 >= MIN_FIRMS else "too few to rate",
                f"{int(s.loc['ND', 'p2_firms'])} of {int(n1)} companies; US {s.loc['US', 'conversion']:.0f}%",
                delta_color="off", delta_arrow="off")
    cols = st.columns(2)
    with cols[0]:
        w = s.reindex(GEOS)
        fig = go.Figure(go.Bar(x=[PEER_NAMES[g] for g in w.index], y=w.dollars_per_resident_yr,
                               marker=dict(color=[color(g) for g in w.index], line=dict(width=0)),
                               hovertemplate="%{x}: $%{y:,.2f}<extra></extra>"))
        lib.layout(fig, 320, ytitle="$ per resident a year", legend=False)
        lib.show(fig, "sup_sbir_pc", title=f"SBIR/STTR award dollars per resident a year, {y0}-{y1}")
    with cols[1]:
        a = ag.groupby("agency").awards.sum().sort_values()
        fig = go.Figure(go.Bar(y=a.index, x=a.values, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                               hovertemplate="%{y}: %{x} awards<extra></extra>"))
        lib.layout(fig, 320, legend=False).update_xaxes(title="Awards")
        lib.show(fig, "sup_sbir_agency", title=f"North Dakota awards by agency, {y0}-{y1}")
    lib.data_table(s.reset_index()[["geo", "awards", "firms", "phase2", "dollars", "awards_per_100k_yr",
                                    "dollars_per_resident_yr", "p1_firms", "p2_firms", "conversion"]].round(2),
                   "Awards by state (table)", key="sup_sbir_t")
    lib.data_table(ag.round(0), "North Dakota awards by agency and phase (table)", key="sup_sbir_ag_t")
    lib.data_table(rg.round(0), "North Dakota awards by planning region (table)", key="sup_sbir_rg_t")
    st.caption(f"SBIR.gov award data, award years {y0}-{y1} (the current year is incomplete). Phase I to Phase II: "
               f"companies whose first Phase I came in {int(s.conv_from.iloc[0])}-{int(s.conv_to.iloc[0])}, and how many "
               f"won a Phase II within 3 years; rates on fewer than {MIN_FIRMS} companies are not shown. Regions come from "
               "the award city. No company is named here; award records are public on SBIR.gov.")
    if (OUT / "formd_states.csv").exists():
        capital()


def capital():
    t = lib.table("formd_states.csv")
    nd = lib.table("formd_nd.csv")
    y0, y1 = int(t.year.min()), int(t.year.max())
    st.markdown("##### Private capital raised: SEC Form D notices")
    st.markdown("Companies raising money from investors without registering the offering, as most angel and venture "
                "rounds do, file a Form D with the SEC. Counted here by the company's principal place of business.")
    op = t[t.venture].groupby(["geo", "year"]).agg(offerings=("offerings", "sum"), sold=("sold", "sum"),
                                                    population=("population", "first")).reset_index()
    op["per_100k"] = op.offerings / op.population * 1e5
    op["sold_pc"] = op.sold / op.population
    w = op[op.year.between(y1 - 4, y1)].groupby("geo").agg(offerings=("offerings", "sum"), sold=("sold", "sum"),
                                                          pop=("population", "mean"))
    w["per_100k_yr"] = w.offerings / 5 / w["pop"] * 1e5
    w["sold_pc_yr"] = w.sold / 5 / w["pop"]
    k = st.columns(3)
    k[0].metric(f"ND company-building offerings, {y1 - 4}-{y1}", lib.num(w.loc["ND", "offerings"]))
    k[1].metric("Offerings per 100,000 residents a year, ND", f"{w.loc['ND', 'per_100k_yr']:.1f}",
                f"US {w.loc['US', 'per_100k_yr']:.1f}", delta_color="off", delta_arrow="off")
    k[2].metric("Reported sold per resident a year, ND", f"${w.loc['ND', 'sold_pc_yr']:,.0f}",
                f"US ${w.loc['US', 'sold_pc_yr']:,.0f}", delta_color="off", delta_arrow="off")
    fig = go.Figure()
    for i, g in enumerate(GEOS):
        e = op[op.geo == g]
        fig.add_trace(go.Scatter(x=e.year, y=e.per_100k, name=PEER_NAMES[g], mode="lines+markers",
                                 line=dict(color=color(g), dash=lib.DASHES[i % len(lib.DASHES)],
                                           width=3 if g == "ND" else 1.5),
                                 hovertemplate=PEER_NAMES[g] + ", %{x}: %{y:.1f}<extra></extra>"))
    lib.layout(fig, 320, ytitle="Offerings per 100,000 residents")
    lib.show(fig, "sup_formd", title="New Form D offerings by companies outside real estate and finance, per 100,000 residents")
    n = nd[nd.year.between(y1 - 4, y1)].groupby("group").agg(offerings=("offerings", "sum"), sold=("sold", "sum"))
    lib.data_table(n.sort_values("offerings", ascending=False).reset_index().rename(columns={
        "group": "Industry (issuer's choice)", "offerings": "Offerings", "sold": "Reported sold ($)"}),
        f"North Dakota offerings by industry, {y1 - 4}-{y1} (table)", key="sup_formd_nd_t")
    lib.data_table(op.round(2).rename(columns={"geo": "Place", "year": "Year", "offerings": "Offerings",
                                               "sold": "Reported sold ($)", "per_100k": "Per 100,000 residents",
                                               "sold_pc": "Sold per resident ($)"}).drop(columns="population"),
                   "Company-building offerings by place and year (table)", key="sup_formd_t")
    st.caption(f"SEC Form D data sets, {y0}-{y1}, new notices only (amendments left out). Charts and the first three figures cover "
               "company-building raises: operating companies outside real estate and finance (pooled funds excluded); "
               "the industry table shows all. Wyoming's rate is high because many companies based elsewhere register "
               "there. Amount sold is what the first notice reports, so dollars are a "
               "floor, and some raises file no Form D. No company is named here; notices are public on EDGAR.")


def page():
    lib.header("Business support insights", "Benchmarks for the organizations that advise, finance and develop North "
               "Dakota businesses: new-business survival, owners near retirement, the state's targeted industries "
               "against its neighbors, and federal research awards to small businesses.", "official", "estimate",
               note="Census Bureau, BLS and SBA; pooled rates, margins and comparisons: IPBA calculations.")
    need = ["survival_sector.csv", "owners_55plus.csv", "target_industries_peers.csv", "sbir_states.csv"]
    if not all((OUT / f).exists() for f in need):
        st.info("These tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return
    tabs = st.tabs(["New business survival", "Owners and succession", "Targeted industries and peers",
                    "SBIR/STTR and startup capital"])
    with tabs[0]:
        survival()
    with tabs[1]:
        owners()
    with tabs[2]:
        targets()
    with tabs[3]:
        sbir()
    lib.method_panel([
        "Survival: Census Business Dynamics Statistics, firms by state, sector and firm age. Survival after k years = "
        "firms aged k in year t + k / new firms (aged 0) in year t, pooled over the latest five birth years with full "
        "follow-up; cells with fewer than 100 pooled births are not shown. BDS dates a firm by its oldest "
        "establishment, so the ratio approximates cohort survival (Haltiwanger et al., 2013).",
        "Owners: Census Annual Business Survey, characteristics of owners of employer firms (up to four owners a "
        "firm), by state and sector. 55 or older = '55 to 64' + '65 or over'; its 90% margin combines the two published "
        "standard errors as if independent.",
        "Targeted industries: the same codes and rules as on Industry profiles, applied to each state with BLS QCEW. "
        "Location quotients compare a state's published codes with the same codes in the US.",
        "SBIR/STTR: SBIR.gov award data by the award's company state; companies matched by UEI, then DUNS, then name. "
        "Per resident uses Census population estimates averaged over the window.",
        "Occupations: ND's published jobs in each targeted industry code spread over occupations with the code's national "
        "staffing pattern (BLS OEWS industry-specific estimates; nearest published parent code when a code is not "
        "published alone). Graduates: ND IPEDS awards linked to SOC major groups with the NCES-BLS crosswalk.",
        "Ownership: Census Annual Business Survey company summary; firms counted by majority (51%+) owners, as shares of classifiable firms; 90% margin approximated as 1.645 x RSE x share; small or unreliable cells hidden.",
        "Capital: SEC Form D notices by the primary issuer's state, new notices only; amount sold as first reported.",
        "Neutral benchmarks from public, aggregated data: they do not evaluate any program or business."],
        refs=("haltiwanger2013", "muro2015"))
    lib.source_line("bds_sec_fa", "abs", "abs_cs", "qcew", "commerce_targets", "oews_ind", "ipeds", "sbir", "formd", "popest")


if __name__ == "__main__":
    page()
